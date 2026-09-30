"""
System Analyzer — Cross-Repo Analysis Engine

Reads existing per-repo CodeFile records and computes:
  a. Duplicate functions / services across repos
  b. Common structural / architectural patterns
  c. Cross-repo API communication (shared endpoint patterns)
  d. Aggregated code smells ranked by frequency and severity
  e. A unified system-level graph combining all repo graphs

Results are persisted into a SystemAnalysis record.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SYSTEM_NODE_COLORS = {
    "duplicate": "#f59e0b",
    "common_pattern": "#06b6d4",
    "cross_api": "#14b8a6",
    "smell_hotspot": "#ef4444",
    "repo": "#23a5da",
    "file": "#4e9af1",
    "class": "#f97316",
    "function": "#22c55e",
    "api_endpoint": "#a855f7",
    "package": "#64748b",
}


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_GENERIC_STRIP_RE = re.compile(r"[\[<][^\]>]*[\]>]")
_PATH_PARAM_RE = re.compile(r"\{[^}]+\}|:[a-zA-Z_]\w*")


def _normalise_endpoint_path(url: str) -> str:
    """Normalise a URL/path for cross-repo call matching.

    - Strips protocol + domain (http://host)
    - Strips query string
    - Replaces path params ({id}, :id) with *
    - Lowercases and strips trailing slash
    """
    url = re.sub(r"^https?://[^/]+", "", url)
    url = url.split("?")[0]
    url = _PATH_PARAM_RE.sub("*", url)
    return url.rstrip("/").lower() or "/"


def _strip_generics(name: str) -> str:
    """Strip generic/template type parameters from a class name before normalisation.

    Handles angle-bracket generics (C#, Java, Kotlin, TypeScript, Rust, Swift)
    and square-bracket generics (Go 1.18+, Swift Array[T] style).
    Examples: Result<T> -> Result, Vec<String, E> -> Vec, Slice[T] -> Slice
    """
    return _GENERIC_STRIP_RE.sub("", name).strip()


def _normalise_params(params: Any) -> str:
    """Produce a canonical string from a function's parameter list for signature matching."""
    if not params:
        return ""
    if isinstance(params, str):
        parts = [p.strip().split(":")[0].split("=")[0].strip() for p in params.split(",") if p.strip()]
        return ",".join(p for p in parts if p not in ("self", "cls", "this", ""))
    if isinstance(params, list):
        normalised = []
        for p in params:
            if isinstance(p, dict):
                pname = p.get("name", p.get("param", "")).split(":")[0].split("=")[0].strip()
            else:
                pname = str(p).strip().split(":")[0].split("=")[0].strip()
            if pname and pname not in ("self", "cls", "this"):
                normalised.append(_normalise(pname))
        return ",".join(normalised)
    return ""


def _find_duplicate_functions(
    repo_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return functions that appear in more than one repo, matched by name AND parameter signature."""
    func_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for repo in repo_data:
        analysis_name = repo["name"]
        for cf in repo["code_files"]:
            for func in cf.get("functions") or []:
                if not isinstance(func, dict):
                    continue
                name = func.get("name", "").strip()
                if not name or name.startswith("_"):
                    continue
                params_key = _normalise_params(func.get("parameters") or func.get("params") or [])
                name_key = _normalise(name)
                sig_key = f"{name_key}|{params_key}"
                func_map[sig_key].append(
                    {
                        "name": name,
                        "repo": analysis_name,
                        "file": cf["filename"],
                        "line": func.get("line", 0),
                        "parameters": func.get("parameters") or func.get("params") or [],
                        "return_type": func.get("return_type", ""),
                        "match_type": "exact_signature" if params_key else "name_only",
                    }
                )

    name_only_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    duplicates = []
    seen_sig_keys: set = set()

    for sig_key, occurrences in func_map.items():
        repos_seen = {o["repo"] for o in occurrences}
        if len(repos_seen) > 1:
            duplicates.append(
                {
                    "function_name": occurrences[0]["name"],
                    "occurrences": occurrences,
                    "repo_count": len(repos_seen),
                    "repos": sorted(repos_seen),
                    "match_type": occurrences[0].get("match_type", "name_only"),
                }
            )
            seen_sig_keys.add(_normalise(occurrences[0]["name"]))

    for sig_key, occurrences in func_map.items():
        name_key = sig_key.split("|")[0]
        name_only_map[name_key].extend(occurrences)

    for name_key, occurrences in name_only_map.items():
        if name_key in seen_sig_keys:
            continue
        repos_seen = {o["repo"] for o in occurrences}
        if len(repos_seen) > 1:
            duplicates.append(
                {
                    "function_name": occurrences[0]["name"],
                    "occurrences": occurrences,
                    "repo_count": len(repos_seen),
                    "repos": sorted(repos_seen),
                    "match_type": "name_only",
                }
            )

    duplicates.sort(key=lambda d: (-d["repo_count"], d.get("match_type", "") != "exact_signature"))
    return duplicates


def _find_duplicate_services(
    repo_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return class / service names that appear in more than one repo."""
    class_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for repo in repo_data:
        analysis_name = repo["name"]
        for cf in repo["code_files"]:
            for cls in cf.get("classes") or []:
                if not isinstance(cls, dict):
                    continue
                name = cls.get("name", "").strip()
                if not name:
                    continue
                key = _normalise(_strip_generics(name))
                class_map[key].append(
                    {
                        "name": name,
                        "repo": analysis_name,
                        "file": cf["filename"],
                        "line": cls.get("line", 0),
                    }
                )

    duplicates = []
    for key, occurrences in class_map.items():
        repos_seen = {o["repo"] for o in occurrences}
        if len(repos_seen) > 1:
            duplicates.append(
                {
                    "service_name": occurrences[0]["name"],
                    "occurrences": occurrences,
                    "repo_count": len(repos_seen),
                    "repos": sorted(repos_seen),
                }
            )

    duplicates.sort(key=lambda d: -d["repo_count"])
    return duplicates


def _find_common_patterns(
    repo_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Find common structural/architectural patterns across repos.

    Detects:
    1. Shared dependency imports (same module used in multiple repos)
    2. Class hierarchy clusters (classes sharing a common base class across repos)
    """
    import_map: Dict[str, List[str]] = defaultdict(list)
    base_class_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for repo in repo_data:
        analysis_name = repo["name"]
        repo_imports: set = set()
        for cf in repo["code_files"]:
            for imp in cf.get("imports") or []:
                if not isinstance(imp, dict):
                    continue
                module = imp.get("module") or imp.get("name", "")
                if module and not module.startswith("."):
                    root_module = module.split(".")[0]
                    repo_imports.add(root_module)

            for cls in cf.get("classes") or []:
                if not isinstance(cls, dict):
                    continue
                bases = cls.get("base_classes") or cls.get("bases") or cls.get("parent_class") or []
                if isinstance(bases, str):
                    bases = [bases]
                for base in bases:
                    if not base or base in ("object", "Object", "Base"):
                        continue
                    base_key = _normalise(base)
                    if len(base_key) > 2:
                        base_class_map[base_key].append(
                            {
                                "base": base,
                                "class": cls.get("name", ""),
                                "repo": analysis_name,
                                "file": cf["filename"],
                            }
                        )

        for module in repo_imports:
            import_map[module].append(analysis_name)

    patterns = []

    for module, repos in import_map.items():
        repos_unique = sorted(set(repos))
        if len(repos_unique) > 1:
            patterns.append(
                {
                    "pattern": module,
                    "type": "shared_dependency",
                    "repos": repos_unique,
                    "repo_count": len(repos_unique),
                }
            )

    for base_key, entries in base_class_map.items():
        repos_seen = {e["repo"] for e in entries}
        if len(repos_seen) > 1:
            patterns.append(
                {
                    "pattern": entries[0]["base"],
                    "type": "class_hierarchy",
                    "repos": sorted(repos_seen),
                    "repo_count": len(repos_seen),
                    "classes": [
                        {"class": e["class"], "repo": e["repo"], "file": e["file"]}
                        for e in entries
                    ],
                }
            )

    patterns.sort(key=lambda p: (-p["repo_count"], p["type"] != "class_hierarchy"))
    return patterns[:50]


_AUTH_PATTERNS = {
    "bearer": re.compile(r"\b(bearer|jwt|token|authorization)\b", re.I),
    "api_key": re.compile(r"\b(api[_\-]?key|x-api-key|apikey)\b", re.I),
    "basic": re.compile(r"\b(basic[_\-]auth|basic)\b", re.I),
    "oauth": re.compile(r"\b(oauth|oauth2|openid)\b", re.I),
    "session": re.compile(r"\b(session|cookie|csrf)\b", re.I),
}


def _detect_auth_scheme(api: Dict[str, Any]) -> Optional[str]:
    """Heuristically detect auth scheme from API metadata."""
    haystack = " ".join(
        str(api.get(k, ""))
        for k in ("auth", "security", "headers", "description", "middleware", "decorator")
    ).lower()
    for scheme, pattern in _AUTH_PATTERNS.items():
        if pattern.search(haystack):
            return scheme
    return None


def _normalise_method(method: str) -> str:
    m = method.upper().strip()
    return m if m in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS") else "GET"


def _find_cross_repo_apis(
    repo_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Match API endpoints across repos.

    Three matching strategies:
    1. path_segment — same URL segment declared as an endpoint in two or more repos.
    2. provider_consumer — endpoint declared in one repo (provider) and called via an
       HTTP client in a different repo (consumer).  Uses the ``http_calls`` field
       extracted alongside ``apis`` during per-file AI analysis.
    3. method_auth_payload — same HTTP method + auth scheme + payload shape across repos.
    """
    segment_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    consumer_segment_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    method_auth_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for repo in repo_data:
        analysis_name = repo["name"]
        for cf in repo["code_files"]:
            # --- declared API endpoints (provider side) ---
            for api in cf.get("apis") or []:
                if not isinstance(api, dict):
                    continue
                path = api.get("path") or api.get("endpoint") or api.get("name", "")
                method = _normalise_method(api.get("method", "GET"))
                if not path:
                    continue

                auth = _detect_auth_scheme(api)
                payload_keys = sorted(
                    _normalise(k)
                    for k in (api.get("request_body") or api.get("payload") or api.get("body") or {})
                    if isinstance(k, str)
                )
                payload_sig = ",".join(payload_keys) if payload_keys else ""

                parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
                entry = {
                    "path": path,
                    "method": method,
                    "auth": auth,
                    "payload_sig": payload_sig,
                    "repo": analysis_name,
                    "file": cf["filename"],
                    "role": "provider",
                }

                for part in parts:
                    key = _normalise(part)
                    if len(key) > 2:
                        segment_map[key].append(dict(entry, segment=part))

                ma_key = f"{method}|{auth or 'none'}"
                if payload_sig:
                    ma_key = f"{ma_key}|{payload_sig[:60]}"
                method_auth_map[ma_key].append(entry)

            # --- outbound HTTP client calls (consumer side) ---
            for call in cf.get("http_calls") or []:
                if not isinstance(call, dict):
                    continue
                path = call.get("path") or call.get("url") or call.get("endpoint", "")
                if not path:
                    continue
                method = _normalise_method(call.get("method", "GET"))
                parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
                entry = {
                    "path": path,
                    "method": method,
                    "auth": None,
                    "payload_sig": "",
                    "repo": analysis_name,
                    "file": cf["filename"],
                    "role": "consumer",
                }
                for part in parts:
                    key = _normalise(part)
                    if len(key) > 2:
                        consumer_segment_map[key].append(dict(entry, segment=part))

    matches = []
    seen_keys: set = set()

    # Strategy 1 — path_segment (provider endpoints shared across repos)
    for key, endpoints in segment_map.items():
        repos_seen = {e["repo"] for e in endpoints}
        if len(repos_seen) > 1 and key not in seen_keys:
            seen_keys.add(key)
            auth_schemes = list({e["auth"] for e in endpoints if e["auth"]})
            matches.append(
                {
                    "shared_segment": endpoints[0].get("segment", key),
                    "match_type": "path_segment",
                    "auth_schemes": auth_schemes,
                    "endpoints": endpoints,
                    "repo_count": len(repos_seen),
                    "repos": sorted(repos_seen),
                }
            )

    # Strategy 2 — provider_consumer (endpoint in one repo called from another)
    for key, providers in segment_map.items():
        if key not in consumer_segment_map:
            continue
        consumers = consumer_segment_map[key]
        provider_repos = {e["repo"] for e in providers}
        consumer_repos = {e["repo"] for e in consumers}
        # Require at least one provider repo that differs from consumer repos
        cross_provider_repos = provider_repos - consumer_repos
        if not cross_provider_repos:
            continue
        cross_repos = provider_repos | consumer_repos
        if key in seen_keys:
            continue
        seen_keys.add(key)
        all_entries = providers + consumers
        auth_schemes = list({e["auth"] for e in providers if e["auth"]})
        matches.append(
            {
                "shared_segment": providers[0].get("segment", key),
                "match_type": "provider_consumer",
                "auth_schemes": auth_schemes,
                "endpoints": all_entries,
                "repo_count": len(cross_repos),
                "repos": sorted(cross_repos),
            }
        )

    # Strategy 3 — method_auth_payload
    for ma_key, endpoints in method_auth_map.items():
        repos_seen = {e["repo"] for e in endpoints}
        if len(repos_seen) < 2:
            continue
        parts = ma_key.split("|")
        method_val = parts[0]
        auth_val = parts[1] if len(parts) > 1 else None
        payload_val = parts[2] if len(parts) > 2 else None
        if not (auth_val and auth_val != "none") and not payload_val:
            continue
        label = f"{method_val} + {auth_val}" if auth_val and auth_val != "none" else method_val
        if payload_val:
            label += f" + payload({payload_val[:30]})"
        matches.append(
            {
                "shared_segment": label,
                "match_type": "method_auth_payload",
                "auth_schemes": [auth_val] if auth_val and auth_val != "none" else [],
                "endpoints": endpoints,
                "repo_count": len(repos_seen),
                "repos": sorted(repos_seen),
            }
        )

    matches.sort(key=lambda m: -m["repo_count"])
    return matches[:40]


def _aggregate_smells(
    repo_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Aggregate code smells across all repos, ranked by frequency.

    Prefers the rich smell objects from ``ai_smells`` (extracted from
    ``Analysis.ai_insights``, the same source as the per-repo Code Smells tab).
    Falls back to ``CodeFile.quality_metrics.code_smells`` only when no
    ``ai_smells`` key is present on the repo entry.
    """
    smell_counts: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "high": 0, "medium": 0, "low": 0, "repos": set(), "examples": []}
    )

    for repo in repo_data:
        analysis_name = repo["name"]

        ai_smells = repo.get("ai_smells", [])
        if repo.get("has_ai_smells_source", False):
            for smell in ai_smells:
                if not isinstance(smell, dict):
                    continue
                name = smell.get("smell") or smell.get("name", "Unknown")
                sev = smell.get("severity", "Medium")
                key = _normalise(name)[:40]
                smell_counts[key]["count"] += 1
                smell_counts[key]["repos"].add(analysis_name)
                sev_key = sev.lower() if sev.lower() in ("high", "medium", "low") else "medium"
                smell_counts[key][sev_key] += 1
                if len(smell_counts[key]["examples"]) < 3:
                    smell_counts[key]["examples"].append(
                        {
                            "repo": analysis_name,
                            "file": smell.get("file", ""),
                            "description": smell.get("description", name),
                            "severity": sev,
                            "line": smell.get("line"),
                            "impact": smell.get("impact", ""),
                        }
                    )
                if not smell_counts[key].get("display_name"):
                    smell_counts[key]["display_name"] = name
        else:
            for cf in repo["code_files"]:
                qm = cf.get("quality_metrics") or {}
                smells = qm.get("code_smells", [])
                if not isinstance(smells, list):
                    continue
                for smell in smells:
                    if isinstance(smell, dict):
                        name = smell.get("smell") or smell.get("name", "Unknown")
                        sev = smell.get("severity", "Medium")
                    elif isinstance(smell, str):
                        name = smell
                        sev = "Medium"
                    else:
                        continue
                    key = _normalise(name)[:40]
                    smell_counts[key]["count"] += 1
                    smell_counts[key]["repos"].add(analysis_name)
                    sev_key = sev.lower() if sev.lower() in ("high", "medium", "low") else "medium"
                    smell_counts[key][sev_key] += 1
                    if len(smell_counts[key]["examples"]) < 3:
                        smell_counts[key]["examples"].append(
                            {
                                "repo": analysis_name,
                                "file": cf["filename"],
                                "description": (
                                    smell.get("description", name)
                                    if isinstance(smell, dict)
                                    else name
                                ),
                                "severity": sev,
                                "line": smell.get("line") if isinstance(smell, dict) else None,
                                "impact": smell.get("impact", "") if isinstance(smell, dict) else "",
                            }
                        )
                    if not smell_counts[key].get("display_name"):
                        smell_counts[key]["display_name"] = name

    result = []
    for key, data in smell_counts.items():
        result.append(
            {
                "smell": data.get("display_name", key),
                "total_count": data["count"],
                "high_count": data["high"],
                "medium_count": data["medium"],
                "low_count": data["low"],
                "repo_count": len(data["repos"]),
                "repos": sorted(data["repos"]),
                "examples": data["examples"],
            }
        )

    result.sort(key=lambda s: (-s["high_count"], -s["total_count"]))
    return result[:30]


def _build_system_graph(
    repo_data: List[Dict[str, Any]],
    duplicate_functions: List[Dict],
    duplicate_services: List[Dict],
    cross_repo_apis: List[Dict],
    aggregated_smells: List[Dict],
    common_patterns: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Build a unified graph from all repo graph_data with semantic colouring."""
    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []
    edge_set: set = set()
    edge_counter = 0

    dup_func_names = {
        _normalise(d["function_name"]) for d in duplicate_functions
    }
    dup_service_names = {
        _normalise(_strip_generics(d["service_name"])) for d in duplicate_services
    }
    cross_api_segments = {
        _normalise(m["shared_segment"]) for m in cross_repo_apis
    }

    shared_dep_names: set = set()
    hierarchy_class_names: set = set()
    if common_patterns:
        for p in common_patterns:
            if p.get("type") == "shared_dependency":
                shared_dep_names.add(_normalise(p["pattern"]))
            elif p.get("type") == "class_hierarchy":
                for cls_entry in p.get("classes", []):
                    hierarchy_class_names.add(_normalise(cls_entry.get("class", "")))

    smell_hotspot_files: set = set()
    for smell in aggregated_smells[:10]:
        for ex in smell.get("examples", []):
            fname = ex.get("file", "")
            if fname:
                smell_hotspot_files.add(fname)

    for repo in repo_data:
        analysis_id = repo["analysis_id"]
        analysis_name = repo["name"]
        gd = repo.get("graph_data") or {}
        repo_nodes = gd.get("nodes", [])
        repo_edges = gd.get("edges", [])

        repo_node_id = f"repo::{analysis_id}"
        nodes[repo_node_id] = {
            "id": repo_node_id,
            "label": analysis_name,
            "type": "repo",
            "file": "",
            "degree": 0,
            "color": SYSTEM_NODE_COLORS["repo"],
            "system_tags": ["repo"],
            "metadata": {"analysis_id": analysis_id},
        }

        id_map: Dict[str, str] = {}

        for node in repo_nodes:
            orig_id = node.get("id", "")
            new_id = f"r{analysis_id}::{orig_id}"
            id_map[orig_id] = new_id

            label = node.get("label", "")
            ntype = node.get("type", "file")
            norm_label = _normalise(label)

            system_tags = []
            color = node.get("color", SYSTEM_NODE_COLORS.get(ntype, "#94a3b8"))

            if ntype == "function" and norm_label in dup_func_names:
                color = SYSTEM_NODE_COLORS["duplicate"]
                system_tags.append("duplicate")
            elif ntype == "class":
                norm_label_stripped = _normalise(_strip_generics(label))
                if norm_label_stripped in dup_service_names:
                    color = SYSTEM_NODE_COLORS["duplicate"]
                    system_tags.append("duplicate")
                elif norm_label in hierarchy_class_names:
                    color = SYSTEM_NODE_COLORS["common_pattern"]
                    system_tags.append("common_pattern")
            elif ntype == "package" and norm_label in shared_dep_names:
                color = SYSTEM_NODE_COLORS["common_pattern"]
                system_tags.append("common_pattern")
            elif ntype == "api_endpoint":
                parts = [
                    _normalise(p)
                    for p in label.replace("/", " ").split()
                    if len(_normalise(p)) > 2
                ]
                if any(p in cross_api_segments for p in parts):
                    color = SYSTEM_NODE_COLORS["cross_api"]
                    system_tags.append("cross_api")
            elif ntype == "file":
                node_file = node.get("file", "") or label
                if node_file in smell_hotspot_files:
                    color = SYSTEM_NODE_COLORS["smell_hotspot"]
                    system_tags.append("smell_hotspot")

            new_node = dict(node)
            new_node["id"] = new_id
            new_node["color"] = color
            new_node["system_tags"] = system_tags
            new_node["repo"] = analysis_name
            new_node["degree"] = 0
            node_meta = dict(node.get("metadata") or {})
            node_meta["analysis_id"] = analysis_id
            new_node["metadata"] = node_meta
            nodes[new_id] = new_node

            if ntype == "file":
                ek = (repo_node_id, new_id, "contains")
                if ek not in edge_set:
                    edge_set.add(ek)
                    edges.append(
                        {
                            "id": f"e{edge_counter}",
                            "source": repo_node_id,
                            "target": new_id,
                            "type": "contains",
                            "color": "#334155",
                        }
                    )
                    edge_counter += 1

        for edge in repo_edges:
            src = id_map.get(edge.get("source", ""), "")
            tgt = id_map.get(edge.get("target", ""), "")
            etype = edge.get("type", "contains")
            if not src or not tgt:
                continue
            ek = (src, tgt, etype)
            if ek in edge_set:
                continue
            edge_set.add(ek)
            edges.append(
                {
                    "id": f"e{edge_counter}",
                    "source": src,
                    "target": tgt,
                    "type": etype,
                    "color": edge.get("color", "#94a3b8"),
                }
            )
            edge_counter += 1

    # Build lookup: (normalised_method, normalised_path) -> [(node_id, analysis_id)]
    # Also keep a path-only fallback for api_endpoint nodes where method is missing.
    endpoint_method_path_map: Dict[Tuple[str, str], List[Tuple[str, int]]] = {}
    endpoint_path_only_map: Dict[str, List[Tuple[str, int]]] = {}
    for node_id, node in nodes.items():
        if node.get("type") == "api_endpoint":
            label = node.get("label", "")
            parts = label.split(" ", 1)
            aid = node.get("metadata", {}).get("analysis_id")
            if len(parts) == 2:
                ep_method = parts[0].upper()
                norm_path = _normalise_endpoint_path(parts[1])
                key = (ep_method, norm_path)
                endpoint_method_path_map.setdefault(key, []).append((node_id, aid))
                endpoint_path_only_map.setdefault(norm_path, []).append((node_id, aid))
            elif len(parts) == 1 and parts[0]:
                norm_path = _normalise_endpoint_path(parts[0])
                endpoint_path_only_map.setdefault(norm_path, []).append((node_id, aid))

    file_node_map: Dict[Tuple[int, str], str] = {}
    for node_id, node in nodes.items():
        if node.get("type") == "file":
            aid = node.get("metadata", {}).get("analysis_id")
            fname = node.get("file", "") or node.get("label", "")
            if aid and fname:
                file_node_map[(aid, fname)] = node_id

    for repo in repo_data:
        analysis_id = repo["analysis_id"]
        for cf in repo.get("code_files", []):
            http_calls = cf.get("http_calls") or []
            if not http_calls:
                continue
            filename = cf.get("filename", "")
            caller_node_id = file_node_map.get((analysis_id, filename))
            if not caller_node_id:
                continue
            for call in http_calls:
                if not isinstance(call, dict):
                    continue
                raw_url = call.get("url", "")
                if not raw_url or raw_url in ("http://", "https://", "/"):
                    continue
                norm_url = _normalise_endpoint_path(raw_url)
                if norm_url == "/":
                    continue
                call_method = (call.get("method") or "").upper().strip()

                # Prefer method+path match to avoid false positives; fall back to
                # path-only when the call has no method recorded.
                if call_method:
                    candidates = endpoint_method_path_map.get((call_method, norm_url), [])
                    if not candidates:
                        candidates = endpoint_path_only_map.get(norm_url, [])
                else:
                    candidates = endpoint_path_only_map.get(norm_url, [])

                for (ep_node_id, ep_analysis_id) in candidates:
                    if ep_analysis_id == analysis_id:
                        continue
                    ek = (caller_node_id, ep_node_id, "cross_repo_call")
                    if ek in edge_set:
                        continue
                    edge_set.add(ek)
                    edges.append({
                        "id": f"e{edge_counter}",
                        "source": caller_node_id,
                        "target": ep_node_id,
                        "type": "cross_repo_call",
                        "color": "#06b6d4",
                    })
                    edge_counter += 1

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        if src in nodes:
            nodes[src]["degree"] = nodes[src].get("degree", 0) + 1
        if tgt in nodes:
            nodes[tgt]["degree"] = nodes[tgt].get("degree", 0) + 1

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "metadata": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "repo_count": len(repo_data),
        },
    }


def run_system_analysis(system_id: int) -> bool:
    """
    Main entry point.  Reads the System and all linked Analysis records,
    computes cross-repo findings, and persists a SystemAnalysis record.

    Returns True on success, False on failure.
    """
    from app import db
    from models import System, SystemAnalysis, CodeFile

    try:
        system = db.session.get(System, system_id)
        if not system:
            logger.error(f"System {system_id} not found")
            return False

        sa = SystemAnalysis(system_id=system_id, status="running")
        db.session.add(sa)
        db.session.commit()

        from graph_processor import generate_graph_data

        repo_data: List[Dict[str, Any]] = []
        for sr in system.repos:
            analysis = sr.analysis
            if not analysis or analysis.status != "completed":
                continue
            code_files = CodeFile.query.filter_by(analysis_id=analysis.id).all()
            cf_list = []
            for cf in code_files:
                cf_list.append(
                    {
                        "filename": cf.filename,
                        "file_path": cf.file_path,
                        "functions": cf.functions or [],
                        "classes": cf.classes or [],
                        "imports": cf.imports or [],
                        "apis": cf.apis or [],
                        "http_calls": cf.http_calls or [],
                        "quality_metrics": cf.quality_metrics or {},
                    }
                )

            ai_smells: List[Dict[str, Any]] = []
            has_ai_smells_source = False
            ai_insights = analysis.ai_insights or {}
            file_analyses = ai_insights.get("file_analyses", {}) if isinstance(ai_insights, dict) else {}
            if isinstance(file_analyses, dict) and file_analyses:
                has_ai_smells_source = True
                for filename, file_data in file_analyses.items():
                    if not isinstance(file_data, dict):
                        continue
                    inner = file_data.get("analysis", {})
                    if not isinstance(inner, dict) or inner.get("status") != "success":
                        continue
                    analysis_data = inner.get("analysis", {})
                    if not isinstance(analysis_data, dict):
                        continue
                    smells = analysis_data.get("code_smells", [])
                    if not isinstance(smells, list):
                        continue
                    for smell in smells:
                        if not isinstance(smell, dict):
                            continue
                        ai_smells.append(
                            {
                                "file": filename,
                                "smell": smell.get("smell") or smell.get("name", "Unknown"),
                                "severity": smell.get("severity", "Medium"),
                                "line": smell.get("line"),
                                "description": smell.get("description", ""),
                                "impact": smell.get("impact", ""),
                                "remediation": smell.get("remediation", ""),
                            }
                        )

            graph_d = analysis.graph_data
            if not graph_d and analysis.analysis_results:
                try:
                    graph_d = generate_graph_data(analysis.analysis_results, analysis.name)
                    analysis.graph_data = graph_d
                    db.session.add(analysis)
                    logger.info(f"Generated graph data on-the-fly for analysis {analysis.id}")
                except Exception as gde:
                    logger.warning(f"Could not generate graph data for analysis {analysis.id}: {gde}")
                    graph_d = {}

            repo_data.append(
                {
                    "analysis_id": analysis.id,
                    "name": analysis.name,
                    "code_files": cf_list,
                    "ai_smells": ai_smells,
                    "has_ai_smells_source": has_ai_smells_source,
                    "graph_data": graph_d or {},
                }
            )

        if not repo_data:
            sa.status = "failed"
            db.session.commit()
            logger.warning(f"System {system_id}: no completed repos to analyse")
            return False

        dup_functions = _find_duplicate_functions(repo_data)
        dup_services = _find_duplicate_services(repo_data)
        common_patterns = _find_common_patterns(repo_data)
        cross_apis = _find_cross_repo_apis(repo_data)
        agg_smells = _aggregate_smells(repo_data)
        graph_data = _build_system_graph(
            repo_data, dup_functions, dup_services, cross_apis, agg_smells, common_patterns
        )

        summary = {
            "repo_count": len(repo_data),
            "duplicate_functions": len(dup_functions),
            "duplicate_services": len(dup_services),
            "common_patterns": len(common_patterns),
            "cross_repo_api_matches": len(cross_apis),
            "total_aggregated_smells": sum(s["total_count"] for s in agg_smells),
            "smell_types": len(agg_smells),
        }

        sa.duplicate_functions = dup_functions
        sa.duplicate_services = dup_services
        sa.common_patterns = common_patterns
        sa.cross_repo_apis = cross_apis
        sa.aggregated_smells = agg_smells
        sa.graph_data = graph_data
        sa.summary = summary
        sa.status = "completed"
        sa.completed_at = datetime.utcnow()
        db.session.commit()

        logger.info(f"System {system_id} analysis complete — {summary}")
        return True

    except Exception as exc:
        logger.error(f"System analysis error for system {system_id}: {exc}", exc_info=True)
        try:
            db.session.rollback()
            from models import SystemAnalysis as SA
            sa_obj = SA.query.filter_by(system_id=system_id, status="running").first()
            if sa_obj:
                sa_obj.status = "failed"
                db.session.commit()
        except Exception:
            pass
        return False
