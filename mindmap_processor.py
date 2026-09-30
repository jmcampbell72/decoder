"""
Mind Map Data Processor for Code Analysis
Extracts and structures code components for visualization
"""

import re
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict


class MindMapProcessor:
    """Process analysis results into mind map structure"""
    
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.node_id_counter = 0
        self.node_map = {}  # name -> node_id mapping
        
    def process_analysis(self, analysis_results: Dict[str, Any], analysis_name: str) -> Dict[str, Any]:
        """Convert analysis results into mind map structure"""
        self.reset()
        
        # Create root project node
        root_id = self._create_node(
            name=analysis_name,
            node_type="project",
            level=0,
            metadata={"description": "Root project node"}
        )
        
        # Process each file (skip summary data)
        for filename, file_data in analysis_results.items():
            if filename != '_summary' and isinstance(file_data, dict) and not file_data.get('error'):
                self._process_file(filename, file_data, root_id)
        
        # Create cross-file relationships
        self._create_relationships(analysis_results)
        
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "metadata": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_types": self._get_node_type_counts()
            }
        }
    
    def reset(self):
        """Reset processor state"""
        self.nodes = []
        self.edges = []
        self.node_id_counter = 0
        self.node_map = {}
    
    def _create_node(self, name: str, node_type: str, level: int, 
                     metadata: Dict[str, Any] = None) -> int:
        """Create a new node and return its ID"""
        node_id = self.node_id_counter
        self.node_id_counter += 1
        
        node = {
            "id": node_id,
            "name": name,
            "type": node_type,
            "level": level,
            "metadata": metadata if metadata is not None else {}
        }
        
        self.nodes.append(node)
        self.node_map[f"{node_type}:{name}"] = node_id
        
        return node_id
    
    def _create_edge(self, source_id: int, target_id: int, edge_type: str, 
                     metadata: Dict[str, Any] = None):
        """Create a new edge"""
        edge = {
            "source": source_id,
            "target": target_id,
            "type": edge_type,
            "metadata": metadata if metadata is not None else {}
        }
        self.edges.append(edge)
    
    def _process_file(self, filename: str, file_data: Dict[str, Any], root_id: int):
        """Process a single file and create nodes/edges"""
        print(f"Processing file: {filename} with data keys: {list(file_data.keys())}")
        
        # Create file node
        file_id = self._create_node(
            name=filename.split('/')[-1],
            node_type="file",
            level=1,
            metadata={
                "full_path": filename,
                "language": file_data.get("language", "unknown"),
                "size_bytes": file_data.get("size_bytes", 0),
                "line_count": file_data.get("line_count", 0),
                "quality_metrics": file_data.get("quality_metrics", {})
            }
        )
        
        # Connect file to root
        self._create_edge(root_id, file_id, "contains")
        
        # Process imports/modules
        self._process_imports(file_data.get("imports", []), file_id, filename)
        
        # Process classes
        self._process_classes(file_data.get("classes", []), file_id, filename)
        
        # Process standalone functions
        self._process_functions(file_data.get("functions", []), file_id, filename)
        
        # Process API endpoints
        self._process_apis(file_data.get("apis", []), file_id, filename)
        
        # Detect database models
        self._process_database_models(file_data, file_id, filename)
    
    def _process_imports(self, imports: List[Dict[str, Any]], file_id: int, filename: str):
        """Process import statements"""
        for imp in imports:
            module_name = imp.get("module") or imp.get("name", "unknown")
            if not module_name:
                continue
                
            # Determine if it's external or internal module
            is_external = not (module_name.startswith('.') or 
                             module_name in ['os', 'sys', 'json', 're'])
            
            module_key = f"module:{module_name}"
            if module_key not in self.node_map:
                module_id = self._create_node(
                    name=module_name,
                    node_type="module",
                    level=1,
                    metadata={
                        "is_external": is_external,
                        "import_type": imp.get("type", "import")
                    }
                )
            else:
                module_id = self.node_map[module_key]
            
            # Create dependency edge
            self._create_edge(file_id, module_id, "imports", {
                "import_items": imp.get("items", [])
            })
    
    def _process_classes(self, classes: List[Dict[str, Any]], file_id: int, filename: str):
        """Process class definitions"""
        for cls in classes:
            class_name = cls.get("name", "UnknownClass")
            
            # Determine class type (regular, database model, etc.)
            class_type = self._determine_class_type(cls, filename)
            
            class_id = self._create_node(
                name=class_name,
                node_type=class_type,
                level=2,
                metadata={
                    "file": filename,
                    "line_number": cls.get("line_number", 0),
                    "parent_class": cls.get("parent_class"),
                    "interfaces": cls.get("interfaces", []),
                    "is_abstract": cls.get("is_abstract", False),
                    "visibility": cls.get("visibility", "public"),
                    "methods_count": len(cls.get("methods", [])),
                    "properties_count": len(cls.get("properties", []))
                }
            )
            
            # Connect class to file
            self._create_edge(file_id, class_id, "contains")
            
            # Process class methods
            self._process_functions(cls.get("methods", []), class_id, filename, class_name)
            
            # Process class properties
            self._process_properties(cls.get("properties", []), class_id, filename, class_name)
    
    def _process_functions(self, functions: List[Dict[str, Any]], parent_id: int, 
                          filename: str, class_name: str = None):
        """Process function definitions"""
        for func in functions:
            func_name = func.get("name", "unknown_function")
            
            # Determine function type
            func_type = self._determine_function_type(func, class_name)
            
            func_id = self._create_node(
                name=func_name,
                node_type=func_type,
                level=3 if class_name else 2,
                metadata={
                    "file": filename,
                    "class": class_name,
                    "line_number": func.get("line_number", 0),
                    "parameters": func.get("parameters", []),
                    "return_type": func.get("return_type"),
                    "is_async": func.get("is_async", False),
                    "is_static": func.get("is_static", False),
                    "visibility": func.get("visibility", "public"),
                    "complexity": func.get("complexity", 1),
                    "lines_of_code": func.get("lines_of_code", 0)
                }
            )
            
            # Connect function to parent (file or class)
            edge_type = "contains"
            self._create_edge(parent_id, func_id, edge_type)
    
    def _process_properties(self, properties: List[Dict[str, Any]], class_id: int,
                           filename: str, class_name: str):
        """Process class properties/attributes"""
        for prop in properties:
            prop_name = prop.get("name", "unknown_property")
            
            prop_id = self._create_node(
                name=prop_name,
                node_type="property",
                level=3,
                metadata={
                    "file": filename,
                    "class": class_name,
                    "data_type": prop.get("type"),
                    "is_static": prop.get("is_static", False),
                    "visibility": prop.get("visibility", "public"),
                    "default_value": prop.get("default_value")
                }
            )
            
            self._create_edge(class_id, prop_id, "contains")
    
    def _process_apis(self, apis: List[Dict[str, Any]], file_id: int, filename: str):
        """Process API endpoints"""
        for api in apis:
            endpoint_name = f"{api.get('method', 'GET')} {api.get('path', api.get('name', '/'))}"
            
            api_id = self._create_node(
                name=endpoint_name,
                node_type="api_endpoint",
                level=2,
                metadata={
                    "file": filename,
                    "method": api.get("method", "GET"),
                    "path": api.get("path"),
                    "handler": api.get("handler"),
                    "line_number": api.get("line_number", 0),
                    "parameters": api.get("parameters", []),
                    "response_type": api.get("response_type")
                }
            )
            
            self._create_edge(file_id, api_id, "contains")
    
    def _process_database_models(self, file_data: Dict[str, Any], file_id: int, filename: str):
        """Detect and process database models"""
        # Look for database model patterns in classes
        classes = file_data.get("classes", [])
        for cls in classes:
            if self._is_database_model(cls, file_data):
                # Already processed as class, just update type
                class_key = f"class:{cls.get('name')}"
                if class_key in self.node_map:
                    # Find and update the node type
                    node_id = self.node_map[class_key]
                    for node in self.nodes:
                        if node["id"] == node_id:
                            node["type"] = "database_model"
                            node["metadata"]["is_model"] = True
                            break
    
    def _determine_class_type(self, cls: Dict[str, Any], filename: str) -> str:
        """Determine the specific type of class"""
        class_name = cls.get("name", "")
        parent_class = cls.get("parent_class", "")
        
        # Check for database models
        if (parent_class in ["Model", "Base", "db.Model", "models.Model"] or
            "model" in class_name.lower() or
            filename.endswith("models.py") or
            "models/" in filename):
            return "database_model"
        
        # Check for API controllers
        if (parent_class in ["Controller", "BaseController"] or
            "controller" in class_name.lower() or
            "views.py" in filename):
            return "controller"
        
        # Check for services
        if ("service" in class_name.lower() or
            "services/" in filename):
            return "service"
        
        return "class"
    
    def _determine_function_type(self, func: Dict[str, Any], class_name: str) -> str:
        """Determine the specific type of function"""
        func_name = func.get("name", "")
        
        if class_name:
            # Constructor
            if func_name in ["__init__", "constructor", "init"]:
                return "constructor"
            # Destructor
            if func_name in ["__del__", "destructor", "deinit"]:
                return "destructor"
            # Getter/Setter
            if func_name.startswith(("get_", "set_")) or func.get("is_property"):
                return "accessor"
            return "method"
        else:
            # Check for main/entry point functions
            if func_name in ["main", "__main__", "run", "start"]:
                return "entry_point"
            # Check for utility functions
            if func_name.startswith("_") or "util" in func_name.lower():
                return "utility"
            return "function"
    
    def _is_database_model(self, cls: Dict[str, Any], file_data: Dict[str, Any]) -> bool:
        """Check if a class is a database model"""
        class_name = cls.get("name", "")
        parent_class = cls.get("parent_class", "")
        
        # Check inheritance
        model_bases = ["Model", "Base", "db.Model", "models.Model", "SQLAlchemyBase"]
        if parent_class in model_bases:
            return True
        
        # Check for model-like attributes
        methods = cls.get("methods", [])
        method_names = [m.get("name", "") for m in methods]
        
        # Look for ORM-like methods
        orm_methods = ["save", "delete", "update", "create", "find", "query"]
        if any(method in method_names for method in orm_methods):
            return True
        
        # Check for table/collection decorators
        if "table" in class_name.lower() or "model" in class_name.lower():
            return True
        
        return False
    
    def _create_relationships(self, analysis_results: Dict[str, Any]):
        """Create cross-file relationships"""
        # Create inheritance relationships
        self._create_inheritance_relationships()
        
        # Create function call relationships
        self._create_call_relationships(analysis_results)
        
        # Create API to handler relationships
        self._create_api_handler_relationships()
    
    def _create_inheritance_relationships(self):
        """Create inheritance edges between classes"""
        for node in self.nodes:
            if node["type"] in ["class", "database_model", "controller", "service"]:
                parent_class = node["metadata"].get("parent_class")
                if parent_class:
                    # Find parent class node
                    parent_key = f"class:{parent_class}"
                    if parent_key in self.node_map:
                        parent_id = self.node_map[parent_key]
                        self._create_edge(node["id"], parent_id, "inherits")
    
    def _create_call_relationships(self, analysis_results: Dict[str, Any]):
        """Create function call relationships (simplified)"""
        # This is a basic implementation - could be enhanced with AST analysis
        function_nodes = [n for n in self.nodes if n["type"] in ["function", "method"]]
        
        for func_node in function_nodes:
            func_name = func_node["name"]
            file_path = func_node["metadata"].get("file", "")
            
            # Look for potential function calls in the same file
            if file_path in analysis_results:
                file_data = analysis_results[file_path]
                # This would need more sophisticated analysis in practice
                # For now, we'll skip this to avoid false positives
                pass
    
    def _create_api_handler_relationships(self):
        """Create relationships between API endpoints and their handlers"""
        api_nodes = [n for n in self.nodes if n["type"] == "api_endpoint"]
        function_nodes = [n for n in self.nodes if n["type"] in ["function", "method"]]
        
        for api_node in api_nodes:
            handler_name = api_node["metadata"].get("handler")
            if handler_name:
                # Find matching handler function
                for func_node in function_nodes:
                    if func_node["name"] == handler_name:
                        self._create_edge(api_node["id"], func_node["id"], "handles")
                        break
    
    def _get_node_type_counts(self) -> Dict[str, int]:
        """Get count of nodes by type"""
        counts = defaultdict(int)
        for node in self.nodes:
            counts[node["type"]] += 1
        return dict(counts)


def generate_mindmap_data(analysis_results: Dict[str, Any], analysis_name: str) -> Dict[str, Any]:
    """Generate mind map data from analysis results"""
    processor = MindMapProcessor()
    return processor.process_analysis(analysis_results, analysis_name)