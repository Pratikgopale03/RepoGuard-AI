import os
import re
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException, RateLimitExceededException


class AnalysisError(Exception):
    """Raised when repository analysis cannot be completed."""


load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.groq.com/openai/v1/chat/completions")
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    os.getenv("GROQ_MODEL", os.getenv("GROK_MODEL", "llama-3.3-70b-versatile")),
)

AI_TASKS: Dict[str, str] = {
    "repository_health_score": (
        "Compute overall repository health score (0-100) using weighted rubric: "
        "maintainability 25%, security 25%, contributor resilience 20%, activity 15%, documentation 15%. "
        "Use only given repository context. No invented facts. "
        "Return JSON with keys: score (int), confidence (0-1 float), rationale (string), "
        "positives (array of strings), risks (array of strings), assumptions (array of strings), "
        "evidence_used (array of strings). Lower confidence if critical data is missing."
    ),
    "bus_factor": (
        "Estimate bus factor resilience score (0-100, higher is better) using contributor concentration. "
        "Scoring guide: top contributor share >60% => 10-35, 40-60% => 30-55, 25-40% => 50-75, <25% => 70-95. "
        "Use top contributors and recent activity signals only. "
        "Return JSON keys: bus_factor_percent (int), concentration_risk (low|medium|high), "
        "key_person_dependency (array of contributor logins), rationale (string), assumptions (array of strings), "
        "evidence_used (array of strings)."
    ),
    "technical_debt": (
        "Estimate technical debt from repo scale and maintenance signals. "
        "Scoring hints: stale activity + high issue volume + uneven ownership increases debt. "
        "Return JSON keys: estimated_hours (int), debt_level (low|medium|high|critical), "
        "top_debt_areas (array of strings), rationale (string), assumptions (array of strings), "
        "evidence_used (array of strings)."
    ),
    "security_risk": (
        "Assess security posture conservatively from available repository metadata. "
        "Penalize missing maintenance signals, high stale issue pressure, and low contributor resilience. "
        "Return JSON keys: security_score (int 0-100, higher safer), risk_level (low|medium|high|critical), "
        "critical_findings (array of strings), rationale (string), assumptions (array of strings), "
        "evidence_used (array of strings)."
    ),
    "code_maintainability": (
        "Assess maintainability based on language spread, issue pressure, contributor distribution, and recent activity. "
        "Return JSON keys: maintainability_score (int 0-100), hotspots (array of strings), rationale (string), "
        "assumptions (array of strings), evidence_used (array of strings)."
    ),
    "documentation_quality": (
        "Assess documentation quality from observable metadata only. If docs are not directly observable, "
        "state uncertainty and reduce confidence in rationale. "
        "Return JSON keys: documentation_score (int 0-100), gaps (array of strings), rationale (string), "
        "assumptions (array of strings), evidence_used (array of strings)."
    ),
    "contributor_distribution": (
        "Analyze contributor distribution from top contributors list. "
        "Compute top_contributor_share_percent as the estimated share of top contributor contribution against top-10 sum. "
        "Return JSON keys: distribution_score (int 0-100), top_contributor_share_percent (int), "
        "long_tail_strength (low|medium|high), rationale (string), assumptions (array of strings), "
        "evidence_used (array of strings)."
    ),
    "refactoring_priorities": (
        "Generate risk-weighted refactoring priorities based only on provided repository context. "
        "Prioritize high-impact and high-risk items first. "
        "Return JSON keys: priorities (array of objects with keys title, area, effort_hours, risk, impact, recommendation). "
        "Provide exactly 5 items, sorted by priority descending, with realistic effort hours."
    ),
    "project_summary": (
        "Study the provided repository context and generate a clear project intelligence summary. "
        "Do not invent facts not present in context. "
        "Return JSON keys: short (string, <= 220 chars), detailed (string, 2-5 sentences), "
        "key_features (array of 4-8 strings), patterns (array of architecture/code patterns), "
        "architecture (string), api_overview (string)."
    ),
}


def _clip_int(value: Any, min_value: int, max_value: int, default: int) -> int:
    try:
        value_int = int(round(float(value)))
    except Exception:
        return default
    return max(min_value, min(max_value, value_int))


def _clip_float(value: Any, min_value: float, max_value: float, default: float) -> float:
    try:
        value_float = float(value)
    except Exception:
        return default
    return max(min_value, min(max_value, value_float))


def _repair_json_quotes(raw_json: str) -> str:
    # Fix trailing commas
    raw_json = re.sub(r",\s*([\]}])", r"\1", raw_json)
    
    chars = list(raw_json)
    in_string = False
    escaped = False
    
    i = 0
    while i < len(chars):
        char = chars[i]
        
        if char == '\\':
            escaped = not escaped
            i += 1
            continue
            
        if char == '"' and not escaped:
            if not in_string:
                in_string = True
            else:
                is_end_of_string = False
                j = i + 1
                while j < len(chars) and chars[j].isspace():
                    j += 1
                if j < len(chars) and chars[j] in (':', ',', '}', ']'):
                    is_end_of_string = True
                
                if is_end_of_string:
                    in_string = False
                else:
                    chars.insert(i, '\\')
                    i += 1
        elif char == '\n' and in_string:
            chars[i] = '\\n'
        elif char == '\t' and in_string:
            chars[i] = '\\t'
        else:
            escaped = False
            
        i += 1
        
    return "".join(chars)


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise AnalysisError("Empty AI response.")

    # Remove markdown code block markers if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Fast path if the model already returned valid JSON only.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise AnalysisError("AI response did not contain JSON object.")

    matched_json = match.group(0)
    try:
        parsed = json.loads(matched_json)
    except json.JSONDecodeError:
        try:
            repaired = _repair_json_quotes(matched_json)
            parsed = json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Malformed AI JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise AnalysisError("AI response JSON must be an object.")
    return parsed


def _get_llm_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        api_key = os.getenv("GROK_API_KEY", "").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AnalysisError("Missing LLM API key. Set GROQ_API_KEY (preferred) or GROK_API_KEY.")
    return api_key


def _make_ai_context(repo_data: Dict[str, Any]) -> Dict[str, Any]:
    contributors = repo_data.get("top_20_contributors", [])
    contributors_trimmed = [
        {"login": c.get("login"), "contributions": c.get("contributions", 0)} for c in contributors[:10]
    ]

    commit_activity = repo_data.get("commit_activity", [])
    last_12_weeks = commit_activity[-12:] if len(commit_activity) > 12 else commit_activity
    commits_last_12_weeks = sum(int(item.get("total_commits", 0)) for item in last_12_weeks)

    branches = repo_data.get("branches", [])
    branch_names = [b.get("name") for b in branches[:20] if isinstance(b, dict) and b.get("name")]

    endpoints = repo_data.get("api_endpoints", [])
    endpoint_preview = [
        {
            "method": e.get("method"),
            "path": e.get("path"),
            "file": e.get("file"),
        }
        for e in endpoints[:20]
        if isinstance(e, dict)
    ]

    return {
        "full_name": repo_data.get("full_name"),
        "description": repo_data.get("description"),
        "visibility": repo_data.get("visibility"),
        "stars": repo_data.get("stars"),
        "forks": repo_data.get("forks_count"),
        "watchers": repo_data.get("watchers"),
        "open_issues": repo_data.get("open_issues"),
        "open_pull_requests": repo_data.get("open_pull_requests"),
        "languages": repo_data.get("languages"),
        "license": repo_data.get("license"),
        "last_commit_date": repo_data.get("last_commit_date"),
        "contributors_total": repo_data.get("contributors"),
        "top_contributors": contributors_trimmed,
        "commits_last_12_weeks": commits_last_12_weeks,
        "default_branch": repo_data.get("default_branch"),
        "branch_names": branch_names,
        "api_endpoints_preview": endpoint_preview,
        "repo_tree": repo_data.get("repo_tree"),
    }


def _grok_chat_json(prompt_key: str, prompt_instruction: str, ai_context: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _get_llm_api_key()

    system_prompt = (
        "You are an expert repository auditor. Return strict JSON only, without markdown, without code fences. "
        "Use only the provided context. Do not invent metrics, files, tools, or vulnerabilities. "
        "If evidence is weak, include explicit assumptions and lower confidence. "
        "Keep scores internally consistent across tasks."
    )
    user_prompt = (
        f"Task: {prompt_key}\n"
        f"Instruction: {prompt_instruction}\n"
        "Repository context JSON:\n"
        f"{json.dumps(ai_context, separators=(',', ':'), ensure_ascii=True)}"
    )

    # refactoring_priorities returns a large array — give it more room to avoid truncation.
    max_tokens = 2000 if prompt_key == "refactoring_priorities" else 600

    payload = {
        "model": LLM_MODEL,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "12"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "4"))
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=timeout_seconds)
            if response.status_code == 429:
                # Respect Retry-After header if provided, else use exponential backoff
                retry_after = response.headers.get("Retry-After") or response.headers.get("x-ratelimit-reset-requests")
                if retry_after and attempt < max_retries:
                    try:
                        wait = float(retry_after)
                    except (ValueError, TypeError):
                        wait = min(60.0, 5.0 * (2 ** attempt))
                    time.sleep(min(wait, 60.0))
                    continue
                elif attempt < max_retries:
                    time.sleep(min(60.0, 5.0 * (2 ** attempt)))
                    continue
                else:
                    raise requests.HTTPError("429 Too Many Requests", response=response)
            response.raise_for_status()
            response_json = response.json()

            choices = response_json.get("choices", [])
            if not choices:
                raise AnalysisError("AI response missing choices.")

            content = choices[0].get("message", {}).get("content", "")
            return _extract_json_object(content)
        except (requests.RequestException, ValueError, AnalysisError) as exc:
            last_error = exc
            if attempt < max_retries:
                sleep_seconds = min(30.0, 2.0 * (2 ** attempt))
                time.sleep(sleep_seconds)
                continue

    raise AnalysisError(f"LLM request failed for {prompt_key}: {last_error}")


def _default_ai_section(task_key: str) -> Dict[str, Any]:
    defaults: Dict[str, Dict[str, Any]] = {
        "repository_health_score": {
            "score": 60,
            "confidence": 0.35,
            "rationale": "Fallback estimate due to unavailable AI output.",
            "positives": [],
            "risks": ["AI response unavailable"],
        },
        "bus_factor": {
            "bus_factor_percent": 50,
            "concentration_risk": "medium",
            "key_person_dependency": [],
            "rationale": "Fallback estimate due to unavailable AI output.",
        },
        "technical_debt": {
            "estimated_hours": 120,
            "debt_level": "medium",
            "top_debt_areas": [],
            "rationale": "Fallback estimate due to unavailable AI output.",
        },
        "security_risk": {
            "security_score": 65,
            "risk_level": "medium",
            "critical_findings": [],
            "rationale": "Fallback estimate due to unavailable AI output.",
        },
        "code_maintainability": {
            "maintainability_score": 62,
            "hotspots": [],
            "rationale": "Fallback estimate due to unavailable AI output.",
        },
        "documentation_quality": {
            "documentation_score": 58,
            "gaps": [],
            "rationale": "Fallback estimate due to unavailable AI output.",
        },
        "contributor_distribution": {
            "distribution_score": 55,
            "top_contributor_share_percent": 35,
            "long_tail_strength": "medium",
            "rationale": "Fallback estimate due to unavailable AI output.",
        },
        "refactoring_priorities": {
            "priorities": [
                {
                    "title": "Reduce module complexity",
                    "area": "core",
                    "effort_hours": 16,
                    "risk": "medium",
                    "impact": "high",
                    "recommendation": "Break large modules into smaller focused units.",
                }
            ],
        },
        "project_summary": {
            "short": "Repository intelligence summary generated from repository metadata.",
            "detailed": "This summary was generated using repository metadata because AI output was unavailable for this run.",
            "key_features": ["Metadata-based fallback summary"],
            "patterns": [],
            "architecture": "Unknown",
            "api_overview": "API overview not available from AI response",
        },
    }
    return defaults.get(task_key, {"error": "No default available"})


def _normalize_ai_section(task_key: str, raw_section: Dict[str, Any]) -> Dict[str, Any]:
    section = dict(raw_section) if isinstance(raw_section, dict) else {}

    assumptions = section.get("assumptions", [])
    if not isinstance(assumptions, list):
        assumptions = []
    evidence_used = section.get("evidence_used", [])
    if not isinstance(evidence_used, list):
        evidence_used = []

    if task_key == "repository_health_score":
        return {
            "score": _clip_int(section.get("score"), 0, 100, 60),
            "confidence": _clip_float(section.get("confidence"), 0.0, 1.0, 0.5),
            "rationale": str(section.get("rationale", ""))[:1200],
            "positives": section.get("positives", []) if isinstance(section.get("positives", []), list) else [],
            "risks": section.get("risks", []) if isinstance(section.get("risks", []), list) else [],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "bus_factor":
        return {
            "bus_factor_percent": _clip_int(section.get("bus_factor_percent"), 0, 100, 50),
            "concentration_risk": str(section.get("concentration_risk", "medium")).lower(),
            "key_person_dependency": section.get("key_person_dependency", []) if isinstance(section.get("key_person_dependency", []), list) else [],
            "rationale": str(section.get("rationale", ""))[:1200],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "technical_debt":
        return {
            "estimated_hours": _clip_int(section.get("estimated_hours"), 0, 20000, 120),
            "debt_level": str(section.get("debt_level", "medium")).lower(),
            "top_debt_areas": section.get("top_debt_areas", []) if isinstance(section.get("top_debt_areas", []), list) else [],
            "rationale": str(section.get("rationale", ""))[:1200],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "security_risk":
        return {
            "security_score": _clip_int(section.get("security_score"), 0, 100, 65),
            "risk_level": str(section.get("risk_level", "medium")).lower(),
            "critical_findings": section.get("critical_findings", []) if isinstance(section.get("critical_findings", []), list) else [],
            "rationale": str(section.get("rationale", ""))[:1200],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "code_maintainability":
        return {
            "maintainability_score": _clip_int(section.get("maintainability_score"), 0, 100, 62),
            "hotspots": section.get("hotspots", []) if isinstance(section.get("hotspots", []), list) else [],
            "rationale": str(section.get("rationale", ""))[:1200],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "documentation_quality":
        return {
            "documentation_score": _clip_int(section.get("documentation_score"), 0, 100, 58),
            "gaps": section.get("gaps", []) if isinstance(section.get("gaps", []), list) else [],
            "rationale": str(section.get("rationale", ""))[:1200],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "contributor_distribution":
        return {
            "distribution_score": _clip_int(section.get("distribution_score"), 0, 100, 55),
            "top_contributor_share_percent": _clip_int(section.get("top_contributor_share_percent"), 0, 100, 35),
            "long_tail_strength": str(section.get("long_tail_strength", "medium")).lower(),
            "rationale": str(section.get("rationale", ""))[:1200],
            "assumptions": assumptions,
            "evidence_used": evidence_used,
        }

    if task_key == "refactoring_priorities":
        priorities = section.get("priorities", [])
        if not isinstance(priorities, list):
            priorities = []

        normalized_items: List[Dict[str, Any]] = []
        for item in priorities[:25]:
            if not isinstance(item, dict):
                continue
            normalized_items.append(
                {
                    "title": str(item.get("title", "Untitled priority"))[:180],
                    "area": str(item.get("area", "unknown"))[:120],
                    "effort_hours": _clip_int(item.get("effort_hours"), 1, 5000, 8),
                    "risk": str(item.get("risk", "medium")).lower(),
                    "impact": str(item.get("impact", "medium")).lower(),
                    "recommendation": str(item.get("recommendation", ""))[:500],
                }
            )

        if not normalized_items:
            return _default_ai_section("refactoring_priorities")
        return {"priorities": normalized_items}

    if task_key == "project_summary":
        key_features = section.get("key_features", [])
        if not isinstance(key_features, list):
            key_features = []

        patterns = section.get("patterns", [])
        if not isinstance(patterns, list):
            patterns = []

        return {
            "short": str(section.get("short", "Repository summary unavailable."))[:240],
            "detailed": str(section.get("detailed", ""))[:2200],
            "key_features": [str(x)[:220] for x in key_features[:10]],
            "patterns": [str(x)[:140] for x in patterns[:12]],
            "architecture": str(section.get("architecture", ""))[:400],
            "api_overview": str(section.get("api_overview", ""))[:800],
        }

    return section


def _project_summary_fallback(repo_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a useful local summary when AI summary generation fails."""
    name = str(repo_data.get("full_name") or "Repository")
    desc = str(repo_data.get("description") or "")
    visibility = str(repo_data.get("visibility") or "unknown")

    languages = repo_data.get("languages") or {}
    if isinstance(languages, dict) and languages:
        top_langs = list(languages.keys())[:4]
    else:
        top_langs = []

    stars = int(repo_data.get("stars") or 0)
    forks = int(repo_data.get("forks_count") or 0)
    open_issues = int(repo_data.get("open_issues") or 0)
    open_prs = int(repo_data.get("open_pull_requests") or 0)
    contributors = int(repo_data.get("contributors") or 0)
    endpoints = repo_data.get("api_endpoints") or []
    endpoint_count = len(endpoints) if isinstance(endpoints, list) else 0

    lang_text = ", ".join(top_langs) if top_langs else "unknown stack"
    short = desc[:220] if desc else f"{name} is a {visibility} project using {lang_text}."

    detailed = (
        f"{name} appears to be a {visibility} repository with {stars} stars, {forks} forks, "
        f"{open_issues} open issues, and {open_prs} open pull requests. "
        f"The dominant technology stack includes {lang_text}. "
        f"Contributor count is {contributors}, indicating {'distributed' if contributors >= 5 else 'limited'} ownership. "
        f"Detected API endpoints: {endpoint_count}."
    )

    key_features: List[str] = [
        f"Visibility: {visibility}",
        f"Tech stack: {lang_text}",
        f"Repo activity indicators: {open_issues} open issues, {open_prs} open PRs",
        f"Contributors: {contributors}",
    ]
    if endpoint_count > 0:
        key_features.append(f"Detected {endpoint_count} API endpoint declarations")

    patterns: List[str] = []
    if endpoint_count > 0:
        methods = sorted({str(e.get("method", "")).upper() for e in endpoints if isinstance(e, dict)})
        if methods:
            patterns.append(f"HTTP routing ({', '.join([m for m in methods if m][:6])})")
    if any("blade" in l.lower() for l in top_langs):
        patterns.append("Server-side rendered templates")
    if any(l.lower() in {"javascript", "typescript"} for l in top_langs):
        patterns.append("Frontend scripting")

    api_overview = (
        f"Detected {endpoint_count} endpoint declarations in repository route/controller files."
        if endpoint_count > 0
        else "No API endpoint declarations detected with current static patterns."
    )

    return {
        "short": short,
        "detailed": detailed[:2200],
        "key_features": key_features[:10],
        "patterns": patterns[:12],
        "architecture": "Monorepo or web-service style repository inferred from metadata",
        "api_overview": api_overview,
    }


def _collect_api_endpoints(repo_obj: Any, max_files: int = 15, max_endpoints: int = 120) -> List[Dict[str, Any]]:
    """Best-effort endpoint extraction from common backend route patterns."""
    endpoint_patterns: List[Tuple[re.Pattern, str]] = [
        (re.compile(r'@(?:app|router|bp|blueprint)\.(get|post|put|delete|patch|options|head)\(\s*[\"\']([^\"\']+)[\"\']', re.IGNORECASE), "decorator"),
        (re.compile(r'\b(?:app|router)\.(get|post|put|delete|patch|options|head|all)\(\s*[\"\'`]([^\"\'`]+)[\"\'`]', re.IGNORECASE), "express"),
        (re.compile(r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\(\s*(?:value\s*=\s*)?[\"\']([^\"\']+)[\"\']', re.IGNORECASE), "spring"),
        (re.compile(r'\[(?:Http)(Get|Post|Put|Delete|Patch|Head|Options)\(\s*[\"\']?([^\"\'\)]*)', re.IGNORECASE), "dotnet"),
        (re.compile(r'\b(?:r|router|group)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*[\"\']([^\"\']+)[\"\']'), "gin"),
        (re.compile(r'\bpath\(\s*[\"\']([^\"\']+)[\"\']\s*,'), "django"),
        (re.compile(r'\bRoute::(get|post|put|delete|patch|options|match|any)\(\s*[\"\']([^\"\']+)[\"\']', re.IGNORECASE), "laravel"),
        (re.compile(r'\bRoute::(?:apiResource|resource)\(\s*[\"\']([^\"\']+)[\"\']', re.IGNORECASE), "laravel_resource"),
    ]

    wanted_ext = {".py", ".js", ".ts", ".tsx", ".go", ".java", ".kt", ".cs", ".rb", ".php"}
    route_hint = re.compile(r"(route|router|api|controller|urls?\.py|views?\.py)", re.IGNORECASE)

    results: List[Dict[str, Any]] = []
    seen: set = set()

    try:
        ref = repo_obj.get_git_ref(f"heads/{repo_obj.default_branch}")
        tree = repo_obj.get_git_tree(ref.object.sha, recursive=True)
    except Exception:
        return []

    candidate_paths: List[str] = []
    for item in tree.tree:
        if getattr(item, "type", "") != "blob":
            continue
        path = getattr(item, "path", "")
        if not path:
            continue
        suffix = Path(path).suffix.lower()
        if suffix in wanted_ext and route_hint.search(path):
            candidate_paths.append(path)

    if len(candidate_paths) < max_files:
        for item in tree.tree:
            if len(candidate_paths) >= max_files:
                break
            if getattr(item, "type", "") != "blob":
                continue
            path = getattr(item, "path", "")
            if not path or path in candidate_paths:
                continue
            suffix = Path(path).suffix.lower()
            if suffix in wanted_ext:
                candidate_paths.append(path)

    for path in candidate_paths[:max_files]:
        if len(results) >= max_endpoints:
            break
        try:
            content_obj = repo_obj.get_contents(path, ref=repo_obj.default_branch)
            if isinstance(content_obj, list):
                continue
            raw = content_obj.decoded_content
            if len(raw) > 250_000:
                continue
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            continue

        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            if len(results) >= max_endpoints:
                break
            line_s = line.strip()
            if not line_s:
                continue

            for pattern, kind in endpoint_patterns:
                match = pattern.search(line_s)
                if not match:
                    continue

                method = "ANY"
                route = ""

                if kind == "spring":
                    route = match.group(1)
                    method_hint = line_s.split("Mapping", 1)[0].lstrip("@[")
                    method = method_hint.replace("Request", "ANY").upper()
                elif kind == "django":
                    route = match.group(1)
                    method = "ANY"
                elif kind == "laravel_resource":
                    route = str(match.group(1))
                    method = "RESOURCE"
                else:
                    if match.lastindex and match.lastindex >= 2:
                        method = str(match.group(1)).upper()
                        route = str(match.group(2))
                    elif match.lastindex and match.lastindex >= 1:
                        route = str(match.group(1))

                if not route:
                    continue

                key = (method, route, path)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "method": method,
                        "path": route,
                        "file": path,
                        "line": line_no,
                    }
                )

        # Generic fallback for route files: capture quoted URL-like paths even when framework syntax is custom.
        if route_hint.search(path) and len(results) < max_endpoints:
            generic_path_pattern = re.compile(r'[\"\'](/[^\"\'\s\)]{1,180})[\"\']')
            for line_no, line in enumerate(lines, start=1):
                if len(results) >= max_endpoints:
                    break
                for gmatch in generic_path_pattern.finditer(line):
                    route = gmatch.group(1)
                    if not route or route.startswith("//"):
                        continue
                    key = ("ANY", route, path)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        {
                            "method": "ANY",
                            "path": route,
                            "file": path,
                            "line": line_no,
                        }
                    )

    return results


def run_ai_analysis(repo_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single consolidated LLM query to perform all audit tasks.
    This prevents 429 Too Many Requests rate limits and speeds up the pipeline.
    """
    ai_context = _make_ai_context(repo_data)
    ai_result: Dict[str, Any] = {}
    failed_tasks: Dict[str, str] = {}
    started_at = time.time()

    api_key = _get_llm_api_key()
    system_prompt = (
        "You are an expert repository auditor. Return a single strict JSON object containing all requested audit sections. "
        "Use only the provided context. Do not invent metrics, files, tools, or vulnerabilities. "
        "No markdown formatting, no backticks, no code fences. Return raw JSON only."
    )
    user_prompt = (
        "Analyze the repository context and perform the following audit tasks. "
        "Return a single JSON object where the keys are the task names, and the values are their respective JSON outputs as specified below:\n\n"
        "1. repository_health_score: Compute overall repository health score (0-100) using weighted rubric. Return JSON keys: score (int), confidence (0-1 float), rationale (string), positives (array of strings), risks (array of strings), assumptions (array of strings), evidence_used (array of strings).\n"
        "2. bus_factor: Estimate bus factor resilience score (0-100). Return JSON keys: bus_factor_percent (int), concentration_risk (low|medium|high), key_person_dependency (array of contributor logins), rationale (string), assumptions (array of strings), evidence_used (array of strings).\n"
        "3. technical_debt: Estimate technical debt level and hours. Return JSON keys: estimated_hours (int), debt_level (low|medium|high|critical), top_debt_areas (array of strings), rationale (string), assumptions (array of strings), evidence_used (array of strings).\n"
        "4. security_risk: Assess security posture conservatively. Return JSON keys: security_score (int), risk_level (low|medium|high|critical), critical_findings (array of strings), rationale (string), assumptions (array of strings), evidence_used (array of strings).\n"
        "5. code_maintainability: Assess maintainability. Return JSON keys: maintainability_score (int), hotspots (array of strings), rationale (string), assumptions (array of strings), evidence_used (array of strings).\n"
        "6. documentation_quality: Assess documentation quality. Return JSON keys: documentation_score (int), gaps (array of strings), rationale (string), assumptions (array of strings), evidence_used (array of strings).\n"
        "7. contributor_distribution: Analyze contributor distribution. Return JSON keys: distribution_score (int), top_contributor_share_percent (int), long_tail_strength (low|medium|high), rationale (string), assumptions (array of strings), evidence_used (array of strings).\n"
        "8. refactoring_priorities: Generate exactly 5 risk-weighted refactoring priorities. Return JSON key: priorities (array of objects with keys: title, area, effort_hours, risk, impact, recommendation).\n"
        "9. project_summary: Generate a clear project intelligence summary. Return JSON keys: short (string, <= 220 chars), detailed (string, 2-5 sentences), key_features (array of 4-8 strings), patterns (array of strings), architecture (string), api_overview (string).\n\n"
        "Repository context JSON:\n"
        f"{json.dumps(ai_context, separators=(',', ':'), ensure_ascii=True)}"
    )

    payload = {
        "model": LLM_MODEL,
        "temperature": 0.2,
        "max_tokens": 3000,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "4"))
    last_error: Optional[Exception] = None
    parsed_response: Dict[str, Any] = {}
    success = False

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=timeout_seconds)
            if response.status_code == 429:
                # Read Retry-After header for smart backoff
                retry_after = response.headers.get("Retry-After") or response.headers.get("x-ratelimit-reset-requests")
                if attempt < max_retries:
                    try:
                        wait = float(retry_after) if retry_after else min(60.0, 10.0 * (2 ** attempt))
                    except (ValueError, TypeError):
                        wait = min(60.0, 10.0 * (2 ** attempt))
                    time.sleep(min(wait, 60.0))
                    continue
                else:
                    raise requests.HTTPError("429 Too Many Requests", response=response)
            response.raise_for_status()
            response_json = response.json()

            choices = response_json.get("choices", [])
            if not choices:
                raise AnalysisError("AI response missing choices.")

            content = choices[0].get("message", {}).get("content", "")
            parsed_response = _extract_json_object(content)
            success = True
            break
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                sleep_seconds = min(30.0, 2.0 * (2 ** attempt))
                time.sleep(sleep_seconds)
                continue

    if not success:
        # Consolidated query failed — silently use fallbacks for all tasks
        # (do NOT propagate error strings to the UI — fallback data is already meaningful)
        for task_key in AI_TASKS:
            failed_tasks[task_key] = f"rate_limited"  # internal only, not shown in UI
    else:
        # Extract and normalize each task's section from the combined response
        for task_key in AI_TASKS:
            if task_key in parsed_response:
                try:
                    ai_result[task_key] = _normalize_ai_section(task_key, parsed_response[task_key])
                except Exception as exc:
                    failed_tasks[task_key] = f"normalization_error"
            else:
                failed_tasks[task_key] = "missing_key"

    # Apply defaults/fallbacks for any failed or missing sections
    for task_key in AI_TASKS:
        if task_key not in ai_result:
            if task_key == "project_summary":
                ai_result[task_key] = _project_summary_fallback(repo_data)
            else:
                ai_result[task_key] = _default_ai_section(task_key)

    elapsed_ms = int((time.time() - started_at) * 1000)
    fallback_count = len(failed_tasks)
    ai_result["meta"] = {
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "elapsed_ms": elapsed_ms,
        "target_runtime_seconds": 15,
        "fallback_count": fallback_count,
        "used_fallback": fallback_count > 0,
        # Do NOT expose raw error strings — UI should only see used_fallback flag
        "failed_tasks": {},
    }
    return ai_result


def analyze_repository(repo_url: str) -> Dict[str, Any]:
    """
    Full Phase 2 + Phase 3 pipeline.

    Returns structured JSON:
    - repository_data: fetched from GitHub API
    - ai_analysis: output of 8 LLM prompts with normalized schema
    - summary: dashboard-ready key metrics
    """
    pipeline_started = time.time()
    repository_data = collect_repository_data(repo_url)
    ai_analysis = run_ai_analysis(repository_data)

    summary = {
        "health_score": ai_analysis["repository_health_score"]["score"],
        "bus_factor_percent": ai_analysis["bus_factor"]["bus_factor_percent"],
        "technical_debt_hours": ai_analysis["technical_debt"]["estimated_hours"],
        "security_score": ai_analysis["security_risk"]["security_score"],
        "top_5_refactoring_priorities": ai_analysis["refactoring_priorities"].get("priorities", [])[:5],
    }

    return {
        "repository_data": repository_data,
        "ai_analysis": ai_analysis,
        "summary": summary,
        "runtime": {
            "total_elapsed_ms": int((time.time() - pipeline_started) * 1000),
            "target_seconds": 15,
        },
    }


def _parse_repo_url(repo_url: str) -> Tuple[str, str]:
    """Parse GitHub URL and return owner/repository."""
    cleaned = repo_url.strip()
    if not cleaned:
        raise AnalysisError("GitHub URL is required.")

    if cleaned.startswith("git@github.com:"):
        # Handles git@github.com:owner/repo.git
        cleaned = cleaned.replace("git@github.com:", "https://github.com/")

    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    if "github.com" not in parsed.netloc.lower():
        raise AnalysisError("Please provide a valid GitHub repository URL.")

    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise AnalysisError("Repository URL format must be: https://github.com/owner/repo")

    owner = parts[0]
    repo = parts[1]
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(r"^[A-Za-z0-9_.-]+$", repo):
        raise AnalysisError("Repository owner/name contains invalid characters.")

    return owner, repo


def _get_github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise AnalysisError("Missing GITHUB_TOKEN environment variable.")
    return Github(token, per_page=100)


def _safe_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _estimate_pr_count(client: Github, owner: str, repo: str) -> int:
    # Search API gives a reliable pull request count.
    query = f"repo:{owner}/{repo} is:pr is:open"
    return client.search_issues(query=query).totalCount


def _collect_top_contributors(repo_obj: Any, limit: int = 20) -> List[Dict[str, Any]]:
    contributors = []
    for contributor in repo_obj.get_contributors()[:limit]:
        contributors.append(
            {
                "login": contributor.login,
                "contributions": contributor.contributions,
                "type": contributor.type,
            }
        )
    return contributors


def _collect_commit_activity(repo_obj: Any) -> List[Dict[str, Any]]:
    # GitHub stats endpoint may return None while generating. Retry briefly.
    for _ in range(3):
        weekly = repo_obj.get_stats_commit_activity()
        if weekly is not None:
            return [
                {
                    "week_start_unix": item.week,
                    "total_commits": item.total,
                    "days": item.days,
                }
                for item in weekly
            ]
        time.sleep(1.0)

    return []


def _collect_branches(repo_obj: Any, limit: int = 80) -> List[Dict[str, Any]]:
    branches: List[Dict[str, Any]] = []
    try:
        for branch in repo_obj.get_branches()[:limit]:
            branches.append(
                {
                    "name": branch.name,
                    "protected": bool(getattr(branch, "protected", False)),
                    "commit_sha": getattr(branch.commit, "sha", None),
                }
            )
    except Exception:
        return []
    return branches


def _build_repo_tree(entries: List[Tuple[str, str]], max_depth: int = 4, max_entries: int = 300) -> Dict[str, Any]:
    tree: Dict[str, Any] = {"name": "/", "type": "dir", "children": {}}
    count = 0

    for path, entry_type in entries:
        if count >= max_entries:
            break
        parts = [p for p in path.split("/") if p]
        if not parts:
            continue
        count += 1

        node = tree
        for depth, part in enumerate(parts[:max_depth]):
            is_last = depth == min(len(parts), max_depth) - 1
            children = node.setdefault("children", {})
            if part not in children:
                children[part] = {"name": part, "type": "dir", "children": {}}
            node = children[part]
            if is_last and len(parts) > max_depth:
                node.setdefault("children", {})["..."] = {"name": "...", "type": "file"}

        if len(parts) <= max_depth:
            node["type"] = "dir" if entry_type == "tree" else "file"

    return tree


def _collect_repo_tree(repo_obj: Any) -> Dict[str, Any]:
    try:
        ref = repo_obj.get_git_ref(f"heads/{repo_obj.default_branch}")
        tree = repo_obj.get_git_tree(ref.object.sha, recursive=True)
        entries = [(item.path, item.type) for item in tree.tree if hasattr(item, "path") and item.type in ("blob", "tree")]
        return _build_repo_tree(entries)
    except Exception:
        return {"name": "/", "type": "dir", "children": {}}


def collect_repository_data(repo_url: str) -> Dict[str, Any]:
    """
    Collect non-AI repository data used by RepoGuard AI analysis.

    Returns a normalized dictionary that Phase 3 can feed into LLM prompts.
    """
    owner, repo_name = _parse_repo_url(repo_url)

    try:
        gh = _get_github_client()
        repo_obj = gh.get_repo(f"{owner}/{repo_name}")

        top_contributors = _collect_top_contributors(repo_obj, limit=20)
        commit_activity = _collect_commit_activity(repo_obj)
        repo_tree = _collect_repo_tree(repo_obj)
        branches = _collect_branches(repo_obj)
        api_endpoints = _collect_api_endpoints(repo_obj)

        contributor_count = repo_obj.get_contributors().totalCount
        open_issues_count = repo_obj.get_issues(state="open").totalCount
        open_pull_requests_count = _estimate_pr_count(gh, owner, repo_name)

        latest_commit = None
        commits = repo_obj.get_commits()
        if commits.totalCount > 0:
            latest_commit = commits[0].commit.committer.date

        data: Dict[str, Any] = {
            "repo_url": repo_url,
            "full_name": repo_obj.full_name,
            "description": repo_obj.description,
            "visibility": "private" if repo_obj.private else "public",
            "stars": repo_obj.stargazers_count,
            "forks": repo_obj.forks,
            "forks_count": repo_obj.forks_count,
            "watchers": repo_obj.watchers_count,
            "open_issues": open_issues_count,
            "open_pull_requests": open_pull_requests_count,
            "languages": repo_obj.get_languages(),
            "default_branch": repo_obj.default_branch,
            "last_commit_date": _safe_iso(latest_commit),
            "license": repo_obj.license.name if repo_obj.license else None,
            "created_at": _safe_iso(repo_obj.created_at),
            "updated_at": _safe_iso(repo_obj.updated_at),
            "pushed_at": _safe_iso(repo_obj.pushed_at),
            "contributors": contributor_count,
            "top_20_contributors": top_contributors,
            "commit_activity": commit_activity,
            "repo_tree": repo_tree,
            "branches": branches,
            "api_endpoints": api_endpoints,
        }
        return data

    except RateLimitExceededException as exc:
        raise AnalysisError("GitHub API rate limit exceeded. Try again later.") from exc
    except GithubException as exc:
        message = str(exc.data.get("message", "GitHub API request failed.")) if hasattr(exc, "data") and isinstance(exc.data, dict) else str(exc)
        if "Not Found" in message:
            raise AnalysisError("Repository not found or inaccessible.") from exc
        if "Bad credentials" in message:
            raise AnalysisError("Invalid GITHUB_TOKEN credentials.") from exc
        if "Resource not accessible by integration" in message:
            raise AnalysisError("Token does not have access to this repository.") from exc
        raise AnalysisError(f"GitHub API error: {message}") from exc
    except AnalysisError:
        raise
    except Exception as exc:
        raise AnalysisError(f"Unexpected analysis error: {exc}") from exc


if __name__ == "__main__":
    # Quick manual smoke test:
    # export GITHUB_TOKEN=...
    # export GROQ_API_KEY=...
    # export LLM_MODEL=openai/gpt-oss-120b
    # python analyzer.py https://github.com/facebook/react
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <github_repo_url>")
        raise SystemExit(1)

    output = analyze_repository(sys.argv[1])
    print(json.dumps(output, indent=2))
