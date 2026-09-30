import os
import json
import uuid
import logging
import io
import time
import zipfile
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort, make_response, send_file, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from sqlalchemy.exc import OperationalError, DBAPIError
from app import db
from models import Analysis, CodeFile, User, Company, Subscription, CompanyInvite, System, SystemRepo, SystemAnalysis, ChangeRequest
from ai_analyzer import analyze_code, analyze_codebase_with_ai, analyze_files_individually
import change_advisor as change_advisor_module
from github_integration import import_github_repo
from mindmap_processor import generate_mindmap_data
from graph_processor import generate_graph_data
from documentation_generator import generate_documentation_for_analysis, DocumentationGenerator
from analysis_progress import initialize_analysis_events, update_analysis_event, get_analysis_progress

main_bp = Blueprint('main', __name__)


def _can_view_analysis(analysis):
    """Check if the current user may view this analysis.

    Access is granted if any of the following are true:
    1. The user is a platform admin (role == 'admin')
    2. The user owns the analysis
    3. The analysis is shared and the user belongs to the same company
    """
    if current_user.is_admin():
        return True
    if analysis.user_id == current_user.id:
        return True
    if (analysis.is_shared
            and analysis.company_id is not None
            and current_user.company_id is not None
            and analysis.company_id == current_user.company_id):
        return True
    return False


def _compute_health_scores(analysis):
    logger = logging.getLogger(__name__)
    quality_scores = []
    maintainability_scores = []
    complexity_counts = {"low": 0, "medium": 0, "high": 0}
    total_smells = 0
    total_best_practices = 0
    total_security_issues = 0
    file_quality_map = {}

    if not analysis.code_files:
        return {
            "score": 70, "label": "Good", "color": "success",
            "maintainability": 70, "scalability": 70, "testability": 70,
            "file_scores": {}, "total_smells": 0,
            "total_best_practices": 0, "total_security_issues": 0,
        }

    ai_smell_count = None
    ai = getattr(analysis, "ai_insights", None)
    if ai and isinstance(ai, dict):
        file_analyses = ai.get("file_analyses", {})
        if isinstance(file_analyses, dict):
            count = 0
            for _fname, fdata in file_analyses.items():
                if not isinstance(fdata, dict):
                    continue
                inner = fdata.get("analysis", {})
                if not isinstance(inner, dict) or inner.get("status") != "success":
                    continue
                inner_analysis = inner.get("analysis", {})
                if isinstance(inner_analysis, dict):
                    smells = inner_analysis.get("code_smells", [])
                    count += len(smells) if isinstance(smells, list) else 0
            ai_smell_count = count

    for cf in analysis.code_files:
        qm = cf.quality_metrics or {}
        fname = cf.filename

        maint_raw = qm.get("maintainability", None)
        if maint_raw is not None:
            try:
                maintainability_scores.append(float(str(maint_raw).split("/")[0].strip()) * 10)
            except (ValueError, IndexError):
                pass

        comp = str(qm.get("complexity", "")).lower()
        if comp in complexity_counts:
            complexity_counts[comp] += 1

        if ai_smell_count is None:
            smells = qm.get("code_smells", [])
            total_smells += len(smells) if isinstance(smells, list) else 0
        bp = qm.get("best_practices", [])
        total_best_practices += len(bp) if isinstance(bp, list) else 0
        sec = qm.get("security_issues", [])
        total_security_issues += len(sec) if isinstance(sec, list) else 0

        file_score = None
        if hasattr(analysis, 'ai_insights') and analysis.ai_insights:
            ai = analysis.ai_insights
            if isinstance(ai, dict) and ai.get("file_analyses"):
                fa = ai["file_analyses"].get(fname, {})
                inner = fa.get("analysis", {})
                if isinstance(inner, dict):
                    inner_analysis = inner.get("analysis", {})
                    if isinstance(inner_analysis, dict):
                        raw = inner_analysis.get("code_quality_score")
                        if raw is not None:
                            try:
                                file_score = int(float(raw))
                            except (ValueError, TypeError):
                                pass

        if file_score is None and maint_raw is not None:
            try:
                file_score = int(float(str(maint_raw).split("/")[0].strip()) * 10)
            except (ValueError, IndexError):
                pass

        if file_score is not None:
            file_score = max(0, min(100, file_score))
            quality_scores.append(file_score)
            file_quality_map[fname] = file_score
        else:
            file_quality_map[fname] = None

    if ai_smell_count is not None:
        total_smells = ai_smell_count

    logger.debug(f"Health scoring: {len(quality_scores)} AI scores found out of {len(analysis.code_files)} files")
    if quality_scores:
        avg_quality = round(sum(quality_scores) / len(quality_scores))
    else:
        total_files = len(analysis.code_files) if analysis.code_files else 1
        total_funcs = 0
        total_classes = 0
        if analysis.analysis_results and "_summary" in analysis.analysis_results:
            total_funcs = analysis.analysis_results["_summary"].get("total_functions", 0)
            total_classes = analysis.analysis_results["_summary"].get("total_classes", 0)
        ratio = (total_funcs + total_classes) / max(total_files, 1)
        if ratio < 5:
            avg_quality = 90
        elif ratio < 15:
            avg_quality = 78
        elif ratio < 30:
            avg_quality = 65
        else:
            avg_quality = 55

    if avg_quality >= 85:
        health_label = "Excellent"
        health_color = "success"
    elif avg_quality >= 70:
        health_label = "Good"
        health_color = "success"
    elif avg_quality >= 55:
        health_label = "Fair"
        health_color = "warning"
    elif avg_quality >= 40:
        health_label = "Needs Work"
        health_color = "warning"
    else:
        health_label = "Critical"
        health_color = "danger"

    if maintainability_scores:
        maintainability = round(sum(maintainability_scores) / len(maintainability_scores))
    else:
        maintainability = max(40, avg_quality - 5)
    maintainability = max(0, min(100, maintainability))

    total_files = len(analysis.code_files) if analysis.code_files else 1
    has_classes = complexity_counts.get("low", 0) + complexity_counts.get("medium", 0) + complexity_counts.get("high", 0)
    if has_classes > 0:
        low_pct = complexity_counts["low"] / has_classes
        scalability = round(60 + low_pct * 30)
    else:
        scalability = max(45, avg_quality - 10)
    scalability = max(0, min(100, scalability))

    smell_ratio = total_smells / max(total_files, 1)
    if smell_ratio < 1:
        testability = min(90, avg_quality + 5)
    elif smell_ratio < 3:
        testability = max(50, avg_quality - 10)
    else:
        testability = max(35, avg_quality - 20)
    testability = round(max(0, min(100, testability)))

    return {
        "score": avg_quality,
        "label": health_label,
        "color": health_color,
        "maintainability": maintainability,
        "scalability": scalability,
        "testability": testability,
        "file_scores": file_quality_map,
        "total_smells": total_smells,
        "total_best_practices": total_best_practices,
        "total_security_issues": total_security_issues,
    }

SMELL_BUSINESS_MAP = {
    "duplicated code": {
        "risk_category": "Technical Debt",
        "justification": "Duplicated logic increases maintenance costs significantly. When a bug is found, it must be fixed in multiple places, increasing the risk of inconsistent behaviour, longer release cycles, and higher developer costs.",
        "hours_per_instance": 4,
        "resource_type": "Mid-level Developer",
    },
    "long method": {
        "risk_category": "Operational Risk",
        "justification": "Overly complex methods are harder to test and debug, leading to longer development cycles and higher defect rates in production. This directly impacts time-to-market for new features and increases support costs.",
        "hours_per_instance": 3,
        "resource_type": "Mid-level Developer",
    },
    "large class": {
        "risk_category": "Technical Debt",
        "justification": "Large classes violate the single responsibility principle, making the codebase rigid and difficult to extend. This slows down feature delivery and increases the cost of onboarding new developers.",
        "hours_per_instance": 6,
        "resource_type": "Senior Developer",
    },
    "complex conditional": {
        "risk_category": "Operational Risk",
        "justification": "Complex conditionals are a leading source of production defects. They are difficult to test exhaustively, leading to edge-case failures that degrade user experience and increase support ticket volume.",
        "hours_per_instance": 3,
        "resource_type": "Mid-level Developer",
    },
    "hardcoded": {
        "risk_category": "Security & Compliance Risk",
        "justification": "Hardcoded values such as credentials, URLs, or configuration make the application inflexible and pose security risks. A data breach caused by exposed credentials can result in regulatory fines and reputational damage.",
        "hours_per_instance": 2,
        "resource_type": "Mid-level Developer",
    },
    "security": {
        "risk_category": "Security & Compliance Risk",
        "justification": "Security vulnerabilities expose the business to data breaches, regulatory penalties (e.g. GDPR, SOC2), and loss of customer trust. Remediation cost increases exponentially the longer issues remain in production.",
        "hours_per_instance": 5,
        "resource_type": "Senior Developer",
    },
    "missing error handling": {
        "risk_category": "Operational Risk",
        "justification": "Insufficient error handling leads to unexpected application failures that impact end users. This increases support ticket volume, degrades customer satisfaction, and can cause data loss or corruption.",
        "hours_per_instance": 2,
        "resource_type": "Mid-level Developer",
    },
    "naming": {
        "risk_category": "Technical Debt",
        "justification": "Poor naming conventions reduce code readability, slowing down developer onboarding and increasing the time required for code reviews. This has a compounding cost as the team and codebase grow.",
        "hours_per_instance": 1,
        "resource_type": "Junior Developer",
    },
    "unused code": {
        "risk_category": "Technical Debt",
        "justification": "Dead code adds noise to the codebase, confuses developers, and can mask real issues during debugging. Removing it reduces cognitive load, improves build times, and lowers maintenance costs.",
        "hours_per_instance": 1,
        "resource_type": "Junior Developer",
    },
    "tight coupling": {
        "risk_category": "Technical Debt",
        "justification": "Tightly coupled components make it impossible to modify one part of the system without risking breakages elsewhere. This dramatically increases the cost and risk of every change, slowing product evolution.",
        "hours_per_instance": 6,
        "resource_type": "Senior Developer",
    },
    "magic number": {
        "risk_category": "Technical Debt",
        "justification": "Magic numbers make code intent unclear and error-prone during maintenance. Extracting them into named constants improves readability and reduces the chance of introducing regressions during future changes.",
        "hours_per_instance": 1,
        "resource_type": "Junior Developer",
    },
    "performance": {
        "risk_category": "Operational Risk",
        "justification": "Performance issues directly impact user experience and can lead to customer churn. Slow response times reduce conversion rates and can cause cascading failures under load, risking service outages.",
        "hours_per_instance": 4,
        "resource_type": "Senior Developer",
    },
    "default": {
        "risk_category": "Technical Debt",
        "justification": "Code quality issues increase the total cost of ownership of the application. Addressing them proactively reduces future maintenance costs and the risk of production incidents.",
        "hours_per_instance": 3,
        "resource_type": "Mid-level Developer",
    },
}

SEVERITY_MULTIPLIER = {"High": 1.5, "Medium": 1.0, "Low": 0.6}
DEFAULT_RESOURCE_HOURLY_RATES = {
    "Junior Developer": 75,
    "Mid-level Developer": 110,
    "Senior Developer": 160,
    "QA Tester": 90,
    "Product Owner": 130,
    "Project Manager": 120,
}
DEFAULT_HOURS_PER_WEEK = 35
DEFAULT_PARALLEL_STREAMS = 1
DEFAULT_CONTINGENCY_PERCENT = 0

QA_RATIO = 0.30
PM_OVERHEAD_RATIO = 0.10
PO_OVERHEAD_RATIO = 0.08

CURRENCY_MAP = {
    'GBP': {'symbol': '£', 'name': 'British Pound (GBP)'},
    'USD': {'symbol': '$', 'name': 'US Dollar (USD)'},
    'EUR': {'symbol': '€', 'name': 'Euro (EUR)'},
    'AUD': {'symbol': 'A$', 'name': 'Australian Dollar (AUD)'},
    'CAD': {'symbol': 'C$', 'name': 'Canadian Dollar (CAD)'},
    'CHF': {'symbol': 'CHF', 'name': 'Swiss Franc (CHF)'},
    'JPY': {'symbol': '¥', 'name': 'Japanese Yen (JPY)'},
    'INR': {'symbol': '₹', 'name': 'Indian Rupee (INR)'},
    'SEK': {'symbol': 'kr', 'name': 'Swedish Krona (SEK)'},
    'NZD': {'symbol': 'NZ$', 'name': 'New Zealand Dollar (NZD)'},
    'AED': {'symbol': 'د.إ', 'name': 'UAE Dirham (AED)'},
    'SAR': {'symbol': '﷼', 'name': 'Saudi Riyal (SAR)'},
}
DEFAULT_CURRENCY = 'GBP'


def _match_smell_category(smell_text):
    smell_lower = smell_text.lower()
    for key in SMELL_BUSINESS_MAP:
        if key == "default":
            continue
        if key in smell_lower:
            return key
    return "default"


def _generate_remediation_plan(analysis, custom_rates=None, parallel_streams=None, hours_per_week=None, contingency_percent=None):
    rates = dict(DEFAULT_RESOURCE_HOURLY_RATES)
    if custom_rates:
        for role, rate in custom_rates.items():
            if role in rates and rate is not None:
                try:
                    rates[role] = float(rate)
                except (ValueError, TypeError):
                    pass

    hpw = hours_per_week if hours_per_week else DEFAULT_HOURS_PER_WEEK
    streams = parallel_streams if parallel_streams else DEFAULT_PARALLEL_STREAMS
    streams = max(1, min(4, streams))
    contingency = contingency_percent if contingency_percent is not None else DEFAULT_CONTINGENCY_PERCENT
    contingency = max(0, min(50, contingency))

    all_smells = []

    if analysis.ai_insights and isinstance(analysis.ai_insights, dict):
        file_analyses = analysis.ai_insights.get("file_analyses", {})
        for filename, file_data in file_analyses.items():
            if not isinstance(file_data, dict):
                continue
            inner = file_data.get("analysis", {})
            if isinstance(inner, dict) and inner.get("status") == "success":
                analysis_data = inner.get("analysis", {})
                if isinstance(analysis_data, dict):
                    smells = analysis_data.get("code_smells", [])
                    if isinstance(smells, list):
                        for smell in smells:
                            if isinstance(smell, dict):
                                all_smells.append({
                                    "file": filename,
                                    "smell": smell.get("smell", smell.get("name", "Unknown")),
                                    "severity": smell.get("severity", "Medium"),
                                    "description": smell.get("description", smell.get("smell", "")),
                                })

    for cf in (analysis.code_files or []):
        qm = cf.quality_metrics or {}
        sec_issues = qm.get("security_issues", [])
        if isinstance(sec_issues, list):
            for issue in sec_issues:
                if isinstance(issue, dict):
                    all_smells.append({
                        "file": cf.filename,
                        "smell": issue.get("type", issue.get("issue", "Security Issue")),
                        "severity": "High",
                        "description": issue.get("description", issue.get("type", "")),
                    })

    categories = {}
    for smell in all_smells:
        cat_key = _match_smell_category(smell["smell"])
        if cat_key not in categories:
            cat_info = SMELL_BUSINESS_MAP[cat_key]
            categories[cat_key] = {
                "name": cat_key.replace("_", " ").title() if cat_key != "default" else "General Code Quality",
                "risk_category": cat_info["risk_category"],
                "justification": cat_info["justification"],
                "resource_type": cat_info["resource_type"],
                "issues": [],
                "total_hours": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
            }
        sev = smell["severity"]
        multiplier = SEVERITY_MULTIPLIER.get(sev, 1.0)
        hours = round(SMELL_BUSINESS_MAP[cat_key]["hours_per_instance"] * multiplier, 1)
        categories[cat_key]["issues"].append({
            "file": smell["file"],
            "description": smell["description"],
            "severity": sev,
            "estimated_hours": hours,
        })
        categories[cat_key]["total_hours"] += hours
        if sev == "High":
            categories[cat_key]["high_count"] += 1
        elif sev == "Medium":
            categories[cat_key]["medium_count"] += 1
        else:
            categories[cat_key]["low_count"] += 1

    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    for cat in categories.values():
        cat["issues"].sort(key=lambda x: severity_order.get(x["severity"], 3))

    priority_order = {"Security & Compliance Risk": 0, "Operational Risk": 1, "Technical Debt": 2}
    sorted_categories = sorted(
        categories.values(),
        key=lambda c: (priority_order.get(c["risk_category"], 3), -c["high_count"], -c["total_hours"])
    )

    dev_total_hours = round(sum(c["total_hours"] for c in sorted_categories), 1)
    pm_hours = round(dev_total_hours * PM_OVERHEAD_RATIO, 1)
    po_hours = round(dev_total_hours * PO_OVERHEAD_RATIO, 1)

    for cat in sorted_categories:
        cat["qa_hours"] = round(cat["total_hours"] * QA_RATIO, 1)

    risk_groups = {}
    for cat in sorted_categories:
        rg = cat["risk_category"]
        if rg not in risk_groups:
            risk_groups[rg] = []
        risk_groups[rg].append(cat)

    risk_group_order = ["Security & Compliance Risk", "Operational Risk", "Technical Debt"]
    ordered_risk_groups = []
    for rg in risk_group_order:
        if rg in risk_groups:
            ordered_risk_groups.append((rg, risk_groups[rg]))

    gantt_tasks = []
    if streams <= 1:
        current_week = 1
        for rg_name, rg_cats in ordered_risk_groups:
            for cat in rg_cats:
                start_week = current_week
                cat_hours = cat["total_hours"]
                weeks_needed = max(1, round(cat_hours / hpw + 0.3))
                end_week = start_week + weeks_needed - 1
                gantt_tasks.append({
                    "name": cat["name"],
                    "risk_category": cat["risk_category"],
                    "start_week": start_week,
                    "end_week": end_week,
                    "weeks": weeks_needed,
                    "hours": round(cat["total_hours"], 1),
                    "resource": cat["resource_type"],
                    "item_count": len(cat["issues"]),
                    "high_count": cat["high_count"],
                    "stream": 1,
                })
                current_week = end_week + 1
    else:
        stream_end_weeks = [0] * streams
        for rg_name, rg_cats in ordered_risk_groups:
            for cat in rg_cats:
                cat_hours = cat["total_hours"]
                weeks_needed = max(1, round(cat_hours / hpw + 0.3))
                earliest_stream = min(range(streams), key=lambda s: stream_end_weeks[s])
                start_week = stream_end_weeks[earliest_stream] + 1
                end_week = start_week + weeks_needed - 1
                gantt_tasks.append({
                    "name": cat["name"],
                    "risk_category": cat["risk_category"],
                    "start_week": start_week,
                    "end_week": end_week,
                    "weeks": weeks_needed,
                    "hours": round(cat["total_hours"], 1),
                    "resource": cat["resource_type"],
                    "item_count": len(cat["issues"]),
                    "high_count": cat["high_count"],
                    "stream": earliest_stream + 1,
                })
                stream_end_weeks[earliest_stream] = end_week
            group_max = max(stream_end_weeks)
            stream_end_weeks = [group_max] * streams

    total_weeks = max((t["end_week"] for t in gantt_tasks), default=1)
    total_items = sum(len(c["issues"]) for c in sorted_categories)

    resource_summary = {}
    for cat in sorted_categories:
        rt = cat["resource_type"]
        if rt not in resource_summary:
            resource_summary[rt] = {"hours": 0, "items": 0, "rate": rates.get(rt, 110)}
        resource_summary[rt]["hours"] += cat["total_hours"]
        resource_summary[rt]["items"] += len(cat["issues"])

    total_qa_hours = round(sum(c.get("qa_hours", 0) for c in sorted_categories), 1)
    if total_qa_hours > 0:
        resource_summary["QA Tester"] = {
            "hours": total_qa_hours,
            "items": total_items,
            "rate": rates.get("QA Tester", 90),
        }
    if pm_hours > 0:
        resource_summary["Project Manager"] = {
            "hours": pm_hours,
            "items": len(sorted_categories),
            "rate": rates.get("Project Manager", 120),
        }
    if po_hours > 0:
        resource_summary["Product Owner"] = {
            "hours": po_hours,
            "items": len(sorted_categories),
            "rate": rates.get("Product Owner", 130),
        }

    for rt in resource_summary:
        resource_summary[rt]["hours"] = round(resource_summary[rt]["hours"], 1)
        resource_summary[rt]["cost"] = round(resource_summary[rt]["hours"] * resource_summary[rt]["rate"])

    base_cost = sum(r["cost"] for r in resource_summary.values())
    base_hours = round(sum(r["hours"] for r in resource_summary.values()), 1)

    contingency_hours = round(base_hours * contingency / 100, 1) if contingency > 0 else 0
    contingency_cost = round(base_cost * contingency / 100) if contingency > 0 else 0
    total_cost = base_cost + contingency_cost
    total_hours = round(base_hours + contingency_hours, 1)

    if total_qa_hours > 0:
        qa_weeks = max(1, round(total_qa_hours / hpw + 0.3))
        qa_start = max((t["end_week"] for t in gantt_tasks), default=0) + 1
        gantt_tasks.append({
            "name": "QA Testing & Validation",
            "risk_category": "Cross-cutting",
            "start_week": qa_start,
            "end_week": qa_start + qa_weeks - 1,
            "weeks": qa_weeks,
            "hours": total_qa_hours,
            "resource": "QA Tester",
            "item_count": total_items,
            "high_count": 0,
            "stream": 1,
        })
        total_weeks = max(total_weeks, qa_start + qa_weeks - 1)

    base_weeks = total_weeks

    if contingency > 0 and contingency_hours > 0:
        contingency_weeks_count = max(1, round(contingency_hours / hpw + 0.3))
        cont_start = total_weeks + 1
        cont_end = cont_start + contingency_weeks_count - 1
        gantt_tasks.append({
            "name": "Contingency Buffer",
            "risk_category": "Contingency",
            "start_week": cont_start,
            "end_week": cont_end,
            "weeks": contingency_weeks_count,
            "hours": contingency_hours,
            "resource": "All Resources",
            "item_count": 0,
            "high_count": 0,
            "stream": 1,
        })
        total_weeks = cont_end
    else:
        contingency_weeks_count = 0

    return {
        "categories": sorted_categories,
        "gantt_tasks": gantt_tasks,
        "total_weeks": total_weeks,
        "base_weeks": base_weeks,
        "contingency_weeks": contingency_weeks_count,
        "total_hours": total_hours,
        "total_items": total_items,
        "total_cost": total_cost,
        "base_hours": base_hours,
        "base_cost": base_cost,
        "contingency_percent": contingency,
        "contingency_hours": contingency_hours,
        "contingency_cost": contingency_cost,
        "resource_summary": resource_summary,
        "all_smells": all_smells,
        "week_range": list(range(1, total_weeks + 1)),
        "parallel_streams": streams,
        "hours_per_week": hpw,
        "custom_rates": rates,
    }


# Configure logging
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {
    'py', 'js', 'html', 'htm', 'css', 'c', 'cpp', 'cc', 'cxx', 'h', 'hpp',
    'cs', 'go', 'java', 'php', 'rb', 'swift', 'kt', 'rs', 'ts', 'jsx', 'tsx'
}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB per file (individual uploads)
MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100MB total for a ZIP upload
MAX_FILES = int(os.environ.get("MAX_FILES", 100))
MAX_ZIP_FILES = int(os.environ.get("MAX_ZIP_FILES", 500))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

SKIP_DIRS = {
    '__macosx', '.git', 'node_modules', 'venv', '.venv', 'env', '.env',
    'dist', 'build', '.idea', '.vscode', '__pycache__', '.pytest_cache',
    'vendor', 'bower_components', 'target', 'out', 'bin', 'obj'
}

def extract_zip_files(zip_bytes):
    """Extract supported code files from a zip archive in memory.

    Returns a list of dicts with keys: filename, content, size_bytes.
    Raises ValueError with a descriptive message on failure.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            if zf.testzip() is not None:
                raise ValueError('The ZIP archive appears to be corrupted.')
            extracted = []
            total_size = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                parts = info.filename.replace('\\', '/').split('/')
                if any(p.lower() in SKIP_DIRS or p.startswith('.') for p in parts[:-1]):
                    continue
                name = parts[-1]
                if name.startswith('.'):
                    continue
                if not allowed_file(name):
                    continue
                raw = zf.read(info.filename)
                try:
                    content_str = raw.decode('utf-8')
                except UnicodeDecodeError:
                    continue
                total_size += len(raw)
                rel_path = '/'.join(parts)
                extracted.append({
                    'filename': name,
                    'file_path': rel_path,
                    'content': content_str,
                    'size_bytes': len(raw),
                    'line_count': len(content_str.splitlines()),
                })
            if not extracted:
                raise ValueError('No supported code files were found inside the ZIP archive.')
            return extracted, total_size
    except zipfile.BadZipFile:
        raise ValueError('The uploaded file is not a valid ZIP archive.')

def get_language_from_extension(filename):
    """Determine programming language from file extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    language_map = {
        'py': 'python',
        'js': 'javascript',
        'jsx': 'javascript',
        'ts': 'javascript',
        'tsx': 'javascript',
        'html': 'html',
        'htm': 'html',
        'css': 'css',
        'c': 'c',
        'h': 'c',
        'cpp': 'cpp',
        'cc': 'cpp',
        'cxx': 'cpp',
        'hpp': 'cpp',
        'cs': 'csharp',
        'go': 'go',
        'java': 'java',
        'php': 'php',
        'rb': 'ruby',
        'swift': 'swift',
        'kt': 'kotlin',
        'rs': 'rust'
    }
    return language_map.get(ext, 'unknown')

@main_bp.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing recent analyses"""
    analyses = Analysis.query.filter_by(user_id=current_user.id)\
                           .order_by(Analysis.created_at.desc())\
                           .limit(10).all()

    from models import Company
    company = Company.query.get(current_user.company_id) if current_user.company_id else None
    trial_days_remaining = company.get_trial_days_remaining() if company else 0
    is_trial_expired = company.is_trial_expired() if company else False

    show_onboarding = not current_user.hide_onboarding

    team_analyses = []
    if current_user.company_id:
        from models import Subscription
        sub = Subscription.query.filter_by(company_id=current_user.company_id).first()
        if sub and sub.allows_team():
            team_analyses = Analysis.query.filter(
                Analysis.company_id == current_user.company_id,
                Analysis.is_shared == True,
                Analysis.user_id != current_user.id
            ).order_by(Analysis.created_at.desc()).limit(20).all()

    return render_template('dashboard.html',
                         analyses=analyses,
                         company=company,
                         trial_days_remaining=trial_days_remaining,
                         is_trial_expired=is_trial_expired,
                         show_onboarding=show_onboarding,
                         team_analyses=team_analyses)

@main_bp.route('/help')
@login_required
def help_page():
    """Help and documentation page"""
    return render_template('help.html')

@main_bp.route('/onboarding/dismiss', methods=['POST'])
@login_required
def dismiss_onboarding():
    """Toggle the onboarding modal visibility for the current user."""
    hide = '1' in request.form.getlist('hide_onboarding')
    current_user.hide_onboarding = hide
    db.session.commit()
    return redirect(url_for('main.dashboard'))

@main_bp.route('/demo-analysis')
@login_required
def start_demo_analysis():
    """Create a demo analysis using bundled sample code files."""
    try:
        demo_dir = os.path.join(current_app.static_folder, 'demo_code')
        demo_files = ['main.py', 'models.py', 'task_manager.py', 'utils.py']

        if not os.path.isdir(demo_dir):
            flash('Demo files are not available. Please try uploading your own code.', 'error')
            return redirect(url_for('main.dashboard'))

        analysis = Analysis(
            name='Demo - Task Manager',
            description='A sample Task Manager project to demonstrate DeCoder analysis capabilities including mind maps, documentation, and code insights.',
            source_type='upload',
            user_id=current_user.id,
            status='analyzing'
        )
        db.session.add(analysis)
        db.session.flush()

        processed_count = 0
        for fname in demo_files:
            fpath = os.path.join(demo_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, 'r') as f:
                content = f.read()
            language = get_language_from_extension(fname)
            code_file = CodeFile(
                filename=fname,
                file_path=fname,
                language=language,
                content=content,
                size_bytes=len(content.encode('utf-8')),
                line_count=len(content.splitlines()),
                analysis_id=analysis.id
            )
            db.session.add(code_file)
            processed_count += 1

        if processed_count == 0:
            db.session.rollback()
            flash('No demo files could be loaded. Please try uploading your own code.', 'error')
            return redirect(url_for('main.dashboard'))

        db.session.commit()
        initialize_analysis_events(analysis.id)
        update_analysis_event(analysis.id, 'team_ready', 'completed')

        flash('Demo analysis started! Watch as DeCoder analyses the sample project.', 'info')
        return redirect(url_for('main.view_analysis', analysis_id=analysis.id))
    except Exception as e:
        current_app.logger.error(f"Demo analysis error: {str(e)}")
        db.session.rollback()
        flash('Could not start demo analysis. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

@main_bp.route('/upload')
@login_required
def upload_form():
    """File upload form"""
    return render_template('upload.html', max_files=MAX_FILES)

@main_bp.route('/upload', methods=['POST'])
@login_required
def upload_files():
    """Handle file uploads"""
    try:
        if 'files[]' not in request.files:
            flash('No files selected.', 'error')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        analysis_name = request.form.get('analysis_name', '').strip()
        analysis_description = request.form.get('analysis_description', '').strip()
        
        if not analysis_name:
            flash('Analysis name is required.', 'error')
            return redirect(request.url)
        
        if not files or files[0].filename == '':
            flash('No files selected.', 'error')
            return redirect(request.url)

        # --- ZIP upload path ---
        if len(files) == 1 and files[0].filename.lower().endswith('.zip'):
            zip_file = files[0]
            zip_bytes = zip_file.read()

            if len(zip_bytes) > MAX_ZIP_SIZE:
                flash(f'ZIP file is too large. Maximum ZIP size is {MAX_ZIP_SIZE // 1024 // 1024} MB.', 'error')
                return redirect(request.url)

            try:
                extracted, total_size = extract_zip_files(zip_bytes)
            except ValueError as e:
                flash(str(e), 'error')
                return redirect(request.url)

            if len(extracted) > MAX_ZIP_FILES:
                flash(f'ZIP contains too many supported files ({len(extracted)}). Maximum {MAX_ZIP_FILES} allowed.', 'error')
                return redirect(request.url)

            analysis = Analysis(
                name=analysis_name,
                description=analysis_description,
                source_type='upload',
                user_id=current_user.id,
                status='analyzing'
            )
            db.session.add(analysis)
            db.session.flush()

            for f in extracted:
                language = get_language_from_extension(f['filename'])
                code_file = CodeFile(
                    filename=f['filename'],
                    file_path=f['file_path'],
                    language=language,
                    content=f['content'],
                    size_bytes=f['size_bytes'],
                    line_count=f['line_count'],
                    analysis_id=analysis.id
                )
                db.session.add(code_file)

            db.session.commit()
            initialize_analysis_events(analysis.id)
            update_analysis_event(analysis.id, 'team_ready', 'completed')
            flash(f'ZIP extracted: {len(extracted)} files uploaded. Analysis in progress...', 'info')
            return redirect(url_for('main.view_analysis', analysis_id=analysis.id))

        # --- Regular multi-file upload path ---
        if len(files) > MAX_FILES:
            flash(f'Too many files. Maximum {MAX_FILES} files allowed.', 'error')
            return redirect(request.url)
        
        # Create analysis record
        analysis = Analysis(
            name=analysis_name,
            description=analysis_description,
            source_type='upload',
            user_id=current_user.id,
            status='analyzing'
        )
        db.session.add(analysis)
        db.session.flush()  # Get the ID
        
        # Process uploaded files
        processed_files = []
        total_size = 0
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                content = file.read()
                
                # Check file size
                if len(content) > MAX_FILE_SIZE:
                    flash(f'File {filename} is too large (max {MAX_FILE_SIZE//1024//1024}MB).', 'error')
                    continue
                
                total_size += len(content)
                if total_size > MAX_FILE_SIZE * 10:  # 160MB total limit
                    flash('Total upload size too large.', 'error')
                    break
                
                try:
                    content_str = content.decode('utf-8')
                except UnicodeDecodeError:
                    flash(f'File {filename} is not a valid text file.', 'error')
                    continue
                
                language = get_language_from_extension(filename)
                line_count = len(content_str.splitlines())
                
                code_file = CodeFile(
                    filename=filename,
                    file_path=filename,
                    language=language,
                    content=content_str,
                    size_bytes=len(content),
                    line_count=line_count,
                    analysis_id=analysis.id
                )
                
                db.session.add(code_file)
                processed_files.append(code_file)
        
        if not processed_files:
            flash('No valid files were processed.', 'error')
            db.session.rollback()
            return redirect(request.url)
        
        db.session.commit()
        
        # Initialize progress tracking
        initialize_analysis_events(analysis.id)
        update_analysis_event(analysis.id, 'team_ready', 'completed')
        
        # Return immediately - processing will be triggered by frontend
        flash(f'Files uploaded successfully. Analysis in progress...', 'info')
        return redirect(url_for('main.view_analysis', analysis_id=analysis.id))
    
    except RequestEntityTooLarge:
        flash('Upload too large. Please reduce file size.', 'error')
        return redirect(request.url)
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash('Upload failed. Please try again.', 'error')
        return redirect(request.url)

def _safe_commit(db):
    """Safely commit the session, rolling back on failure."""
    try:
        db.session.commit()
    except Exception as e:
        logger.warning(f"Commit failed, rolling back: {str(e)}")
        try:
            db.session.rollback()
        except Exception:
            pass
        raise


def _is_transient_db_error(e):
    """True for connection-level DB errors worth retrying (e.g. Neon dropping an idle SSL connection)."""
    if isinstance(e, OperationalError):
        return True
    if isinstance(e, DBAPIError) and getattr(e, "connection_invalidated", False):
        return True
    return False


def _safe_update_status(db, analysis_id, status=None, ai_insights=None, max_retries=3, base_delay=0.5):
    """Safely update analysis status, retrying on transient connection drops with a fresh fetch each attempt."""
    from models import Analysis
    for attempt in range(1, max_retries + 1):
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            analysis = db.session.get(Analysis, analysis_id)
            if not analysis:
                return
            if status is not None:
                analysis.status = status
            if ai_insights is not None:
                analysis.ai_insights = ai_insights
            if status == 'completed':
                analysis.completed_at = datetime.utcnow()
            db.session.commit()
            if attempt > 1:
                logger.info(f"Recovered: updated analysis {analysis_id} status to '{status}' on retry attempt {attempt}")
            return
        except Exception as e2:
            if _is_transient_db_error(e2) and attempt < max_retries:
                logger.warning(
                    f"Transient DB error updating analysis {analysis_id} status to '{status}' "
                    f"(attempt {attempt}/{max_retries}): {str(e2)}. Retrying..."
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass
                time.sleep(base_delay * attempt)
                continue
            logger.error(f"Failed to update analysis {analysis_id} status to '{status}': {str(e2)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return


def _save_analysis_fields(db, analysis_id, max_retries=3, base_delay=0.5, **fields):
    """
    Persist one or more fields on the Analysis row (e.g. analysis_results, ai_insights, status),
    retrying against a fresh connection on transient DB drops. Re-fetches the row and reapplies
    the fields on every attempt, since a rollback expires any pending in-memory changes.
    """
    from models import Analysis

    for attempt in range(1, max_retries + 1):
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            analysis = db.session.get(Analysis, analysis_id)
            if not analysis:
                logger.warning(f"Analysis {analysis_id} not found when saving fields {list(fields.keys())}")
                return False
            for key, value in fields.items():
                setattr(analysis, key, value)
            db.session.commit()
            if attempt > 1:
                logger.info(f"Recovered: saved {list(fields.keys())} for analysis {analysis_id} on retry attempt {attempt}")
            return True
        except Exception as e:
            if _is_transient_db_error(e) and attempt < max_retries:
                logger.warning(
                    f"Transient DB error saving {list(fields.keys())} for analysis {analysis_id} "
                    f"(attempt {attempt}/{max_retries}): {str(e)}. Retrying with a fresh connection..."
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass
                time.sleep(base_delay * attempt)
                continue
            logger.error(f"Failed to save {list(fields.keys())} for analysis {analysis_id}: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return False
    logger.error(f"Giving up saving {list(fields.keys())} for analysis {analysis_id} after {max_retries} attempts")
    return False


def _save_code_file_result(db, code_file_id, analysis, error, max_retries=3, base_delay=0.5):
    """
    Persist one file's AI analysis results, retrying against a fresh connection on transient
    DB drops instead of losing the whole batch. Re-fetches the row and reapplies the fields on
    every attempt, since a rollback expires any pending in-memory changes.
    """
    from models import CodeFile

    def _apply(code_file):
        if analysis and not error:
            code_file.functions = analysis.get('functions', [])
            code_file.classes = analysis.get('classes', [])
            code_file.imports = analysis.get('imports', [])
            code_file.apis = analysis.get('apis', [])
            code_file.http_calls = analysis.get('http_calls', [])
            code_file.quality_metrics = analysis.get('quality_metrics', {})
        else:
            code_file.functions = []
            code_file.classes = []
            code_file.imports = []
            code_file.apis = []
            code_file.http_calls = []
            code_file.quality_metrics = {}

    for attempt in range(1, max_retries + 1):
        try:
            code_file = db.session.get(CodeFile, code_file_id)
            if not code_file:
                logger.warning(f"CodeFile {code_file_id} not found when saving analysis results")
                return False
            _apply(code_file)
            db.session.commit()
            if attempt > 1:
                logger.info(f"Recovered: saved results for code_file {code_file_id} on retry attempt {attempt}")
            return True
        except Exception as e:
            if _is_transient_db_error(e) and attempt < max_retries:
                logger.warning(
                    f"Transient DB error saving code_file {code_file_id} results "
                    f"(attempt {attempt}/{max_retries}): {str(e)}. Retrying with a fresh connection..."
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass
                time.sleep(base_delay * attempt)
                continue
            logger.error(f"Failed to save results for code_file {code_file_id}: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return False
    logger.error(f"Giving up saving code_file {code_file_id} results after {max_retries} attempts")
    return False

def run_analysis_in_background(app, analysis_id):
    """Background worker function that runs analysis with proper Flask app context"""
    with app.app_context():
        from app import db
        from models import Analysis, CodeFile
        from ai_analyzer import analyze_code, analyze_files_individually
        from analysis_progress import update_analysis_event

        try:
            analysis = db.session.get(Analysis, analysis_id)
            if not analysis:
                logger.error(f"Analysis {analysis_id} not found in background worker")
                return

            code_files = CodeFile.query.filter_by(analysis_id=analysis_id).all()

            if not code_files:
                logger.error(f"No files found for analysis {analysis_id}")
                _safe_update_status(db, analysis_id, 'failed')
                return

            update_analysis_event(analysis_id, 'architect_analysis', 'in_progress')

            def _save_fn(code_file_id, file_analysis, file_error):
                _save_code_file_result(db, code_file_id, file_analysis, file_error)

            analysis_results = analyze_code(code_files, save_fn=_save_fn)
            if not _save_analysis_fields(db, analysis_id, analysis_results=analysis_results):
                raise RuntimeError(f"Failed to persist analysis_results for analysis {analysis_id} after retries")
            update_analysis_event(analysis_id, 'architect_analysis', 'completed')

            update_analysis_event(analysis_id, 'business_analyst', 'in_progress')
            update_analysis_event(analysis_id, 'business_analyst', 'completed')

            update_analysis_event(analysis_id, 'app_architect', 'in_progress')
            update_analysis_event(analysis_id, 'app_architect', 'completed')

            try:
                update_analysis_event(analysis_id, 'data_flow_expert', 'in_progress')
                file_ai_analysis = analyze_files_individually(code_files)

                update_analysis_event(analysis_id, 'data_flow_expert', 'completed')

                update_analysis_event(analysis_id, 'consolidation', 'in_progress')
                ai_insights_payload = {
                    "status": "success",
                    "message": "AI analysis completed successfully",
                    "file_analyses": file_ai_analysis.get("file_analyses", {}),
                    "comprehensive_analysis": None,
                    "total_files": file_ai_analysis.get("total_files", 0),
                    "successful_analyses": file_ai_analysis.get("successful_analyses", 0)
                }
                if not _save_analysis_fields(db, analysis_id, ai_insights=ai_insights_payload):
                    raise RuntimeError(f"Failed to persist ai_insights for analysis {analysis_id} after retries")
                update_analysis_event(analysis_id, 'consolidation', 'completed')
                ai_analysis_failed = False
            except Exception as e:
                ai_analysis_failed = True
                logger.error(f"AI analysis failed: {str(e)}")
                _safe_update_status(db, analysis_id, 'failed', ai_insights={
                    "status": "error",
                    "message": f"AI analysis failed: {str(e)}",
                    "file_analyses": {},
                    "comprehensive_analysis": None
                })

            if not ai_analysis_failed:
                if _save_analysis_fields(db, analysis_id, status='completed', completed_at=datetime.utcnow()):
                    try:
                        update_analysis_event(analysis_id, 'completed', 'completed')
                    except Exception as e:
                        logger.warning(f"Analysis {analysis_id} completed, but failed to record the completion event: {str(e)}")
                    logger.info(f"Analysis {analysis_id} completed successfully in background")
                else:
                    logger.error(f"Failed to mark analysis {analysis_id} as completed after retries")
                    _safe_update_status(db, analysis_id, 'failed')

        except Exception as e:
            logger.error(f"Analysis processing failed in background: {str(e)}")
            _safe_update_status(db, analysis_id, 'failed')

@main_bp.route('/analysis/<int:analysis_id>/process', methods=['POST'])
@login_required
def process_analysis(analysis_id):
    """Process an analysis (actual code analysis work) - Starts background processing"""
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        
        # Verify ownership
        if analysis.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        # Check if already processing or completed
        if analysis.status not in ['analyzing', 'pending']:
            return jsonify({'status': 'error', 'message': 'Analysis already processed'}), 400
        
        # Get code files
        code_files = CodeFile.query.filter_by(analysis_id=analysis_id).all()
        
        if not code_files:
            return jsonify({'status': 'error', 'message': 'No files found'}), 400
        
        # Start processing in background thread
        import threading
        thread = threading.Thread(
            target=run_analysis_in_background,
            args=(current_app._get_current_object(), analysis_id)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started background processing for analysis {analysis_id}")
        
        # Return immediately - processing happens in background
        return jsonify({
            'status': 'success',
            'message': 'Analysis processing started',
            'analysis_id': analysis.id
        })
    
    except Exception as e:
        logger.error(f"Process analysis error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main_bp.route('/github-import')
@login_required
def github_import_form():
    """GitHub repository import form"""
    return render_template('upload.html', github_mode=True)

@main_bp.route('/github-import', methods=['POST'])
@login_required
def github_import():
    """Handle GitHub repository import"""
    try:
        repo_url = request.form.get('repo_url', '').strip()
        analysis_name = request.form.get('analysis_name', '').strip()
        analysis_description = request.form.get('analysis_description', '').strip()
        github_token = request.form.get('github_token', '').strip() or None
        
        if not repo_url:
            flash('Repository URL is required.', 'error')
            return redirect(request.url)
        
        if not analysis_name:
            flash('Analysis name is required.', 'error')
            return redirect(request.url)
        
        # Create analysis record
        analysis = Analysis(
            name=analysis_name,
            description=analysis_description,
            source_type='github',
            source_url=repo_url,
            user_id=current_user.id,
            status='analyzing'
        )
        db.session.add(analysis)
        db.session.flush()
        
        # Import repository
        try:
            code_files = import_github_repo(repo_url, analysis.id, github_token)
            
            if not code_files:
                flash('No supported code files found in repository.', 'error')
                db.session.rollback()
                return redirect(request.url)
            
            db.session.commit()
            
            # Initialize progress tracking
            initialize_analysis_events(analysis.id)
            update_analysis_event(analysis.id, 'team_ready', 'completed')
            
            # Return immediately - processing will be triggered by frontend
            flash(f'Repository imported successfully. Analysis in progress...', 'info')
            return redirect(url_for('main.view_analysis', analysis_id=analysis.id))
            
        except Exception as e:
            current_app.logger.error(f"GitHub import failed: {str(e)}")
            analysis.status = 'failed'
            db.session.commit()
            flash(f'GitHub import failed: {str(e)}', 'error')
            return redirect(request.url)
            
    except Exception as e:
        current_app.logger.error(f"GitHub import error: {str(e)}")
        flash('Import failed. Please try again.', 'error')
        return redirect(request.url)

@main_bp.route('/analysis/<int:analysis_id>')
@login_required
def view_analysis(analysis_id):
    """View analysis results"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if not _can_view_analysis(analysis):
        flash('You do not have permission to view this analysis.', 'error')
        return redirect(url_for('main.dashboard'))
    
    health_data = _compute_health_scores(analysis)
    prior_requests = ChangeRequest.query.filter_by(
        analysis_id=analysis_id
    ).order_by(ChangeRequest.created_at.desc()).all()
    return render_template(
        'analysis.html',
        analysis=analysis,
        health=health_data,
        change_requests=prior_requests
    )

@main_bp.route('/analysis/<int:analysis_id>/change-advisor', methods=['POST'])
@login_required
def submit_change_advisor(analysis_id):
    """Accept a natural language change description and generate an AI-powered implementation plan."""
    analysis = Analysis.query.get_or_404(analysis_id)

    if not _can_view_analysis(analysis):
        flash('You do not have permission to use the Change Advisor for this analysis.', 'error')
        return redirect(url_for('main.dashboard'))

    if analysis.status != 'completed':
        flash('Change Advisor is only available for completed analyses.', 'warning')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

    description = request.form.get('description', '').strip()
    if not description:
        flash('Please describe the change you want to make.', 'warning')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id) + '#change-advisor')

    change_request = ChangeRequest(
        analysis_id=analysis_id,
        user_id=current_user.id,
        description=description,
        status='processing'
    )
    db.session.add(change_request)
    db.session.commit()

    try:
        result = change_advisor_module.generate_change_plan(
            description=description,
            analysis=analysis,
            code_files=analysis.code_files
        )
        change_request.result = result
        change_request.status = 'completed'
    except Exception as e:
        logger.error(f"Change Advisor failed for analysis {analysis_id}: {str(e)}")
        change_request.status = 'failed'
        change_request.result = {'error': str(e)}

    db.session.commit()
    return redirect(
        url_for('main.view_change_request', analysis_id=analysis_id, request_id=change_request.id)
    )


@main_bp.route('/analysis/<int:analysis_id>/change-advisor/<int:request_id>')
@login_required
def view_change_request(analysis_id, request_id):
    """Display a saved Change Advisor result."""
    analysis = Analysis.query.get_or_404(analysis_id)

    if not _can_view_analysis(analysis):
        flash('You do not have permission to view this result.', 'error')
        return redirect(url_for('main.dashboard'))

    change_request = ChangeRequest.query.filter_by(
        id=request_id, analysis_id=analysis_id
    ).first_or_404()

    health_data = _compute_health_scores(analysis)
    prior_requests = ChangeRequest.query.filter_by(
        analysis_id=analysis_id
    ).order_by(ChangeRequest.created_at.desc()).all()

    return render_template(
        'analysis.html',
        analysis=analysis,
        health=health_data,
        change_requests=prior_requests,
        active_change_request=change_request,
        active_tab='change-advisor'
    )


@main_bp.route('/analysis/<int:analysis_id>/delete', methods=['POST'])
@login_required
def delete_analysis(analysis_id):
    """Delete an analysis"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    # Check permissions - only owner or admin can delete
    if not current_user.is_admin() and analysis.user_id != current_user.id:
        flash('You do not have permission to delete this analysis.', 'error')
        return redirect(url_for('main.dashboard'))
    
    analysis_name = analysis.name

    # Block deletion if the analysis is part of any System
    linked_systems = SystemRepo.query.filter_by(analysis_id=analysis_id).all()
    if linked_systems:
        flash(
            f'Analysis "{analysis_name}" is linked to a System and cannot be deleted. '
            'Remove it from the System first.',
            'error'
        )
        return redirect(url_for('main.dashboard'))

    try:
        db.session.delete(analysis)
        db.session.commit()
        flash(f'Analysis "{analysis_name}" has been successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete analysis: {str(e)}")
        flash('Failed to delete analysis. Please try again.', 'error')
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/analysis/<int:analysis_id>/toggle-sharing', methods=['POST'])
@login_required
def toggle_sharing(analysis_id):
    """Toggle shared/private flag on an analysis"""
    analysis = Analysis.query.get_or_404(analysis_id)

    if analysis.user_id != current_user.id:
        flash('You do not have permission to change sharing for this analysis.', 'error')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

    if not current_user.has_team_access():
        flash('Sharing requires a Team or Enterprise subscription.', 'error')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

    try:
        analysis.is_shared = not analysis.is_shared
        if analysis.is_shared:
            analysis.company_id = current_user.company_id
        db.session.commit()
        state = 'shared with your team' if analysis.is_shared else 'set to private'
        flash(f'Analysis "{analysis.name}" is now {state}.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to toggle sharing: {str(e)}")
        flash('Failed to update sharing. Please try again.', 'error')

    return redirect(url_for('main.view_analysis', analysis_id=analysis_id))


@main_bp.route('/analysis/<int:analysis_id>/data')
@login_required
def analysis_data(analysis_id):
    """Get analysis data as JSON for diagrams"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    # Check permissions
    if not _can_view_analysis(analysis):
        return jsonify({'error': 'Permission denied'}), 403

    return jsonify({
        'analysis': {
            'id': analysis.id,
            'name': analysis.name,
            'description': analysis.description,
            'status': analysis.status,
            'created_at': analysis.created_at.isoformat(),
            'results': analysis.analysis_results,
            'diagram_data': analysis.diagram_data
        }
    })

@main_bp.route('/analysis/<int:analysis_id>/progress')
@login_required
def analysis_progress(analysis_id):
    """Get analysis progress for real-time updates"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    # Check permissions
    if not _can_view_analysis(analysis):
        return jsonify({'error': 'Permission denied'}), 403

    progress_data = get_analysis_progress(analysis_id)
    progress_data['analysis_status'] = analysis.status
    
    return jsonify(progress_data)

@main_bp.route('/analysis/<int:analysis_id>/mindmap')
@login_required
def mindmap_data(analysis_id):
    """Get mind map data for an analysis"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if not _can_view_analysis(analysis):
        abort(403)

    # Generate mind map data if not exists
    if not analysis.mindmap_data:
        if analysis.analysis_results:
            print(f"Analysis results keys: {list(analysis.analysis_results.keys())}")
            mindmap_data = generate_mindmap_data(analysis.analysis_results, analysis.name)
            print(f"Generated mindmap nodes: {len(mindmap_data.get('nodes', []))}")
            print(f"Generated mindmap edges: {len(mindmap_data.get('edges', []))}")
            analysis.mindmap_data = mindmap_data
            db.session.commit()
        else:
            return jsonify({"error": "No analysis results available"}), 400
    
    return jsonify(analysis.mindmap_data)

@main_bp.route('/analysis/<int:analysis_id>/regenerate-mindmap', methods=['POST'])
@login_required
def regenerate_mindmap(analysis_id):
    """Regenerate mind map data for an analysis"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    # Check ownership
    if analysis.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    
    if analysis.analysis_results:
        # Regenerate mind map data
        mindmap_data = generate_mindmap_data(analysis.analysis_results, analysis.name)
        analysis.mindmap_data = mindmap_data
        db.session.commit()
        
        flash('Mind map regenerated successfully!', 'success')
        return jsonify({"status": "success", "data": mindmap_data})
    else:
        return jsonify({"error": "No analysis results available"}), 400

@main_bp.route('/analysis/<int:analysis_id>/graph')
@login_required
def view_graph(analysis_id):
    """Full-page relationship graph visualisation"""
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _can_view_analysis(analysis):
        abort(403)
    return render_template('graph.html', analysis=analysis)


@main_bp.route('/analysis/<int:analysis_id>/graph-data')
@login_required
def graph_data(analysis_id):
    """Return JSON graph data, generating and caching if needed"""
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _can_view_analysis(analysis):
        return jsonify({'error': 'Permission denied'}), 403

    if not analysis.graph_data:
        if not analysis.analysis_results:
            return jsonify({'error': 'No analysis results available'}), 400
        data = generate_graph_data(analysis.analysis_results, analysis.name)
        analysis.graph_data = data
        db.session.commit()

    return jsonify(analysis.graph_data)


@main_bp.route('/analysis/<int:analysis_id>/regenerate-graph', methods=['POST'])
@login_required
def regenerate_graph(analysis_id):
    """Clear and regenerate cached graph data"""
    analysis = Analysis.query.get_or_404(analysis_id)
    if analysis.user_id != current_user.id and not current_user.is_admin():
        abort(403)

    if not analysis.analysis_results:
        return jsonify({'error': 'No analysis results available'}), 400

    data = generate_graph_data(analysis.analysis_results, analysis.name)
    analysis.graph_data = data
    db.session.commit()
    return jsonify({'status': 'success', 'data': data})


@main_bp.route('/analysis/<int:analysis_id>/node-insights')
@login_required
def node_insights(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _can_view_analysis(analysis):
        return jsonify({'error': 'Permission denied'}), 403

    filename = request.args.get('file', '')
    if not filename:
        return jsonify({'error': 'Missing file parameter'}), 400

    result = {
        'what_it_does': None,
        'observations': [],
        'recommendations': [],
        'code_quality_score': None,
        'complexity_level': None,
        'performance_notes': None,
        'function_count': None,
        'language': None,
    }

    if analysis.ai_insights and isinstance(analysis.ai_insights, dict):
        file_analyses = analysis.ai_insights.get('file_analyses', {})
        file_data = file_analyses.get(filename, {})
        inner = file_data.get('analysis', {})
        if isinstance(inner, dict):
            analysis_data = inner.get('analysis', {})
            if isinstance(analysis_data, dict):
                result['what_it_does'] = analysis_data.get('what_it_does')
                result['observations'] = analysis_data.get('observations', [])
                result['recommendations'] = analysis_data.get('recommendations', [])
                result['code_quality_score'] = analysis_data.get('code_quality_score')
                result['complexity_level'] = analysis_data.get('complexity_level')
                result['performance_notes'] = analysis_data.get('performance_notes')

    if analysis.analysis_results and isinstance(analysis.analysis_results, dict):
        ar_file = analysis.analysis_results.get(filename, {})
        if isinstance(ar_file, dict):
            ar_funcs = ar_file.get('functions', [])
            if isinstance(ar_funcs, list):
                result['function_count'] = len(ar_funcs)
            ar_lang = ar_file.get('language')
            if ar_lang:
                result['language'] = ar_lang

    basename = filename.split('/')[-1]
    cf = CodeFile.query.filter_by(analysis_id=analysis_id, filename=filename).first()
    if not cf:
        cf = CodeFile.query.filter_by(analysis_id=analysis_id, filename=basename).first()
    if not cf:
        cf = CodeFile.query.filter_by(analysis_id=analysis_id, file_path=filename).first()

    if cf:
        if result['function_count'] is None:
            funcs = cf.functions
            result['function_count'] = len(funcs) if isinstance(funcs, list) else 0
        if not result['language']:
            result['language'] = cf.language

    return jsonify(result)


@main_bp.route('/documentation/<int:analysis_id>')
@login_required
def view_documentation(analysis_id):
    """View generated documentation for an analysis"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if not _can_view_analysis(analysis):
        abort(403)

    try:
        # Generate structured documentation
        documentation = generate_documentation_for_analysis(analysis_id)

        # Define section icons for the interface
        section_icons = {
            'overview': 'chart-pie',
            'quality_metrics': 'tachometer-alt',
            'key_components': 'cube',
            'architecture': 'sitemap',
            'security': 'shield-alt',
            'hardcoded_items': 'code',
            'file_details': 'file-alt',
            'recommendations': 'lightbulb'
        }
        
        return render_template('documentation.html', 
                             analysis=analysis,
                             documentation=documentation,
                             section_icons=section_icons)
    except Exception as e:
        flash(f'Error generating documentation: {str(e)}', 'error')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

@main_bp.route('/documentation/<int:analysis_id>/download/<format>')
@login_required
def download_documentation(analysis_id, format):
    """Download documentation in specified format"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if not _can_view_analysis(analysis):
        abort(403)

    try:
        # Generate structured documentation
        documentation = generate_documentation_for_analysis(analysis_id)

        if format == 'docx':
            # Generate DOCX document
            doc_generator = DocumentationGenerator()
            docx_doc = doc_generator.generate_docx(documentation)
            
            # Save to memory
            docx_buffer = io.BytesIO()
            docx_doc.save(docx_buffer)
            docx_buffer.seek(0)
            
            filename = f"{analysis.name}_documentation.docx"
            return send_file(docx_buffer, 
                           as_attachment=True, 
                           download_name=filename,
                           mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        elif format == 'markdown':
            # Generate markdown for backward compatibility
            content = documentation.get('markdown', 'Documentation not available')
            mimetype = 'text/markdown'
            filename = f"{analysis.name}_documentation.md"
        elif format == 'html':
            # Generate HTML for backward compatibility
            content = documentation.get('html', 'Documentation not available')
            mimetype = 'text/html'
            filename = f"{analysis.name}_documentation.html"
        else:
            abort(400)
        
        response = make_response(content)
        response.headers['Content-Type'] = mimetype
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        flash(f'Error downloading documentation: {str(e)}', 'error')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

@main_bp.route('/documentation/<int:analysis_id>/download/summary')
@login_required
def download_summary(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)

    if not _can_view_analysis(analysis):
        abort(403)

    if analysis.status != 'completed' or not analysis.analysis_results:
        flash('Analysis must be completed before exporting a summary.', 'warning')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

    try:
        doc_generator = DocumentationGenerator()
        docx_doc = doc_generator.generate_summary_docx(analysis)

        docx_buffer = io.BytesIO()
        docx_doc.save(docx_buffer)
        docx_buffer.seek(0)

        filename = f"{analysis.name}_executive_summary.docx"
        return send_file(docx_buffer,
                        as_attachment=True,
                        download_name=filename,
                        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        flash(f'Error generating executive summary: {str(e)}', 'error')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

@main_bp.route('/admin')
@login_required
def admin_panel():
    """Admin panel (admin only)"""
    if not current_user.is_admin():
        flash('Access restricted to platform administrators.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get system statistics
    from models import User
    total_users = User.query.count()
    total_analyses = Analysis.query.count()
    recent_analyses = Analysis.query.order_by(Analysis.created_at.desc()).limit(20).all()
    all_users = User.query.order_by(User.username).all()

    team_companies = (Company.query
                      .join(Subscription, Company.id == Subscription.company_id)
                      .filter(Subscription.tier.in_(['team', 'enterprise']))
                      .order_by(Company.name)
                      .all())

    admin_invite_url = session.pop('admin_invite_url', None)

    return render_template('dashboard.html', 
                         admin_mode=True,
                         total_users=total_users,
                         total_analyses=total_analyses,
                         analyses=recent_analyses,
                         all_users=all_users,
                         team_companies=team_companies,
                         admin_invite_url=admin_invite_url)


@main_bp.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    """Allow a platform admin to reset any user's password"""
    if not current_user.is_admin():
        flash('Access restricted to platform administrators.', 'error')
        return redirect(url_for('main.dashboard'))

    from models import User
    from werkzeug.security import generate_password_hash

    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()

    if len(new_password) < 8:
        flash(f'Password must be at least 8 characters long.', 'error')
        return redirect(url_for('main.admin_panel'))

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash(f'Password for {user.username} has been reset successfully.', 'success')
    return redirect(url_for('main.admin_panel'))


@main_bp.route('/admin/generate-invite', methods=['POST'])
@login_required
def admin_generate_invite():
    """Allow a platform admin to generate an invite link for an existing Team or Enterprise company"""
    if not current_user.is_admin():
        flash('Access restricted to platform administrators.', 'error')
        return redirect(url_for('main.dashboard'))

    company_id = request.form.get('company_id', '').strip()

    if not company_id:
        flash('Please select a company.', 'error')
        return redirect(url_for('main.admin_panel'))

    company = Company.query.get(company_id)
    if not company:
        flash('Company not found.', 'error')
        return redirect(url_for('main.admin_panel'))

    subscription = company.subscription
    if not subscription or not subscription.allows_team():
        flash('Selected company does not have a Team or Enterprise subscription.', 'error')
        return redirect(url_for('main.admin_panel'))

    current_count = company.get_member_count()
    if not subscription.can_add_user(current_count):
        flash(f'{company.name} has reached its maximum number of seats.', 'error')
        return redirect(url_for('main.admin_panel'))

    try:
        invite = CompanyInvite()
        invited_email = request.form.get('invited_email', '').strip().lower() or None

        invite.company_id = company.id
        invite.token = CompanyInvite.generate_token()
        invite.invited_email = invited_email
        invite.created_by_id = current_user.id
        db.session.add(invite)
        db.session.commit()

        invite_url = url_for('auth.invite_register', token=invite.token, _external=True)
        session['admin_invite_url'] = invite_url
        flash(f'Invite link generated for {company.name}.', 'success')
        logging.info(f"Admin {current_user.email} generated invite for company {company.id}")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to generate admin invite: {e}")
        flash('Failed to generate invite link. Please try again.', 'error')

    return redirect(url_for('main.admin_panel'))


def generate_diagram_data(analysis_results):
    """Generate Mermaid diagram data from analysis results"""
    if not analysis_results:
        return None
    
    diagrams = {}
    
    # Generate flowchart for function calls and dependencies
    if 'functions' in analysis_results or 'classes' in analysis_results:
        flowchart = ["flowchart TD"]
        node_id = 0
        
        # Add classes
        for file_name, file_data in analysis_results.items():
            if isinstance(file_data, dict) and 'classes' in file_data:
                for class_name in file_data['classes']:
                    flowchart.append(f"    C{node_id}[{class_name}]")
                    node_id += 1
        
        # Add functions
        for file_name, file_data in analysis_results.items():
            if isinstance(file_data, dict) and 'functions' in file_data:
                for func_name in file_data['functions']:
                    flowchart.append(f"    F{node_id}[{func_name}]")
                    node_id += 1
        
        diagrams['flowchart'] = "\n".join(flowchart)
    
    # Generate class diagram
    class_diagram = ["classDiagram"]
    for file_name, file_data in analysis_results.items():
        if isinstance(file_data, dict) and 'classes' in file_data:
            for class_item in file_data['classes']:
                # Handle both string and dictionary formats
                if isinstance(class_item, dict):
                    class_name = class_item.get('name', 'UnknownClass')
                else:
                    class_name = str(class_item)
                class_diagram.append(f"    class {class_name.replace(' ', '_')}")
    
    if len(class_diagram) > 1:
        diagrams['class_diagram'] = "\n".join(class_diagram)
    
    return diagrams


@main_bp.route('/analysis/<int:analysis_id>/remediation')
@login_required
def view_remediation_plan(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _can_view_analysis(analysis):
        abort(403)
    if analysis.status != 'completed':
        flash('Analysis must be completed before generating a remediation plan.', 'warning')
        return redirect(url_for('main.view_analysis', analysis_id=analysis_id))

    custom_rates = {}
    for role in DEFAULT_RESOURCE_HOURLY_RATES:
        param_key = 'rate_' + role.lower().replace(' ', '_').replace('-', '_')
        val = request.args.get(param_key)
        if val:
            try:
                custom_rates[role] = float(val)
            except (ValueError, TypeError):
                pass

    try:
        parallel_streams = int(request.args.get('parallel_streams', DEFAULT_PARALLEL_STREAMS))
    except (ValueError, TypeError):
        parallel_streams = DEFAULT_PARALLEL_STREAMS

    try:
        hours_per_week = int(request.args.get('hours_per_week', DEFAULT_HOURS_PER_WEEK))
    except (ValueError, TypeError):
        hours_per_week = DEFAULT_HOURS_PER_WEEK

    try:
        contingency_percent = int(request.args.get('contingency_percent', DEFAULT_CONTINGENCY_PERCENT))
    except (ValueError, TypeError):
        contingency_percent = DEFAULT_CONTINGENCY_PERCENT

    currency_code = request.args.get('currency', DEFAULT_CURRENCY).upper()
    if currency_code not in CURRENCY_MAP:
        currency_code = DEFAULT_CURRENCY
    currency_symbol = CURRENCY_MAP[currency_code]['symbol']

    plan = _generate_remediation_plan(analysis, custom_rates=custom_rates or None,
                                       parallel_streams=parallel_streams,
                                       hours_per_week=hours_per_week,
                                       contingency_percent=contingency_percent)
    health = _compute_health_scores(analysis)

    calc_info = {
        'categories': {k: {
            'risk_category': v['risk_category'],
            'hours_per_instance': v['hours_per_instance'],
            'resource_type': v['resource_type'],
        } for k, v in SMELL_BUSINESS_MAP.items() if k != 'default'},
        'default_category': {
            'hours_per_instance': SMELL_BUSINESS_MAP['default']['hours_per_instance'],
            'resource_type': SMELL_BUSINESS_MAP['default']['resource_type'],
        },
        'severity_multipliers': SEVERITY_MULTIPLIER,
        'resource_rates': plan['custom_rates'],
        'hours_per_week': plan['hours_per_week'],
        'default_rates': DEFAULT_RESOURCE_HOURLY_RATES,
        'parallel_streams': plan['parallel_streams'],
        'qa_ratio': QA_RATIO,
        'pm_overhead_ratio': PM_OVERHEAD_RATIO,
        'po_overhead_ratio': PO_OVERHEAD_RATIO,
        'currency_code': currency_code,
        'currency_symbol': currency_symbol,
        'currency_options': CURRENCY_MAP,
    }

    return render_template('remediation.html',
                         analysis=analysis,
                         plan=plan,
                         health=health,
                         calc_info=calc_info)


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------

@main_bp.route('/chat/analyses')
@login_required
def chat_analyses():
    """Return a JSON list of completed analyses accessible to the current user."""
    query = Analysis.query.filter_by(status='completed')

    if current_user.is_admin():
        analyses = query.order_by(Analysis.created_at.desc()).all()
    elif current_user.company_id is not None:
        from sqlalchemy import or_
        from models import Subscription
        sub = Subscription.query.filter_by(company_id=current_user.company_id).first()
        has_team_access = sub is not None and sub.allows_team()
        if has_team_access:
            analyses = query.filter(
                or_(
                    Analysis.user_id == current_user.id,
                    (Analysis.is_shared == True) & (Analysis.company_id == current_user.company_id)
                )
            ).order_by(Analysis.created_at.desc()).all()
        else:
            analyses = query.filter(
                Analysis.user_id == current_user.id
            ).order_by(Analysis.created_at.desc()).all()
    else:
        analyses = query.filter(
            Analysis.user_id == current_user.id
        ).order_by(Analysis.created_at.desc()).all()

    result = []
    for a in analyses:
        result.append({
            'id': a.id,
            'name': a.name,
            'source_type': a.source_type,
            'source_url': a.source_url or '',
            'created_at': a.created_at.strftime('%d %b %Y') if a.created_at else '',
        })
    return jsonify(result)


@main_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Accept a user message + list of analysis IDs, return an AI response."""
    data = request.get_json(silent=True) or {}
    analysis_ids = data.get('analysis_ids', [])
    message = (data.get('message') or '').strip()

    if not message:
        return jsonify({'error': 'Message is required.'}), 400
    if not analysis_ids:
        return jsonify({'error': 'Please select at least one analysis result.'}), 400

    # Load and authorise analyses
    context_blocks = []
    for aid in analysis_ids:
        analysis = Analysis.query.get(aid)
        if not analysis or not _can_view_analysis(analysis):
            continue

        block = [f"=== Analysis: {analysis.name} ==="]

        # Summary metrics
        summary = {}
        if analysis.analysis_results and isinstance(analysis.analysis_results, dict):
            summary = analysis.analysis_results.get('_summary', {})
        if summary:
            langs = summary.get('languages', [])
            if isinstance(langs, dict):
                lang_str = ', '.join(langs.keys())
            elif isinstance(langs, list):
                lang_str = ', '.join(str(l) for l in langs)
            else:
                lang_str = str(langs)
            block.append(
                f"Files: {summary.get('total_files', 'N/A')} | "
                f"Functions: {summary.get('total_functions', 'N/A')} | "
                f"Classes: {summary.get('total_classes', 'N/A')} | "
                f"Languages: {lang_str}"
            )

        # AI insights
        insights = analysis.ai_insights or {}
        if isinstance(insights, dict):
            for key in ('overall_assessment', 'architecture_summary', 'technology_stack',
                        'security_summary', 'key_recommendations'):
                val = insights.get(key)
                if val:
                    block.append(f"{key.replace('_', ' ').title()}: {val}")

        # Per-file quality data — read from analysis_results JSON blob (CodeFile rows
        # may have empty quality_metrics columns; the full data lives here).
        ar = analysis.analysis_results or {}
        if isinstance(ar, dict):
            file_entries = [(k, v) for k, v in ar.items()
                            if k != '_summary' and isinstance(v, dict)]
            # Cap at 30 files to stay within context window
            for fname, fdata in file_entries[:30]:
                qm = fdata.get('quality_metrics') or {}
                insights_data = fdata.get('insights') or {}
                lang = fdata.get('language', 'unknown')

                # Code smells: prefer the detailed list from insights, fall back to quality_metrics
                detailed_smells = insights_data.get('code_smells', [])
                if not isinstance(detailed_smells, list):
                    detailed_smells = []
                qm_smells = qm.get('code_smells', [])
                if not isinstance(qm_smells, list):
                    qm_smells = []
                # Use whichever has content; prefer detailed
                smells_to_use = detailed_smells if detailed_smells else qm_smells

                security = qm.get('security_issues', [])
                if not isinstance(security, list):
                    security = []

                block.append(
                    f"\nFile: {fname} ({lang}) — "
                    f"Maintainability: {qm.get('maintainability', 'N/A')}/10 | "
                    f"Complexity: {qm.get('complexity', 'N/A')} | "
                    f"Code smells: {len(smells_to_use)} | "
                    f"Security issues: {len(security)}"
                )

                for smell in smells_to_use[:5]:
                    if isinstance(smell, dict):
                        name = smell.get('smell', smell.get('type', str(smell)))
                        severity = smell.get('severity', '')
                        desc = smell.get('description', '')
                        block.append(f"  - Smell: {name} [Severity: {severity}] — {desc}")
                    elif isinstance(smell, str) and smell:
                        block.append(f"  - Smell: {smell}")

                for issue in security[:3]:
                    if isinstance(issue, dict):
                        block.append(f"  - Security: {issue.get('issue', issue.get('type', str(issue)))}")
                    elif isinstance(issue, str) and issue:
                        block.append(f"  - Security: {issue}")

        context_blocks.append('\n'.join(block))

    if not context_blocks:
        return jsonify({'error': 'None of the selected analyses could be loaded or you do not have access.'}), 403

    system_prompt = (
        "You are an expert software architect and code reviewer. "
        "You have been given structured analysis data about one or more codebases. "
        "Answer the user's question accurately and concisely, grounded only in the data provided. "
        "If the data does not contain enough information to answer, say so clearly. "
        "Format your response with clear structure — use short paragraphs or bullet points where appropriate.\n\n"
        "=== ANALYSIS DATA ===\n\n"
        + "\n\n".join(context_blocks)
    )

    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OpenAI API key is not configured.'}), 500
        client = OpenAI(api_key=api_key, timeout=60.0)
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': message},
            ],
            max_tokens=1500,
            temperature=0.4,
        )
        reply = completion.choices[0].message.content.strip()
        return jsonify({'response': reply})
    except Exception as exc:
        logging.error(f'Chat route OpenAI error: {exc}')
        return jsonify({'error': 'The AI service encountered an error. Please try again.'}), 500


def _can_access_system(system):
    """Check if current user may view/edit this system."""
    if current_user.is_admin():
        return True
    if system.user_id == current_user.id:
        return True
    return False


@main_bp.route('/systems')
@login_required
def systems_list():
    """List all systems accessible to the current user."""
    systems = System.query.filter_by(user_id=current_user.id)\
        .order_by(System.created_at.desc()).all()

    return render_template('systems/list.html', systems=systems)


@main_bp.route('/systems/new', methods=['GET', 'POST'])
@login_required
def create_system():
    """Create a new system record."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        selected_ids = request.form.getlist('analysis_ids')

        if not name:
            flash('System name is required.', 'error')
            return redirect(url_for('main.create_system'))

        system = System(
            name=name,
            description=description or None,
            user_id=current_user.id,
            company_id=current_user.company_id,
        )
        db.session.add(system)
        db.session.flush()

        for aid in selected_ids:
            try:
                aid_int = int(aid)
            except (ValueError, TypeError):
                continue
            analysis = db.session.get(Analysis, aid_int)
            if analysis and analysis.status == 'completed' and _can_view_analysis(analysis):
                sr = SystemRepo(system_id=system.id, analysis_id=aid_int)
                db.session.add(sr)

        db.session.commit()
        flash(f'System "{name}" created successfully.', 'success')
        return redirect(url_for('main.view_system', system_id=system.id))

    available_analyses = _get_available_analyses()
    return render_template('systems/create.html', available_analyses=available_analyses, system=None)


@main_bp.route('/systems/<int:system_id>')
@login_required
def view_system(system_id):
    """View a system and its analysis results."""
    system = db.session.get(System, system_id)
    if not system:
        abort(404)
    if not _can_access_system(system):
        abort(403)

    latest = system.latest_analysis
    return render_template('systems/detail.html', system=system, latest_analysis=latest)


@main_bp.route('/systems/<int:system_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_system(system_id):
    """Edit a system record."""
    system = db.session.get(System, system_id)
    if not system:
        abort(404)
    if not _can_access_system(system):
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        selected_ids = request.form.getlist('analysis_ids')

        if not name:
            flash('System name is required.', 'error')
            return redirect(url_for('main.edit_system', system_id=system_id))

        system.name = name
        system.description = description or None

        existing_ids = {sr.analysis_id for sr in system.repos}
        new_ids = set()
        for aid in selected_ids:
            try:
                new_ids.add(int(aid))
            except (ValueError, TypeError):
                pass

        for aid in new_ids - existing_ids:
            analysis = db.session.get(Analysis, aid)
            if analysis and analysis.status == 'completed' and _can_view_analysis(analysis):
                db.session.add(SystemRepo(system_id=system.id, analysis_id=aid))

        for sr in list(system.repos):
            if sr.analysis_id not in new_ids:
                db.session.delete(sr)

        db.session.commit()
        flash('System updated successfully.', 'success')
        return redirect(url_for('main.view_system', system_id=system_id))

    available_analyses = _get_available_analyses()
    linked_ids = {sr.analysis_id for sr in system.repos}
    return render_template(
        'systems/create.html',
        system=system,
        available_analyses=available_analyses,
        linked_ids=linked_ids,
    )


@main_bp.route('/systems/<int:system_id>/delete', methods=['POST'])
@login_required
def delete_system(system_id):
    """Delete a system."""
    system = db.session.get(System, system_id)
    if not system:
        abort(404)
    if not _can_access_system(system):
        abort(403)
    db.session.delete(system)
    db.session.commit()
    flash('System deleted.', 'success')
    return redirect(url_for('main.systems_list'))


@main_bp.route('/systems/<int:system_id>/analyse', methods=['POST'])
@login_required
def run_system_analysis(system_id):
    """Trigger a system-level analysis in a background thread."""
    system = db.session.get(System, system_id)
    if not system:
        abort(404)
    if not _can_access_system(system):
        abort(403)

    if not system.repos:
        flash('Add at least one repo to the system before running analysis.', 'error')
        return redirect(url_for('main.view_system', system_id=system_id))

    running = SystemAnalysis.query.filter_by(system_id=system_id, status='running').first()
    if running:
        flash('An analysis is already running for this system.', 'info')
        return redirect(url_for('main.view_system', system_id=system_id))

    import threading
    from system_analyzer import run_system_analysis as _run

    app = current_app._get_current_object()

    def _worker():
        with app.app_context():
            _run(system_id)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    flash('System analysis started — results will appear shortly.', 'info')
    return redirect(url_for('main.view_system', system_id=system_id))


@main_bp.route('/systems/<int:system_id>/analysis-status')
@login_required
def system_analysis_status(system_id):
    """Poll endpoint returning the latest analysis status."""
    system = db.session.get(System, system_id)
    if not system or not _can_access_system(system):
        return jsonify({'status': 'error'}), 403

    latest = system.latest_analysis
    if not latest:
        return jsonify({'status': 'none'})

    payload = {
        'status': latest.status,
        'id': latest.id,
        'created_at': latest.created_at.isoformat(),
    }
    if latest.status == 'completed' and latest.summary:
        payload['summary'] = latest.summary
    return jsonify(payload)


@main_bp.route('/systems/<int:system_id>/graph')
@login_required
def system_graph(system_id):
    """System-level relationship graph."""
    system = db.session.get(System, system_id)
    if not system:
        abort(404)
    if not _can_access_system(system):
        abort(403)

    latest = system.latest_analysis
    return render_template('systems/graph.html', system=system, latest_analysis=latest)


@main_bp.route('/systems/<int:system_id>/graph-data')
@login_required
def system_graph_data(system_id):
    """Return JSON graph data for the system graph view."""
    system = db.session.get(System, system_id)
    if not system or not _can_access_system(system):
        return jsonify({'nodes': [], 'edges': [], 'metadata': {}}), 403

    latest = system.latest_analysis
    if not latest or not latest.graph_data:
        return jsonify({'nodes': [], 'edges': [], 'metadata': {}})

    return jsonify(latest.graph_data)


@main_bp.route('/systems/<int:system_id>/node-findings')
@login_required
def system_node_findings(system_id):
    """Return system-level finding detail for a node in the system graph."""
    import re as _re

    def _norm(s):
        return _re.sub(r'[^a-z0-9]', '', (s or '').lower())

    system = db.session.get(System, system_id)
    if not system or not _can_access_system(system):
        return jsonify({'error': 'Permission denied'}), 403

    label     = request.args.get('label', '').strip()
    node_type = request.args.get('node_type', '').strip()
    tag       = request.args.get('system_tag', '').strip()
    file_path = request.args.get('file', '').strip()

    if not label or not tag:
        return jsonify({'found': False, 'tag': tag, 'finding': None}), 200

    latest = system.latest_analysis
    if not latest:
        return jsonify({'found': False, 'tag': tag, 'finding': None}), 200

    norm_label = _norm(label)

    if tag == 'duplicate':
        if node_type == 'function':
            for entry in (latest.duplicate_functions or []):
                if _norm(entry.get('function_name', '')) == norm_label:
                    return jsonify({'found': True, 'tag': tag, 'finding': entry})
        elif node_type in ('class', 'service'):
            for entry in (latest.duplicate_services or []):
                if _norm(entry.get('service_name', '')) == norm_label:
                    return jsonify({'found': True, 'tag': tag, 'finding': entry})
        else:
            for entry in (latest.duplicate_functions or []):
                if _norm(entry.get('function_name', '')) == norm_label:
                    return jsonify({'found': True, 'tag': tag, 'finding': entry})
            for entry in (latest.duplicate_services or []):
                if _norm(entry.get('service_name', '')) == norm_label:
                    return jsonify({'found': True, 'tag': tag, 'finding': entry})

    elif tag == 'common_pattern':
        for entry in (latest.common_patterns or []):
            if _norm(entry.get('pattern', '')) == norm_label:
                return jsonify({'found': True, 'tag': tag, 'finding': entry})
        if node_type == 'class':
            for entry in (latest.common_patterns or []):
                for cls in entry.get('classes', []):
                    if _norm(cls.get('class', '')) == norm_label:
                        return jsonify({'found': True, 'tag': tag, 'finding': entry})
        norm_parts = set(_norm(p) for p in label.replace('/', ' ').split() if len(_norm(p)) > 2)
        for entry in (latest.common_patterns or []):
            if _norm(entry.get('pattern', '')) in norm_parts:
                return jsonify({'found': True, 'tag': tag, 'finding': entry})

    elif tag == 'cross_api':
        label_parts = set(
            _norm(p) for p in label.replace('/', ' ').split()
            if len(_norm(p)) > 2
        )
        for entry in (latest.cross_repo_apis or []):
            if _norm(entry.get('shared_segment', '')) in label_parts:
                return jsonify({'found': True, 'tag': tag, 'finding': entry})

    elif tag == 'smell_hotspot':
        matched_smells = []
        basename = file_path.split('/')[-1] if file_path else ''
        for smell in (latest.aggregated_smells or []):
            matched_examples = [
                ex for ex in smell.get('examples', [])
                if file_path and (
                    ex.get('file') == file_path
                    or (basename and ex.get('file', '').endswith('/' + basename))
                )
            ]
            if matched_examples:
                matched_smells.append({
                    'smell': smell.get('smell'),
                    'examples': matched_examples,
                })
        if matched_smells:
            return jsonify({'found': True, 'tag': tag, 'finding': {'smells': matched_smells}})

    return jsonify({'found': False, 'tag': tag, 'finding': None})


@main_bp.route('/systems/<int:system_id>/node-insights')
@login_required
def system_node_insights(system_id):
    """Return AI insights for a node in the system graph."""
    system = db.session.get(System, system_id)
    if not system or not _can_access_system(system):
        return jsonify({'error': 'Permission denied'}), 403

    filename = request.args.get('file', '')
    analysis_id_str = request.args.get('analysis_id', '')

    if not filename or not analysis_id_str:
        return jsonify({'error': 'Missing file or analysis_id parameter'}), 400

    try:
        analysis_id = int(analysis_id_str)
    except ValueError:
        return jsonify({'error': 'Invalid analysis_id'}), 400

    linked_analysis_ids = {sr.analysis_id for sr in system.repos}
    if analysis_id not in linked_analysis_ids:
        return jsonify({'error': 'Analysis does not belong to this system'}), 403

    analysis = Analysis.query.get_or_404(analysis_id)
    if not _can_view_analysis(analysis):
        return jsonify({'error': 'Permission denied'}), 403

    result = {
        'what_it_does': None,
        'observations': [],
        'recommendations': [],
        'code_quality_score': None,
        'complexity_level': None,
        'performance_notes': None,
        'function_count': None,
        'language': None,
    }

    if analysis.ai_insights and isinstance(analysis.ai_insights, dict):
        file_analyses = analysis.ai_insights.get('file_analyses', {})
        file_data = file_analyses.get(filename, {})
        inner = file_data.get('analysis', {})
        if isinstance(inner, dict):
            analysis_data = inner.get('analysis', {})
            if isinstance(analysis_data, dict):
                result['what_it_does'] = analysis_data.get('what_it_does')
                result['observations'] = analysis_data.get('observations', [])
                result['recommendations'] = analysis_data.get('recommendations', [])
                result['code_quality_score'] = analysis_data.get('code_quality_score')
                result['complexity_level'] = analysis_data.get('complexity_level')
                result['performance_notes'] = analysis_data.get('performance_notes')

    if analysis.analysis_results and isinstance(analysis.analysis_results, dict):
        ar_file = analysis.analysis_results.get(filename, {})
        if isinstance(ar_file, dict):
            ar_funcs = ar_file.get('functions', [])
            if isinstance(ar_funcs, list):
                result['function_count'] = len(ar_funcs)
            ar_lang = ar_file.get('language')
            if ar_lang:
                result['language'] = ar_lang

    basename = filename.split('/')[-1]
    cf = CodeFile.query.filter_by(analysis_id=analysis_id, filename=filename).first()
    if not cf:
        cf = CodeFile.query.filter_by(analysis_id=analysis_id, filename=basename).first()
    if not cf:
        cf = CodeFile.query.filter_by(analysis_id=analysis_id, file_path=filename).first()

    if cf:
        if result['function_count'] is None:
            funcs = cf.functions
            result['function_count'] = len(funcs) if isinstance(funcs, list) else 0
        if not result['language']:
            result['language'] = cf.language

    return jsonify(result)


def _get_available_analyses():
    """Return completed analyses the current user may link to a system."""
    if current_user.company_id:
        return Analysis.query.filter(
            Analysis.status == 'completed',
            (Analysis.user_id == current_user.id) |
            ((Analysis.company_id == current_user.company_id) & (Analysis.is_shared == True))
        ).order_by(Analysis.created_at.desc()).all()
    return Analysis.query.filter_by(
        user_id=current_user.id, status='completed'
    ).order_by(Analysis.created_at.desc()).all()
