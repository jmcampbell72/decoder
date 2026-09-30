"""
Graph Processor for Codebase Relationship Visualisation
Builds a node/edge graph from existing analysis data (no additional AI calls).
"""

from typing import Dict, List, Any
from collections import defaultdict


ENTITY_COLORS = {
    "file": "#4e9af1",
    "class": "#f97316",
    "function": "#22c55e",
    "api_endpoint": "#a855f7",
    "package": "#64748b",
}

EDGE_COLORS = {
    "contains": "#94a3b8",
    "imports": "#64748b",
    "exposes": "#a855f7",
    "inherits": "#f97316",
}


class GraphProcessor:
    """Build a relationship graph from existing per-file analysis results."""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._edge_set: set = set()
        self._edge_counter: int = 0

    def process_analysis(self, analysis_results: Dict[str, Any], analysis_name: str) -> Dict[str, Any]:
        self._reset()

        for filename, file_data in analysis_results.items():
            if filename == "_summary" or not isinstance(file_data, dict) or file_data.get("error"):
                continue
            self._process_file(filename, file_data)

        self._compute_degrees()

        nodes_list = list(self.nodes.values())
        edges_list = self.edges

        node_type_counts: Dict[str, int] = defaultdict(int)
        for n in nodes_list:
            node_type_counts[n["type"]] += 1

        edge_type_counts: Dict[str, int] = defaultdict(int)
        for e in edges_list:
            edge_type_counts[e["type"]] += 1

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "metadata": {
                "analysis_name": analysis_name,
                "total_nodes": len(nodes_list),
                "total_edges": len(edges_list),
                "node_type_counts": dict(node_type_counts),
                "edge_type_counts": dict(edge_type_counts),
            },
        }

    def _reset(self):
        self.nodes = {}
        self.edges = []
        self._edge_set = set()
        self._edge_counter = 0

    def _node_id(self, entity_type: str, name: str) -> str:
        safe = name.replace('"', "'").replace(" ", "_")
        return f"{entity_type}::{safe}"

    def _add_node(self, node_id: str, label: str, entity_type: str,
                  file: str = "", metadata: Dict[str, Any] = None):
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "label": label,
                "type": entity_type,
                "file": file,
                "degree": 0,
                "color": ENTITY_COLORS.get(entity_type, "#94a3b8"),
                "metadata": metadata or {},
            }

    def _add_edge(self, source: str, target: str, edge_type: str):
        key = (source, target, edge_type)
        if key in self._edge_set:
            return
        self._edge_set.add(key)
        self.edges.append({
            "id": f"e{self._edge_counter}",
            "source": source,
            "target": target,
            "type": edge_type,
            "color": EDGE_COLORS.get(edge_type, "#94a3b8"),
        })
        self._edge_counter += 1

    def _process_file(self, filename: str, file_data: Dict[str, Any]):
        short_name = filename.split("/")[-1]
        file_node_id = self._node_id("file", filename)

        self._add_node(
            node_id=file_node_id,
            label=short_name,
            entity_type="file",
            file=filename,
            metadata={
                "full_path": filename,
                "language": file_data.get("language", "unknown"),
                "line_count": file_data.get("line_count", 0),
                "size_bytes": file_data.get("size_bytes", 0),
            },
        )

        self._process_imports(file_data.get("imports", []), file_node_id, filename)
        self._process_classes(file_data.get("classes", []), file_node_id, filename)
        self._process_functions(file_data.get("functions", []), file_node_id, filename)
        self._process_apis(file_data.get("apis", []), file_node_id, filename)

    def _process_imports(self, imports: List[Any], file_node_id: str, filename: str):
        for imp in imports:
            if not isinstance(imp, dict):
                continue
            module_name = imp.get("module") or imp.get("name", "")
            if not module_name:
                continue

            pkg_id = self._node_id("package", module_name)
            self._add_node(
                node_id=pkg_id,
                label=module_name,
                entity_type="package",
                file="",
                metadata={
                    "is_external": not module_name.startswith("."),
                    "import_type": imp.get("type", "import"),
                    "items": imp.get("items", []),
                },
            )
            self._add_edge(file_node_id, pkg_id, "imports")

    def _process_classes(self, classes: List[Any], file_node_id: str, filename: str):
        for cls in classes:
            if not isinstance(cls, dict):
                continue
            class_name = cls.get("name", "")
            if not class_name:
                continue

            cls_id = self._node_id("class", f"{filename}::{class_name}")
            self._add_node(
                node_id=cls_id,
                label=class_name,
                entity_type="class",
                file=filename,
                metadata={
                    "parent_class": cls.get("parent_class"),
                    "interfaces": cls.get("interfaces", []),
                    "is_abstract": cls.get("is_abstract", False),
                    "methods_count": len(cls.get("methods", [])),
                    "line_number": cls.get("line_number", 0),
                },
            )
            self._add_edge(file_node_id, cls_id, "contains")

            for method in cls.get("methods", []):
                if not isinstance(method, dict):
                    continue
                method_name = method.get("name", "")
                if not method_name:
                    continue
                m_id = self._node_id("function", f"{filename}::{class_name}::{method_name}")
                self._add_node(
                    node_id=m_id,
                    label=f"{class_name}.{method_name}",
                    entity_type="function",
                    file=filename,
                    metadata={
                        "class": class_name,
                        "parameters": method.get("parameters", []),
                        "return_type": method.get("return_type"),
                        "is_async": method.get("is_async", False),
                        "line_number": method.get("line_number", 0),
                    },
                )
                self._add_edge(cls_id, m_id, "contains")

            parent = cls.get("parent_class")
            if parent:
                parent_id = self._node_id("class", f"{filename}::{parent}")
                if parent_id in self.nodes:
                    self._add_edge(cls_id, parent_id, "inherits")

    def _process_functions(self, functions: List[Any], file_node_id: str, filename: str):
        for func in functions:
            if not isinstance(func, dict):
                continue
            func_name = func.get("name", "")
            if not func_name:
                continue

            func_id = self._node_id("function", f"{filename}::{func_name}")
            self._add_node(
                node_id=func_id,
                label=func_name,
                entity_type="function",
                file=filename,
                metadata={
                    "parameters": func.get("parameters", []),
                    "return_type": func.get("return_type"),
                    "is_async": func.get("is_async", False),
                    "complexity": func.get("complexity", 1),
                    "line_number": func.get("line_number", 0),
                },
            )
            self._add_edge(file_node_id, func_id, "contains")

    def _process_apis(self, apis: List[Any], file_node_id: str, filename: str):
        for api in apis:
            if not isinstance(api, dict):
                continue
            method = api.get("method", "GET")
            path = api.get("endpoint") or api.get("path") or api.get("name", "/")
            label = f"{method} {path}"

            api_id = self._node_id("api_endpoint", f"{filename}::{label}")
            self._add_node(
                node_id=api_id,
                label=label,
                entity_type="api_endpoint",
                file=filename,
                metadata={
                    "method": method,
                    "path": path,
                    "handler": api.get("handler"),
                    "parameters": api.get("parameters", []),
                    "line_number": api.get("line_number", 0),
                },
            )
            self._add_edge(file_node_id, api_id, "exposes")

    def _compute_degrees(self):
        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            if src in self.nodes:
                self.nodes[src]["degree"] += 1
            if tgt in self.nodes:
                self.nodes[tgt]["degree"] += 1


def generate_graph_data(analysis_results: Dict[str, Any], analysis_name: str) -> Dict[str, Any]:
    """Public entry point — generates graph data from existing analysis results."""
    processor = GraphProcessor()
    return processor.process_analysis(analysis_results, analysis_name)
