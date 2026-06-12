from typing import Any, Dict, List, Tuple

import networkx as nx
import plotly.graph_objects as go


def _base_layout(title: str, height: int = 320) -> Dict[str, Any]:
    return {
        "title": {
            "text": title,
            "font": {"size": 13, "color": "#94c4de", "family": "Inter, sans-serif"},
            "x": 0.02,
        },
        "height": height,
        "margin": {"l": 36, "r": 24, "t": 52, "b": 36},
        "paper_bgcolor": "rgba(5, 15, 28, 0.92)",
        "plot_bgcolor":  "rgba(5, 15, 28, 0.0)",
        "font": {"color": "#94c4de", "family": "Inter, sans-serif", "size": 12},
    }



def _build_radar_chart(analysis_data: Dict[str, Any]) -> go.Figure:
    ai = analysis_data.get("ai_analysis", {})
    categories = ["Code Quality", "Community", "Security", "Maintainability", "Documentation"]

    values = [
        int(ai.get("repository_health_score", {}).get("score", 60)),
        int(ai.get("contributor_distribution", {}).get("distribution_score", 55)),
        int(ai.get("security_risk", {}).get("security_score", 65)),
        int(ai.get("code_maintainability", {}).get("maintainability_score", 62)),
        int(ai.get("documentation_quality", {}).get("documentation_score", 58)),
    ]

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values + [values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                line={"color": "#60a5fa", "width": 2},
                marker={"size": 6, "color": "#93c5fd"},
                name="Repository Profile",
            )
        ]
    )
    fig.update_layout(
        **_base_layout("1) Repository Radar Chart"),
        polar={
            "radialaxis": {"visible": True, "range": [0, 100], "gridcolor": "rgba(148, 163, 184, 0.3)"},
            "angularaxis": {"gridcolor": "rgba(148, 163, 184, 0.25)"},
        },
        showlegend=False,
    )
    return fig


def _build_contributor_network(analysis_data: Dict[str, Any]) -> go.Figure:
    repo_data = analysis_data.get("repository_data", {})
    contributors = repo_data.get("top_20_contributors", [])

    graph = nx.Graph()
    graph.add_node("Repository")

    top_contributors = contributors[:15]
    for contributor in top_contributors:
        login = contributor.get("login", "unknown")
        contribution_count = max(int(contributor.get("contributions", 1)), 1)
        graph.add_node(login, contributions=contribution_count)
        graph.add_edge("Repository", login, weight=contribution_count)

    if len(graph.nodes) == 1:
        graph.add_node("No contributors")
        graph.add_edge("Repository", "No contributors", weight=1)

    positions = nx.spring_layout(graph, seed=42, k=0.8)

    edge_x: List[float] = []
    edge_y: List[float] = []
    for src, dst in graph.edges():
        x0, y0 = positions[src]
        x1, y1 = positions[dst]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    node_x: List[float] = []
    node_y: List[float] = []
    node_text: List[str] = []
    node_size: List[float] = []

    for node in graph.nodes():
        x, y = positions[node]
        node_x.append(x)
        node_y.append(y)

        if node == "Repository":
            node_text.append("Repository")
            node_size.append(28)
        else:
            contribution_count = graph.nodes[node].get("contributions", 1)
            node_text.append(f"{node} ({contribution_count})")
            node_size.append(10 + min(contribution_count / 8.0, 22))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            hoverinfo="none",
            line={"width": 1, "color": "rgba(148, 163, 184, 0.55)"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition="top center",
            hoverinfo="text",
            marker={
                "size": node_size,
                "color": "#38bdf8",
                "line": {"width": 1, "color": "#0f172a"},
                "opacity": 0.9,
            },
        )
    )
    fig.update_layout(
        **_base_layout("2) Contributor Network Graph", height=350),
        xaxis={"visible": False},
        yaxis={"visible": False},
        showlegend=False,
    )
    return fig


def _build_debt_heatmap(analysis_data: Dict[str, Any]) -> go.Figure:
    ai = analysis_data.get("ai_analysis", {})
    debt = ai.get("technical_debt", {})
    total_hours = max(int(debt.get("estimated_hours", 120)), 1)
    areas = debt.get("top_debt_areas", [])

    if not isinstance(areas, list) or len(areas) == 0:
        areas = ["core", "api", "testing", "docs", "ci"]

    areas = [str(item)[:30] for item in areas[:6]]
    weights = [max(1.0, (len(areas) - idx) * 1.2) for idx in range(len(areas))]
    weight_sum = sum(weights)
    values = [round((weight / weight_sum) * total_hours, 1) for weight in weights]

    fig = go.Figure(
        data=go.Heatmap(
            z=[values],
            x=areas,
            y=["Estimated Debt Hours"],
            colorscale="YlOrRd",
            hovertemplate="Area: %{x}<br>Debt: %{z}h<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout("3) Technical Debt Heatmap"))
    return fig


def _build_language_pie(analysis_data: Dict[str, Any]) -> go.Figure:
    repo_data = analysis_data.get("repository_data", {})
    languages = repo_data.get("languages", {})

    if not isinstance(languages, dict) or len(languages) == 0:
        languages = {"Unknown": 1}

    labels = list(languages.keys())
    values = list(languages.values())

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.45,
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(**_base_layout("4) Language Distribution Pie Chart"), showlegend=False)
    return fig


def _build_issue_age_timeline(analysis_data: Dict[str, Any]) -> go.Figure:
    repo_data = analysis_data.get("repository_data", {})
    open_issues = max(int(repo_data.get("open_issues", 0)), 0)

    # Estimated issue age distribution when detailed issue timestamps are unavailable.
    buckets = ["0-7d", "8-30d", "31-90d", "90d+"]
    values = [
        int(open_issues * 0.25),
        int(open_issues * 0.35),
        int(open_issues * 0.25),
        max(open_issues - int(open_issues * 0.25) - int(open_issues * 0.35) - int(open_issues * 0.25), 0),
    ]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=buckets,
                y=values,
                mode="lines+markers",
                line={"color": "#22d3ee", "width": 3},
                marker={"size": 9, "color": "#67e8f9"},
                fill="tozeroy",
                fillcolor="rgba(34, 211, 238, 0.18)",
                name="Open issues",
            )
        ]
    )
    fig.update_layout(**_base_layout("5) Issue Age Timeline"), yaxis_title="Issue Count")
    return fig


def _build_security_risk_matrix(analysis_data: Dict[str, Any]) -> go.Figure:
    ai = analysis_data.get("ai_analysis", {})
    security = ai.get("security_risk", {})
    risk_level = str(security.get("risk_level", "medium")).lower()
    critical_findings = security.get("critical_findings", [])
    finding_count = len(critical_findings) if isinstance(critical_findings, list) else 0

    level_to_xy: Dict[str, Tuple[float, float]] = {
        "low": (2.0, 2.0),
        "medium": (4.5, 5.0),
        "high": (7.0, 7.5),
        "critical": (8.8, 9.2),
    }
    x_value, y_value = level_to_xy.get(risk_level, (4.5, 5.0))
    y_value = min(10.0, y_value + min(finding_count * 0.2, 1.5))

    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=5, y1=5, fillcolor="rgba(34, 197, 94, 0.15)", line={"width": 0})
    fig.add_shape(type="rect", x0=5, y0=0, x1=10, y1=5, fillcolor="rgba(250, 204, 21, 0.15)", line={"width": 0})
    fig.add_shape(type="rect", x0=0, y0=5, x1=10, y1=10, fillcolor="rgba(239, 68, 68, 0.12)", line={"width": 0})
    fig.add_trace(
        go.Scatter(
            x=[x_value],
            y=[y_value],
            mode="markers+text",
            marker={"size": 18, "color": "#f97316"},
            text=[risk_level.title()],
            textposition="top center",
            hovertemplate="Risk level: %{text}<br>Likelihood: %{x:.1f}<br>Impact: %{y:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout("6) Security Risk Matrix"),
        xaxis={"title": "Likelihood", "range": [0, 10], "dtick": 2},
        yaxis={"title": "Impact", "range": [0, 10], "dtick": 2},
        showlegend=False,
    )
    return fig


def _build_dependency_risk_bars(analysis_data: Dict[str, Any]) -> go.Figure:
    ai = analysis_data.get("ai_analysis", {})
    security = ai.get("security_risk", {})
    debt = ai.get("technical_debt", {})

    security_score = int(security.get("security_score", 65))
    debt_hours = int(debt.get("estimated_hours", 120))

    categories = [
        "Outdated Dependencies",
        "Vulnerability Exposure",
        "Patch Lag Risk",
        "License Compatibility",
        "Build Supply Chain",
    ]

    risk_values = [
        min(100, max(5, int(100 - security_score * 0.6))),
        min(100, max(5, int(100 - security_score * 0.75))),
        min(100, max(5, int(debt_hours / 3))),
        min(100, max(5, int((100 - security_score) * 0.7))),
        min(100, max(5, int((100 - security_score) * 0.55 + debt_hours / 8))),
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=categories,
                y=risk_values,
                marker={
                    "color": risk_values,
                    "colorscale": "OrRd",
                    "cmin": 0,
                    "cmax": 100,
                },
                hovertemplate="%{x}<br>Risk: %{y}<extra></extra>",
            )
        ]
    )
    fig.update_layout(**_base_layout("7) Dependency Risk Bar Chart"), yaxis={"title": "Risk Score (0-100)"})
    return fig


def build_all_charts(analysis_data: Dict[str, Any]) -> Dict[str, go.Figure]:
    return {
        "radar": _build_radar_chart(analysis_data),
        "network": _build_contributor_network(analysis_data),
        "debt_heatmap": _build_debt_heatmap(analysis_data),
        "language_pie": _build_language_pie(analysis_data),
        "issue_timeline": _build_issue_age_timeline(analysis_data),
        "security_matrix": _build_security_risk_matrix(analysis_data),
        "dependency_risk": _build_dependency_risk_bars(analysis_data),
    }
