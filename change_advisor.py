"""
Change Advisor Module
Generates codebase-aware implementation plans from natural language change requests.
Uses existing analysis data to ground AI responses in the real state of the codebase.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any

from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
MAX_FILES_IN_CONTEXT = 15


def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=api_key, timeout=60.0, max_retries=1)


def _call_with_retry(func, *args, **kwargs):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_transient = any(k in error_str for k in [
                'rate_limit', 'rate limit', 'timeout', 'timed out',
                'connection', 'server_error', '503', '502', '429'
            ])
            if is_transient and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Transient error (attempt {attempt + 1}/{MAX_RETRIES}), "
                    f"retrying in {delay}s: {str(e)[:100]}")
                time.sleep(delay)
            else:
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry failed with no error captured")


def _build_codebase_context(analysis, code_files) -> str:
    """Construct a rich textual summary of the codebase for the AI prompt."""
    lines = []

    summary = analysis.analysis_results.get('_summary', {}) if analysis.analysis_results else {}
    lines.append(f"Project: {analysis.name}")
    if analysis.description:
        lines.append(f"Description: {analysis.description}")
    lines.append(f"Source: {analysis.source_type}")
    if analysis.source_url:
        lines.append(f"Repository: {analysis.source_url}")
    lines.append(f"Total files: {summary.get('total_files', len(code_files))}")
    langs = summary.get('languages', [])
    if langs:
        lines.append(f"Languages: {', '.join(langs)}")
    lines.append(f"Total functions: {summary.get('total_functions', 0)}")
    lines.append(f"Total classes: {summary.get('total_classes', 0)}")
    lines.append(f"Total API endpoints: {summary.get('total_apis', 0)}")
    lines.append("")

    comp_analysis = None
    if analysis.ai_insights and isinstance(analysis.ai_insights, dict):
        comp_analysis = analysis.ai_insights.get('comprehensive_analysis')
        if isinstance(comp_analysis, dict):
            comp_inner = comp_analysis.get('comprehensive_analysis', comp_analysis)
            if isinstance(comp_inner, dict):
                arch = comp_inner.get('architecture_assessment', '')
                if arch:
                    lines.append(f"Architecture: {arch}")
                proj_type = comp_inner.get('project_type', '')
                if proj_type:
                    lines.append(f"Project type: {proj_type}")
                tech_stack = comp_inner.get('technology_stack', [])
                if tech_stack:
                    lines.append(f"Tech stack: {', '.join(tech_stack) if isinstance(tech_stack, list) else tech_stack}")
                maturity = comp_inner.get('maturity_level', '')
                if maturity:
                    lines.append(f"Maturity: {maturity}")
                lines.append("")

    lines.append("FILES AND STRUCTURE:")
    files_to_include = list(code_files)[:MAX_FILES_IN_CONTEXT]
    for cf in files_to_include:
        file_line = f"  {cf.filename} [{cf.language}]"
        details = []
        if cf.functions:
            func_names = [f.get('name', '') for f in cf.functions if isinstance(f, dict)][:6]
            if func_names:
                details.append(f"functions: {', '.join(func_names)}")
        if cf.classes:
            class_names = [c.get('name', '') for c in cf.classes if isinstance(c, dict)][:4]
            if class_names:
                details.append(f"classes: {', '.join(class_names)}")
        if cf.apis:
            api_endpoints = [a.get('endpoint', a.get('route', '')) for a in cf.apis if isinstance(a, dict)][:4]
            api_endpoints = [e for e in api_endpoints if e]
            if api_endpoints:
                details.append(f"endpoints: {', '.join(api_endpoints)}")
        if details:
            file_line += f" — {'; '.join(details)}"
        lines.append(file_line)

        if cf.quality_metrics and isinstance(cf.quality_metrics, dict):
            smells = cf.quality_metrics.get('code_smells', [])
            if smells and isinstance(smells, list) and len(smells) > 0:
                smell_strs = [s if isinstance(s, str) else str(s) for s in smells[:3]]
                lines.append(f"    known issues: {', '.join(smell_strs)}")

    if len(code_files) > MAX_FILES_IN_CONTEXT:
        lines.append(f"  ... and {len(code_files) - MAX_FILES_IN_CONTEXT} more files")

    lines.append("")

    all_imports = set()
    for cf in code_files:
        if cf.imports and isinstance(cf.imports, list):
            for imp in cf.imports:
                if isinstance(imp, dict):
                    mod = imp.get('module', '')
                    if mod:
                        all_imports.add(mod)
    if all_imports:
        sorted_imports = sorted(all_imports)[:20]
        lines.append(f"KEY DEPENDENCIES: {', '.join(sorted_imports)}")

    return '\n'.join(lines)


def generate_change_plan(description: str, analysis, code_files) -> Dict[str, Any]:
    """
    Generate a codebase-aware implementation plan for a described change.

    Args:
        description: Natural language description of the desired change
        analysis: Analysis model instance
        code_files: List of CodeFile model instances

    Returns:
        Structured dict with the implementation plan
    """
    client = _get_client()
    codebase_context = _build_codebase_context(analysis, code_files)

    system_prompt = (
        "You are a senior software architect and business analyst. "
        "You receive a description of a real codebase and a desired change the team wants to make. "
        "Your job is to produce a concrete, actionable implementation plan grounded in the actual codebase. "
        "You must also produce a business risk assessment — written entirely in plain business language, "
        "with no technical jargon — that explains to non-technical stakeholders what could go wrong if "
        "this change is poorly executed, which business processes or end-users could be affected, and what "
        "the financial or operational consequences might be. "
        "Always respond with valid JSON."
    )

    user_prompt = f"""
CODEBASE CONTEXT:
{codebase_context}

REQUESTED CHANGE:
{description}

Produce a detailed implementation plan for this change. Respond with a JSON object matching this exact structure:

ESTIMATION GUIDANCE — base your estimated_hours on the actual scope:
- A simple config change or single-file edit: 2–6 hours
- A small cross-cutting change (2–4 files, no new architecture): 8–20 hours
- A medium feature (new module, 5–10 files affected, some integration work): 20–60 hours
- A large feature or architectural change (new services, schema migrations, many files): 60–200+ hours
- Factor in the number of affected_files, new_files, dependencies, and implementation_steps you identify below.
- Do NOT default to 8. Calculate a realistic figure based on the actual work described.

{{
    "summary": "A clear 2-3 sentence plain English summary of what this change involves and why it matters",
    "complexity": "Low|Medium|High",
    "estimated_hours": <integer — your calculated estimate based on the guidance above, NOT a default value>,
    "implementation_steps": [
        "Step 1: ...",
        "Step 2: ..."
    ],
    "affected_files": [
        {{
            "filename": "path/to/file.py",
            "change_description": "What specifically needs to change in this file and why"
        }}
    ],
    "new_files": [
        {{
            "filename": "path/to/new_file.py",
            "purpose": "Why this file needs to be created and what it will contain"
        }}
    ],
    "dependencies": [
        {{
            "action": "add|remove|upgrade",
            "package": "package-name",
            "reason": "Why this dependency change is needed"
        }}
    ],
    "business_risk_assessment": "A paragraph written in plain business language (no technical jargon) that explains: what could go wrong if this change is executed poorly; which business processes, customers, or revenue streams could be disrupted; what the financial or operational consequences might be; and how long any disruption could last. This should be understandable by a CEO or CFO with no software background.",
    "risk_level": "Low|Medium|High",
    "risks": [
        "Specific risk 1 written in business terms",
        "Specific risk 2 written in business terms"
    ]
}}

Be specific about file names using the actual files from the codebase context. If a file isn't in the codebase, explain why a new one is needed.
"""

    def _make_api_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=2500
        )

    response = _call_with_retry(_make_api_call)
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty response from AI model")

    result = json.loads(content)

    required_keys = [
        'summary', 'complexity', 'estimated_hours', 'implementation_steps',
        'affected_files', 'new_files', 'dependencies',
        'business_risk_assessment', 'risk_level', 'risks'
    ]
    for key in required_keys:
        if key not in result:
            result[key] = [] if key in ('implementation_steps', 'affected_files', 'new_files', 'dependencies', 'risks') else ''

    if result.get('complexity') not in ('Low', 'Medium', 'High'):
        result['complexity'] = 'Medium'
    if result.get('risk_level') not in ('Low', 'Medium', 'High'):
        result['risk_level'] = 'Medium'

    try:
        hours_raw = result.get('estimated_hours')
        result['estimated_hours'] = int(float(str(hours_raw))) if hours_raw not in (None, '', 'null') else None
    except (ValueError, TypeError):
        result['estimated_hours'] = None

    return result
