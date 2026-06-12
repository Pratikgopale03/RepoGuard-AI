import io
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe_text(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _mk_placeholder_chart(title: str, destination: str) -> str:
    plt.figure(figsize=(9, 4.2))
    plt.text(0.5, 0.5, f"{title}\n(Chart image unavailable)", ha="center", va="center", fontsize=13)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(destination, dpi=140)
    plt.close()
    return destination


def _export_plotly_chart_images(chart_figures: Optional[Dict[str, Any]], temp_dir: str) -> List[Dict[str, str]]:
    exported_items: List[Dict[str, str]] = []
    if not isinstance(chart_figures, dict) or len(chart_figures) == 0:
        for idx in range(1, 8):
            placeholder_path = _mk_placeholder_chart(f"Chart {idx}", os.path.join(temp_dir, f"chart_{idx}.png"))
            exported_items.append({"key": f"placeholder_{idx}", "title": f"Chart {idx}", "path": placeholder_path})
        return exported_items

    for idx, (key, figure) in enumerate(chart_figures.items(), start=1):
        image_path = os.path.join(temp_dir, f"chart_{idx}_{key}.png")
        try:
            image_bytes = figure.to_image(format="png", width=1300, height=700, scale=1)
            with open(image_path, "wb") as fp:
                fp.write(image_bytes)
            exported_items.append({"key": str(key), "title": str(key).replace("_", " ").title(), "path": image_path})
        except Exception:
            placeholder_path = _mk_placeholder_chart(f"{key}", image_path)
            exported_items.append({"key": str(key), "title": str(key).replace("_", " ").title(), "path": placeholder_path})

    while len(exported_items) < 7:
        idx = len(exported_items) + 1
        placeholder_path = _mk_placeholder_chart(f"Chart {idx}", os.path.join(temp_dir, f"chart_{idx}.png"))
        exported_items.append({"key": f"placeholder_{idx}", "title": f"Chart {idx}", "path": placeholder_path})

    return exported_items[:7]


def _chart_title(key: str, fallback_title: str) -> str:
    mapping = {
        "radar": "Repository Radar",
        "network": "Contributor Network",
        "language_pie": "Language Distribution",
        "security_matrix": "Security Risk Matrix",
        "dependency_risk": "Dependency Risk",
    }
    return mapping.get(key, fallback_title)


def _chart_narrative(key: str, analysis_data: Dict[str, Any]) -> str:
    summary = analysis_data.get("summary", {}) if isinstance(analysis_data, dict) else {}
    repo_data = analysis_data.get("repository_data", {}) if isinstance(analysis_data, dict) else {}
    ai = analysis_data.get("ai_analysis", {}) if isinstance(analysis_data, dict) else {}

    health = _safe_text(summary.get("health_score"))
    security = _safe_text(summary.get("security_score"))
    bus = _safe_text(summary.get("bus_factor_percent"))
    debt = _safe_text(summary.get("technical_debt_hours"))

    languages = repo_data.get("languages", {})
    lang_text = ""
    if isinstance(languages, dict) and languages:
        total = sum(v for v in languages.values() if isinstance(v, (int, float))) or 1
        top = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:3]
        lang_parts = [f"{k} ({(v / total) * 100:.1f}%)" for k, v in top if isinstance(v, (int, float))]
        lang_text = ", ".join(lang_parts)

    risk_level = _safe_text(ai.get("security_risk", {}).get("risk_level"))
    debt_level = _safe_text(ai.get("technical_debt", {}).get("debt_level"))
    concentration = _safe_text(ai.get("bus_factor", {}).get("concentration_risk"))

    narratives = {
        "radar": (
            f"This radar chart compares core repository dimensions in one view. Current headline signals are "
            f"Health {health}%, Security {security}%, and Bus Factor {bus}%. Use it to spot imbalance quickly "
            f"and prioritize dimensions that lag behind the others."
        ),
        "network": (
            f"The contributor network visual highlights ownership spread and dependency on key individuals. "
            f"Bus factor is {bus}% with concentration risk marked as {concentration}. If ownership appears clustered, "
            f"reduce delivery risk by rotating maintainers and documenting critical workflows."
        ),
        "language_pie": (
            "Language distribution indicates where most maintenance effort will accumulate. "
            + (f"Top observed stack share: {lang_text}. " if lang_text else "")
            + "A highly skewed distribution can simplify standards but may create single-stack bottlenecks."
        ),
        "security_matrix": (
            f"Security matrix contextualizes severity and likelihood patterns from repository metadata. "
            f"Current security score is {security}% with overall risk level {risk_level}. Use this to sequence fixes by "
            f"criticality before broader hardening work."
        ),
        "dependency_risk": (
            f"Dependency risk view reflects potential operational drag from outdated or vulnerable package surfaces. "
            f"Technical debt is estimated at {debt} hours and debt level is {debt_level}. Focus first on dependencies "
            f"that are both high-impact and frequently touched."
        ),
    }

    return narratives.get(
        key,
        "This chart provides a supporting lens for repository health. Correlate it with the executive metrics and "
        "AI findings to determine actionable engineering priorities.",
    )


def _styles() -> Dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=sample["Heading1"], fontSize=24, leading=28, textColor=colors.HexColor("#0f172a")),
        "h2": ParagraphStyle("h2", parent=sample["Heading2"], fontSize=16, leading=20, textColor=colors.HexColor("#0f172a")),
        "h3": ParagraphStyle("h3", parent=sample["Heading3"], fontSize=12, leading=15, textColor=colors.HexColor("#0f172a")),
        "body": ParagraphStyle("body", parent=sample["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#0f172a")),
        "small": ParagraphStyle("small", parent=sample["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#334155")),
        "muted": ParagraphStyle("muted", parent=sample["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#64748b")),
        "mono": ParagraphStyle("mono", parent=sample["BodyText"], fontName="Courier", fontSize=8.0, leading=9.5, textColor=colors.HexColor("#0f172a")),
    }


def _score_band(score: Any) -> str:
    try:
        val = float(score)
    except (TypeError, ValueError):
        return "unknown"
    if val >= 80:
        return "strong"
    if val >= 60:
        return "moderate"
    if val >= 40:
        return "elevated risk"
    return "critical"


def _paragraph_list(items: List[str], styles: Dict[str, ParagraphStyle]) -> List[Paragraph]:
    return [Paragraph(f"- {item}", styles["small"]) for item in items]


def _draw_header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(doc.leftMargin, A4[1] - 1.0 * cm, "RepoGuard AI - Repository Intelligence Report")
    canvas.drawRightString(A4[0] - doc.rightMargin, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _repo_tree_ascii_lines(tree: Dict[str, Any], max_depth: int = 4, max_lines: int = 140) -> List[str]:
    lines: List[str] = []

    def walk(node: Dict[str, Any], prefix: str, depth: int, is_last: bool) -> None:
        if len(lines) >= max_lines:
            return

        name = str(node.get("name", ""))
        node_type = node.get("type", "file")
        children = node.get("children", {}) if isinstance(node.get("children"), dict) else {}

        if depth == 0:
            lines.append(f"{name}/")
        else:
            connector = "`-- " if is_last else "|-- "
            suffix = "/" if node_type == "dir" else ""
            lines.append(f"{prefix}{connector}{name}{suffix}")

        if depth >= max_depth or node_type != "dir":
            return

        sorted_children = sorted(children.values(), key=lambda c: (c.get("type") != "dir", c.get("name", "")))
        for idx, child in enumerate(sorted_children):
            if len(lines) >= max_lines:
                return
            next_prefix = prefix + ("    " if is_last else "|   ")
            walk(child, next_prefix, depth + 1, idx == len(sorted_children) - 1)

    walk(tree, "", 0, True)
    if len(lines) >= max_lines:
        lines.append("`-- ... (truncated)")
    return lines


def _html_preserve_spaces(text: str) -> str:
    return text.replace(" ", "&nbsp;")


def _chunk_lines(lines: List[str], chunk_size: int) -> List[List[str]]:
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]


def generate_pdf_report(
    analysis_data: Dict[str, Any],
    chart_figures: Optional[Dict[str, Any]] = None,
    output_path: str = "repo_health_report.pdf",
) -> str:
    styles = _styles()
    summary = analysis_data.get("summary", {})
    repo_data = analysis_data.get("repository_data", {})
    ai = analysis_data.get("ai_analysis", {})
    health = ai.get("repository_health_score", {})
    bus_factor = ai.get("bus_factor", {})
    technical_debt = ai.get("technical_debt", {})
    security_risk = ai.get("security_risk", {})

    with tempfile.TemporaryDirectory() as temp_dir:
        chart_items = _export_plotly_chart_images(chart_figures, temp_dir)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.7 * cm,
            bottomMargin=1.6 * cm,
        )
        story: List[Any] = []

        # 1) Cover page
        story.append(Spacer(1, 3.0 * cm))
        story.append(Paragraph("RepoGuard AI", styles["title"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Repository Health Intelligence Report", styles["h2"]))
        story.append(Spacer(1, 0.8 * cm))
        story.append(Paragraph(f"Repository: <b>{_safe_text(repo_data.get('full_name'))}</b>", styles["body"]))
        story.append(Paragraph(f"Generated: {_safe_text(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))}", styles["body"]))
        story.append(Spacer(1, 1.2 * cm))
        story.append(Paragraph("Confidential engineering assessment for maintainability, resilience, and security planning.", styles["small"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Prepared for engineering leadership to support roadmap, risk, and resourcing decisions.", styles["muted"]))
        story.append(PageBreak())

        # 2) Executive summary
        story.append(Paragraph("2. Executive Summary", styles["h2"]))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("This report summarizes repository quality signals, contributor resilience, technical debt, and security risk.", styles["body"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(
            Paragraph(
                "The scores below are directional indicators. They should be interpreted alongside repository context, "
                "recent change velocity, and team ownership.",
                styles["small"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))

        summary_table = Table(
            [
                ["Health Score", f"{_safe_text(summary.get('health_score'))}%"],
                ["Bus Factor", f"{_safe_text(summary.get('bus_factor_percent'))}%"],
                ["Technical Debt", f"{_safe_text(summary.get('technical_debt_hours'))} hours"],
                ["Security Score", f"{_safe_text(summary.get('security_score'))}%"],
            ],
            colWidths=[7 * cm, 8.5 * cm],
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * cm))
        story.extend(
            _paragraph_list(
                [
                    f"Health score indicates overall codebase stability ({_score_band(summary.get('health_score'))}).",
                    f"Bus factor reflects contributor concentration risk ({_score_band(summary.get('bus_factor_percent'))}).",
                    "Technical debt hours estimate the remediation effort to reduce friction and maintenance drag.",
                    f"Security score captures vulnerability posture ({_score_band(summary.get('security_score'))}).",
                ],
                styles,
            )
        )
        story.append(Spacer(1, 0.6 * cm))

        # 3) Repository metadata
        story.append(Paragraph("3. Repository Metadata", styles["h2"]))
        repo_rows = [
            ["Full Name", _safe_text(repo_data.get("full_name"))],
            ["Description", _safe_text(repo_data.get("description"))],
            ["Visibility", _safe_text(repo_data.get("visibility"))],
            ["Stars", _safe_text(repo_data.get("stars"))],
            ["Forks", _safe_text(repo_data.get("forks_count"))],
            ["Open Issues", _safe_text(repo_data.get("open_issues"))],
            ["Open PRs", _safe_text(repo_data.get("open_pull_requests"))],
            ["License", _safe_text(repo_data.get("license"))],
            ["Last Commit", _safe_text(repo_data.get("last_commit_date"))],
        ]
        meta_table = Table(repo_rows, colWidths=[5.2 * cm, 10.3 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.4 * cm))

        repo_tree = repo_data.get("repo_tree", {"name": repo_data.get("full_name", "repo"), "type": "dir", "children": {}})
        tree_lines = _repo_tree_ascii_lines(repo_tree, max_depth=4, max_lines=220)
        if tree_lines:
            story.append(Paragraph("Repository Tree Snapshot", styles["h3"]))
            story.append(Paragraph("Branch-style structure of the default branch.", styles["small"]))
            tree_chunks = _chunk_lines(tree_lines, 45)
            for idx, chunk in enumerate(tree_chunks, start=1):
                if idx > 1:
                    story.append(PageBreak())
                    story.append(Paragraph("Repository Tree Snapshot (cont.)", styles["h3"]))
                tree_html = "<br/>".join(_html_preserve_spaces(line) for line in chunk)
                tree_table = Table([[Paragraph(tree_html, styles["mono"]) ]], colWidths=[15.6 * cm])
                tree_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                            ("PADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.append(tree_table)

        branches = repo_data.get("branches", [])
        if isinstance(branches, list) and branches:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Repository Branches", styles["h3"]))
            story.append(Paragraph("Active branches at the time of analysis.", styles["small"]))
            branch_rows = [["Branch", "Protected", "Commit"]]
            for branch in branches[:30]:
                name = _safe_text(branch.get("name"))
                protected = "Yes" if branch.get("protected") else "No"
                sha = _safe_text(branch.get("commit_sha"))
                short_sha = sha[:7] if isinstance(sha, str) else ""
                branch_rows.append([name, protected, short_sha])
            branch_table = Table(branch_rows, colWidths=[8.2 * cm, 3 * cm, 4 * cm])
            branch_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("PADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(branch_table)

        story.append(PageBreak())

        # 4) Health score breakdown
        story.append(Paragraph("4. Health Score Breakdown", styles["h2"]))
        story.append(Paragraph(f"Score: <b>{_safe_text(health.get('score'))}</b>", styles["body"]))
        story.append(Paragraph(f"Confidence: <b>{_safe_text(health.get('confidence'))}</b>", styles["body"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(f"Rationale: {_safe_text(health.get('rationale'))}", styles["small"]))
        story.append(Spacer(1, 0.2 * cm))
        story.extend(
            _paragraph_list(
                [
                    "Interpretation considers recent change volume, test coverage signals, and issue backlog health.",
                    "Confidence reflects AI certainty based on repository metadata and code signals.",
                ],
                styles,
            )
        )
        story.append(Spacer(1, 0.6 * cm))

        # 5) AI analysis tables
        story.append(Paragraph("5. AI Analysis Overview", styles["h2"]))
        rows = [["Dimension", "Score", "Risk/Notes"]]
        rows.append(["Bus Factor", _safe_text(bus_factor.get("bus_factor_percent")), _safe_text(bus_factor.get("concentration_risk"))])
        rows.append(["Technical Debt", _safe_text(technical_debt.get("estimated_hours")), _safe_text(technical_debt.get("debt_level"))])
        rows.append(["Security", _safe_text(security_risk.get("security_score")), _safe_text(security_risk.get("risk_level"))])
        rows.append(["Maintainability", _safe_text(ai.get("code_maintainability", {}).get("maintainability_score")), "See hotspots"]) 
        rows.append(["Documentation", _safe_text(ai.get("documentation_quality", {}).get("documentation_score")), "See gaps"]) 

        ai_table = Table(rows, colWidths=[4.5 * cm, 3 * cm, 8 * cm])
        ai_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(ai_table)
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Key Findings:", styles["h3"]))
        story.extend(
            _paragraph_list(
                [
                    f"Contributor concentration risk is {_safe_text(bus_factor.get('concentration_risk'))}.",
                    f"Debt level is {_safe_text(technical_debt.get('debt_level'))} with estimated remediation of {_safe_text(technical_debt.get('estimated_hours'))} hours.",
                    f"Security risk level is {_safe_text(security_risk.get('risk_level'))}.",
                    "Maintainability and documentation scores indicate operational friction over time.",
                ],
                styles,
            )
        )
        story.append(PageBreak())

        # 6) Charts pages
        story.append(Paragraph("6. Visual Analytics", styles["h2"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("The following pages embed generated chart snapshots with interpretation and recommended action focus.", styles["small"]))
        story.append(Spacer(1, 0.2 * cm))
        story.extend(
            _paragraph_list(
                [
                    "Each chart includes explanation text tied to current repository scores.",
                    "Use the narrative callouts to convert visuals into engineering actions.",
                    "Correlate chart insights with refactoring priorities in section 10.",
                ],
                styles,
            )
        )
        story.append(PageBreak())

        for idx, item in enumerate(chart_items, start=1):
            chart_key = item.get("key", f"chart_{idx}")
            chart_title = _chart_title(chart_key, item.get("title", f"Chart {idx}"))
            chart_path = item.get("path", "")
            narrative = _chart_narrative(chart_key, analysis_data)

            story.append(Paragraph(f"Chart {idx}: {escape(chart_title)}", styles["h3"]))
            story.append(Spacer(1, 0.15 * cm))

            chart_image = Image(chart_path, width=10.9 * cm, height=6.3 * cm)
            chart_text = Paragraph(escape(narrative), styles["small"])
            chart_panel = Table(
                [[chart_image, chart_text]],
                colWidths=[11.2 * cm, 4.4 * cm],
                hAlign="LEFT",
            )
            chart_panel.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(chart_panel)
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph("Action note: validate this visual against current sprint priorities and ownership constraints.", styles["muted"]))

            if idx % 2 == 0 and idx != len(chart_items):
                story.append(PageBreak())
            else:
                story.append(Spacer(1, 0.35 * cm))

        # 7) Contributor analysis
        contributors = repo_data.get("top_20_contributors", [])
        story.append(Paragraph("7. Contributor Analysis", styles["h2"]))
        story.append(Paragraph("Top contributors and activity concentration are used to estimate resilience to team changes.", styles["small"]))
        top_rows = [["Login", "Contributions"]]
        for item in contributors[:15]:
            top_rows.append([_safe_text(item.get("login")), _safe_text(item.get("contributions"))])
        contrib_table = Table(top_rows, colWidths=[9 * cm, 6.5 * cm])
        contrib_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(contrib_table)
        story.append(Spacer(1, 0.6 * cm))

        # 8) Security review
        sec = ai.get("security_risk", {})
        findings = sec.get("critical_findings", [])
        story.append(Paragraph("8. Security Review", styles["h2"]))
        story.append(Paragraph(f"Security Score: <b>{_safe_text(sec.get('security_score'))}</b>", styles["body"]))
        story.append(Paragraph(f"Risk Level: <b>{_safe_text(sec.get('risk_level'))}</b>", styles["body"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("Security posture combines dependency risk, vulnerability indicators, and access hygiene signals.", styles["small"]))
        story.append(Paragraph("Critical Findings:", styles["h3"]))
        if isinstance(findings, list) and findings:
            for finding in findings[:15]:
                story.append(Paragraph(f"- {_safe_text(finding)}", styles["small"]))
        else:
            story.append(Paragraph("- No critical findings reported by AI layer.", styles["small"]))
        story.append(Spacer(1, 0.6 * cm))

        # 9) Technical debt summary
        td = ai.get("technical_debt", {})
        story.append(Paragraph("9. Technical Debt Summary", styles["h2"]))
        story.append(Paragraph(f"Estimated Debt: <b>{_safe_text(td.get('estimated_hours'))} hours</b>", styles["body"]))
        story.append(Paragraph(f"Debt Level: <b>{_safe_text(td.get('debt_level'))}</b>", styles["body"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("Focus areas below represent high friction modules or hotspots that slow delivery.", styles["small"]))
        for area in td.get("top_debt_areas", [])[:20] if isinstance(td.get("top_debt_areas", []), list) else []:
            story.append(Paragraph(f"- {_safe_text(area)}", styles["small"]))
        story.append(PageBreak())

        # 10) Top 25 refactoring tickets
        priorities = ai.get("refactoring_priorities", {}).get("priorities", [])
        story.append(Paragraph("10. Top 25 Refactoring Tickets", styles["h2"]))
        story.append(Paragraph("Recommended actions prioritized by risk reduction, delivery acceleration, and stability impact.", styles["small"]))
        ticket_rows = [["#", "Title", "Area", "Effort(h)", "Risk", "Impact"]]
        if isinstance(priorities, list) and priorities:
            for idx, item in enumerate(priorities[:25], start=1):
                ticket_rows.append(
                    [
                        str(idx),
                        _safe_text(item.get("title")),
                        _safe_text(item.get("area")),
                        _safe_text(item.get("effort_hours")),
                        _safe_text(item.get("risk")),
                        _safe_text(item.get("impact")),
                    ]
                )
        else:
            ticket_rows.append(["1", "Refactor complex modules", "core", "16", "medium", "high"])

        tickets_table = Table(ticket_rows, colWidths=[1 * cm, 6.5 * cm, 2.4 * cm, 2 * cm, 2 * cm, 2 * cm], repeatRows=1)
        tickets_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(tickets_table)
        story.append(PageBreak())

        # 11) Recommendations and next steps
        story.append(Paragraph("11. Recommendations and Next Steps", styles["h2"]))
        story.append(Paragraph("Priority actions aligned to mitigate risk and improve delivery outcomes.", styles["small"]))
        story.extend(
            _paragraph_list(
                [
                    "Establish ownership coverage for key modules to reduce bus factor exposure.",
                    "Schedule targeted refactors that reduce cycle time in high change areas.",
                    "Address critical security findings and review dependency update cadence.",
                    "Improve documentation for onboarding, runbooks, and architectural decisions.",
                ],
                styles,
            )
        )
        story.append(Spacer(1, 0.6 * cm))

        # 12) Methodology and definitions
        story.append(Paragraph("12. Methodology and Definitions", styles["h2"]))
        story.append(
            Paragraph(
                "Scores are derived from repository metadata, contributor activity signals, dependency indicators, "
                "issue and pull request patterns, and AI-based assessment of risks.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 0.2 * cm))
        story.extend(
            _paragraph_list(
                [
                    "Health Score: composite signal of maintainability, change resilience, and operational hygiene.",
                    "Bus Factor: percentage of contributions concentrated in the top contributor cohort.",
                    "Technical Debt: estimated remediation effort to reduce churn and complexity hotspots.",
                    "Security Score: relative risk posture based on code and dependency indicators.",
                ],
                styles,
            )
        )
        story.append(Spacer(1, 0.6 * cm))

        # 13) Disclaimer
        story.append(Paragraph("13. Disclaimer", styles["h2"]))
        story.append(
            Paragraph(
                "This report provides decision support and should be validated with code review, "
                "security scanning, and engineering judgment.",
                styles["small"],
            )
        )

        doc.build(story, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)

    return output_path


def generate_pdf_bytes(analysis_data: Dict[str, Any], chart_figures: Optional[Dict[str, Any]] = None) -> bytes:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "repo_health_report.pdf")
        generate_pdf_report(analysis_data=analysis_data, chart_figures=chart_figures, output_path=output_path)
        with open(output_path, "rb") as fp:
            return fp.read()
