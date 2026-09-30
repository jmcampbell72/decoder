/**
 * Interactive Mind Map Visualization for Code Analysis
 * Shows relationships between modules, classes, functions, APIs, and database models
 */

class CodeMindMap {
    constructor(containerId, data) {
        this.container = d3.select(`#${containerId}`);
        this.data = data;
        this.width = 1200;
        this.height = 800;
        this.nodeRadius = 8;
        this.linkDistance = 200; // Further increased for better separation
        this.chargeStrength = -800; // Much stronger repulsion to prevent overlap
        
        this.init();
    }
    
    init() {
        // Clear existing content
        this.container.selectAll("*").remove();
        
        // Create SVG
        this.svg = this.container
            .append("svg")
            .attr("width", this.width)
            .attr("height", this.height)
            .style("border", "1px solid #dee2e6")
            .style("border-radius", "0.375rem");
            
        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {
                this.g.attr("transform", event.transform);
            });
            
        this.svg.call(zoom);
        
        // Create main group for zooming
        this.g = this.svg.append("g");
        
        // Add arrow markers for directed relationships
        this.svg.append("defs").selectAll("marker")
            .data(["contains", "extends", "implements", "calls", "imports"])
            .enter().append("marker")
            .attr("id", d => `arrow-${d}`)
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 15)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("class", "arrow");
            
        this.processData();
        this.createVisualization();
    }
    
    processData() {
        // Use the nodes and edges directly from backend
        if (this.data.nodes && this.data.edges) {
            this.nodes = this.data.nodes.map(node => ({
                id: node.id,
                name: node.name,
                type: node.type,
                level: node.level,
                size: this.getNodeSize(node.type),
                ...node.metadata
            }));
            
            this.links = this.data.edges.map(edge => ({
                source: edge.source,
                target: edge.target,
                type: edge.type,
                ...edge.metadata
            }));
        } else {
            // Fallback to old format
            this.nodes = [];
            this.links = [];
            
            const rootNode = {
                id: "root",
                name: this.data.name || "Code Analysis",
                type: "project",
                level: 0,
                size: 20
            };
            this.nodes.push(rootNode);
            
            Object.entries(this.data.files || {}).forEach(([filename, fileData]) => {
                this.processFile(filename, fileData);
            });
            
            this.createRelationships();
        }
    }
    
    getNodeSize(type) {
        const sizes = {
            'project': 20,
            'file': 12,
            'class': 10,
            'database_model': 10,
            'controller': 10,
            'service': 10,
            'function': 8,
            'method': 6,
            'constructor': 6,
            'destructor': 6,
            'accessor': 6,
            'entry_point': 8,
            'utility': 6,
            'api_endpoint': 9,
            'module': 7,
            'property': 5
        };
        return sizes[type] || 6;
    }
    
    processFile(filename, fileData) {
        const fileId = `file-${filename}`;
        const language = fileData.language || 'unknown';
        
        // File node
        const fileNode = {
            id: fileId,
            name: filename.split('/').pop(),
            fullPath: filename,
            type: "file",
            language: language,
            level: 1,
            size: 12,
            metrics: fileData.quality_metrics || {}
        };
        this.nodes.push(fileNode);
        
        // Link file to root
        this.links.push({
            source: "root",
            target: fileId,
            type: "contains"
        });
        
        // Process classes
        if (fileData.classes && fileData.classes.length > 0) {
            fileData.classes.forEach(cls => {
                const classId = `class-${filename}-${cls.name}`;
                const classNode = {
                    id: classId,
                    name: cls.name,
                    type: "class",
                    level: 2,
                    size: 10,
                    methods: cls.methods || [],
                    parentClass: cls.parent_class,
                    interfaces: cls.interfaces || [],
                    file: filename
                };
                this.nodes.push(classNode);
                
                // Link class to file
                this.links.push({
                    source: fileId,
                    target: classId,
                    type: "contains"
                });
                
                // Process class methods
                if (cls.methods) {
                    cls.methods.forEach(method => {
                        const methodId = `method-${filename}-${cls.name}-${method.name}`;
                        const methodNode = {
                            id: methodId,
                            name: method.name,
                            type: "method",
                            level: 3,
                            size: 6,
                            parameters: method.parameters || [],
                            returnType: method.return_type,
                            isStatic: method.is_static || false,
                            visibility: method.visibility || 'public',
                            file: filename,
                            className: cls.name
                        };
                        this.nodes.push(methodNode);
                        
                        // Link method to class
                        this.links.push({
                            source: classId,
                            target: methodId,
                            type: "contains"
                        });
                    });
                }
            });
        }
        
        // Process standalone functions
        if (fileData.functions && fileData.functions.length > 0) {
            fileData.functions.forEach(func => {
                const funcId = `function-${filename}-${func.name}`;
                const funcNode = {
                    id: funcId,
                    name: func.name,
                    type: "function",
                    level: 2,
                    size: 8,
                    parameters: func.parameters || [],
                    returnType: func.return_type,
                    isAsync: func.is_async || false,
                    complexity: func.complexity || 1,
                    file: filename
                };
                this.nodes.push(funcNode);
                
                // Link function to file
                this.links.push({
                    source: fileId,
                    target: funcId,
                    type: "contains"
                });
            });
        }
        
        // Process API endpoints
        if (fileData.apis && fileData.apis.length > 0) {
            fileData.apis.forEach(api => {
                const apiId = `api-${filename}-${api.path || api.name}`;
                const apiNode = {
                    id: apiId,
                    name: `${api.method || 'GET'} ${api.path || api.name}`,
                    type: "api",
                    level: 2,
                    size: 9,
                    method: api.method,
                    path: api.path,
                    handler: api.handler,
                    file: filename
                };
                this.nodes.push(apiNode);
                
                // Link API to file
                this.links.push({
                    source: fileId,
                    target: apiId,
                    type: "contains"
                });
            });
        }
        
        // Process imports as dependencies
        if (fileData.imports && fileData.imports.length > 0) {
            fileData.imports.forEach(imp => {
                const importId = `import-${imp.module || imp.name}`;
                
                // Check if import node already exists
                let importNode = this.nodes.find(n => n.id === importId);
                if (!importNode) {
                    importNode = {
                        id: importId,
                        name: imp.module || imp.name,
                        type: "module",
                        level: 1,
                        size: 7,
                        isExternal: !imp.module || !imp.module.startsWith('./')
                    };
                    this.nodes.push(importNode);
                }
                
                // Link file to import
                this.links.push({
                    source: fileId,
                    target: importId,
                    type: "imports"
                });
            });
        }
    }
    
    createRelationships() {
        // Create inheritance relationships
        this.nodes.filter(n => n.type === 'class' && n.parentClass).forEach(classNode => {
            const parentNode = this.nodes.find(n => 
                n.type === 'class' && n.name === classNode.parentClass
            );
            if (parentNode) {
                this.links.push({
                    source: classNode.id,
                    target: parentNode.id,
                    type: "extends"
                });
            }
        });
        
        // Create interface implementation relationships
        this.nodes.filter(n => n.type === 'class' && n.interfaces).forEach(classNode => {
            classNode.interfaces.forEach(interfaceName => {
                const interfaceNode = this.nodes.find(n => 
                    n.type === 'class' && n.name === interfaceName
                );
                if (interfaceNode) {
                    this.links.push({
                        source: classNode.id,
                        target: interfaceNode.id,
                        type: "implements"
                    });
                }
            });
        });
    }
    
    createVisualization() {
        // Stop any existing simulation
        if (this.simulation) {
            this.simulation.stop();
        }
        
        // Initialize node positions to prevent top-left corner clustering
        this.nodes.forEach((node, i) => {
            if (!node.x || !node.y) {
                // Position nodes in a larger spread with better spacing
                const angle = (i / this.nodes.length) * 2 * Math.PI;
                const radius = Math.min(this.width, this.height) / 3; // Increased radius
                node.x = this.width / 2 + Math.cos(angle) * radius;
                node.y = this.height / 2 + Math.sin(angle) * radius;
            }
        });

        // Create force simulation with improved spacing parameters
        this.simulation = d3.forceSimulation(this.nodes)
            .force("link", d3.forceLink(this.links).id(d => d.id).distance(this.linkDistance))
            .force("charge", d3.forceManyBody().strength(this.chargeStrength))
            .force("center", d3.forceCenter(this.width / 2, this.height / 2))
            .force("collision", d3.forceCollide().radius(d => d.size + 25)) // Much larger collision padding
            .alphaDecay(0.05) // Slower decay for better settling
            .alphaMin(0.01)
            .velocityDecay(0.3); // Less velocity decay for smoother movement
        
        // Create links
        this.link = this.g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(this.links)
            .enter().append("line")
            .attr("class", d => `link link-${d.type}`)
            .attr("marker-end", d => `url(#arrow-${d.type})`)
            .style("stroke", d => this.getLinkColor(d.type))
            .style("stroke-width", 2)
            .style("opacity", 0.7);
        
        // Create nodes
        this.node = this.g.append("g")
            .attr("class", "nodes")
            .selectAll("circle")
            .data(this.nodes)
            .enter().append("circle")
            .attr("class", d => `node node-${d.type}`)
            .attr("r", d => d.size)
            .style("fill", d => this.getNodeColor(d.type))
            .style("stroke", "#fff")
            .style("stroke-width", 2)
            .call(d3.drag()
                .on("start", (event, d) => this.dragstarted(event, d))
                .on("drag", (event, d) => this.dragged(event, d))
                .on("end", (event, d) => this.dragended(event, d)));
        
        // Create labels
        this.label = this.g.append("g")
            .attr("class", "labels")
            .selectAll("text")
            .data(this.nodes)
            .enter().append("text")
            .attr("class", "label")
            .style("font-size", d => `${Math.min(12, d.size)}px`)
            .style("font-weight", d => d.type === 'project' ? 'bold' : 'normal')
            .style("text-anchor", "middle")
            .style("pointer-events", "none")
            .style("fill", "#ffffff")
            .text(d => d.name);
        
        // Add tooltips
        this.addTooltips();
        
        // Run simulation for more ticks to allow better settling with increased forces
        let tickCount = 0;
        const maxTicks = 150;
        
        this.simulation.on("tick", () => {
            tickCount++;
            
            this.link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            this.node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            this.label
                .attr("x", d => d.x)
                .attr("y", d => d.y + 4);
            
            // Stop after exactly maxTicks
            if (tickCount >= maxTicks) {
                this.simulation.stop();
                this.simulation = null; // Completely remove simulation reference
                console.log(`Simulation stopped and destroyed after ${tickCount} ticks`);
            }
        });
    }
    
    getNodeColor(type) {
        const colors = {
            'project': '#6f42c1',
            'file': '#0d6efd',
            'class': '#198754',
            'function': '#fd7e14',
            'method': '#20c997',
            'api': '#dc3545',
            'module': '#6c757d'
        };
        return colors[type] || '#6c757d';
    }
    
    getLinkColor(type) {
        const colors = {
            'contains': '#6c757d',
            'extends': '#198754',
            'implements': '#0dcaf0',
            'calls': '#fd7e14',
            'imports': '#6f42c1'
        };
        return colors[type] || '#6c757d';
    }
    
    addTooltips() {
        // Create tooltip
        const tooltip = d3.select("body").append("div")
            .attr("class", "mindmap-tooltip")
            .style("position", "absolute")
            .style("visibility", "hidden")
            .style("background", "rgba(0, 0, 0, 0.8)")
            .style("color", "white")
            .style("padding", "10px")
            .style("border-radius", "5px")
            .style("font-size", "12px")
            .style("z-index", "1000");
        
        this.node
            .on("mouseover", (event, d) => {
                tooltip.style("visibility", "visible")
                    .html(this.getTooltipContent(d));
            })
            .on("mousemove", (event) => {
                tooltip
                    .style("top", (event.pageY - 10) + "px")
                    .style("left", (event.pageX + 10) + "px");
            })
            .on("mouseout", () => {
                tooltip.style("visibility", "hidden");
            });
    }
    
    getTooltipContent(d) {
        let content = `<strong>${d.name}</strong><br/>Type: ${d.type}`;
        
        if (d.file) content += `<br/>File: ${d.file}`;
        if (d.language) content += `<br/>Language: ${d.language}`;
        if (d.method && d.path) content += `<br/>Endpoint: ${d.method} ${d.path}`;
        if (d.parameters && d.parameters.length > 0) {
            content += `<br/>Parameters: ${d.parameters.map(p => p.name || p).join(', ')}`;
        }
        if (d.returnType) content += `<br/>Returns: ${d.returnType}`;
        if (d.complexity) content += `<br/>Complexity: ${d.complexity}`;
        if (d.metrics && d.metrics.lines_of_code) {
            content += `<br/>Lines: ${d.metrics.lines_of_code}`;
        }
        
        return content;
    }
    
    dragstarted(event, d) {
        // Set up dragging and find connected nodes
        d.fx = d.x;
        d.fy = d.y;
        
        // Store initial positions of connected nodes
        this.dragGroup = this.getConnectedNodes(d);
        this.dragOffsets = new Map();
        
        console.log(`Dragging ${d.name}, found ${this.dragGroup.length} connected nodes`);
        
        this.dragGroup.forEach(node => {
            // Fix all nodes in the group at their current positions
            node.fx = node.x;
            node.fy = node.y;
            
            // Store relative offset from the dragged node
            this.dragOffsets.set(node.id, {
                dx: node.x - d.x,
                dy: node.y - d.y
            });
        });
        
        // Highlight the drag group with visual feedback
        this.highlightDragGroup(true);
    }
    
    dragged(event, d) {
        // Update main node position
        d.fx = event.x;
        d.fy = event.y;
        d.x = event.x;
        d.y = event.y;
        
        // Apply dynamic spatial adjustment with distance-based scaling
        this.dragGroup.forEach(node => {
            if (node.id !== d.id) {
                const offset = this.dragOffsets.get(node.id);
                if (offset) {
                    // Calculate original distance from dragged node
                    const originalDistance = Math.sqrt(offset.dx * offset.dx + offset.dy * offset.dy);
                    
                    // Apply scaling based on distance (closer nodes follow more closely)
                    let scaleFactor = 1.0;
                    if (originalDistance > 80) {
                        // Nodes farther away move with reduced influence, maintaining better spacing
                        scaleFactor = Math.max(0.4, 1 - (originalDistance - 80) / 150);
                    }
                    
                    // Calculate new position with dynamic scaling
                    const targetX = event.x + offset.dx * scaleFactor;
                    const targetY = event.y + offset.dy * scaleFactor;
                    
                    // Smooth interpolation for more natural movement
                    const lerpFactor = 0.8; // How quickly nodes follow (0.8 = 80% of the way)
                    node.x = node.x + (targetX - node.x) * lerpFactor;
                    node.y = node.y + (targetY - node.y) * lerpFactor;
                    
                    node.fx = node.x;
                    node.fy = node.y;
                }
            }
        });
        
        // Apply smooth transitions to visual elements
        this.dragGroup.forEach(node => {
            this.node
                .filter(nodeData => nodeData.id === node.id)
                .transition()
                .duration(50) // Short transition for smoothness
                .attr("cx", node.x)
                .attr("cy", node.y);
                
            this.label
                .filter(labelData => labelData.id === node.id)
                .transition()
                .duration(50)
                .attr("x", node.x)
                .attr("y", node.y + 4);
        });
        
        // Update links with smooth transitions
        this.link
            .transition()
            .duration(30)
            .attr("x1", l => l.source.x)
            .attr("y1", l => l.source.y)
            .attr("x2", l => l.target.x)
            .attr("y2", l => l.target.y);
    }
    
    dragended(event, d) {
        // Keep all nodes fixed at their dragged positions
        this.dragGroup.forEach(node => {
            node.fx = node.x;
            node.fy = node.y;
        });
        
        // Remove visual highlighting
        this.highlightDragGroup(false);
        
        // Clean up
        this.dragGroup = null;
        this.dragOffsets = null;
    }
    
    highlightDragGroup(highlight) {
        if (!this.dragGroup) return;
        
        const dragNodeIds = new Set(this.dragGroup.map(n => n.id));
        
        // Highlight connected nodes with visual feedback
        this.node
            .style("opacity", d => {
                if (highlight) {
                    return dragNodeIds.has(d.id) ? 1 : 0.3;
                }
                return 1;
            })
            .style("stroke-width", d => {
                if (highlight && dragNodeIds.has(d.id)) {
                    return "3px";
                }
                return "2px";
            });
            
        this.label
            .style("opacity", d => {
                if (highlight) {
                    return dragNodeIds.has(d.id) ? 1 : 0.3;
                }
                return 1;
            })
            .style("font-weight", d => {
                if (highlight && dragNodeIds.has(d.id)) {
                    return "bold";
                }
                return d.type === 'project' ? 'bold' : 'normal';
            });
            
        // Highlight connecting links
        this.link
            .style("opacity", l => {
                if (highlight) {
                    const sourceId = l.source.id || l.source;
                    const targetId = l.target.id || l.target;
                    return (dragNodeIds.has(sourceId) && dragNodeIds.has(targetId)) ? 1 : 0.1;
                }
                return 0.7;
            })
            .style("stroke-width", l => {
                if (highlight) {
                    const sourceId = l.source.id || l.source;
                    const targetId = l.target.id || l.target;
                    return (dragNodeIds.has(sourceId) && dragNodeIds.has(targetId)) ? "3px" : "2px";
                }
                return "2px";
            });
    }
    
    getConnectedNodes(centralNode) {
        const connected = new Set([centralNode]);
        const visited = new Set([centralNode.id]);
        
        // Recursively find connected nodes up to 2 levels deep for better grouping
        const findConnections = (node, depth) => {
            if (depth >= 2) return; // Limit depth to prevent too large groups
            
            this.links.forEach(link => {
                let connectedNode = null;
                
                // Handle both object and string references for source/target
                const sourceId = link.source.id || link.source;
                const targetId = link.target.id || link.target;
                const nodeId = node.id || node;
                
                if (sourceId === nodeId) {
                    connectedNode = this.nodes.find(n => n.id === targetId);
                } else if (targetId === nodeId) {
                    connectedNode = this.nodes.find(n => n.id === sourceId);
                }
                
                if (connectedNode && !visited.has(connectedNode.id)) {
                    connected.add(connectedNode);
                    visited.add(connectedNode.id);
                    // Recursively find connections of this node
                    findConnections(connectedNode, depth + 1);
                }
            });
        };
        
        findConnections(centralNode, 0);
        
        return Array.from(connected);
    }
    
    // Filter nodes by type
    filterByType(types) {
        this.node
            .style("opacity", d => types.includes(d.type) ? 1 : 0.1);
        this.label
            .style("opacity", d => types.includes(d.type) ? 1 : 0.1);
        this.link
            .style("opacity", d => {
                const sourceVisible = types.includes(d.source.type);
                const targetVisible = types.includes(d.target.type);
                return sourceVisible && targetVisible ? 0.7 : 0.1;
            });
    }
    
    // Reset filter
    resetFilter() {
        this.node.style("opacity", 1);
        this.label.style("opacity", 1);
        this.link.style("opacity", 0.7);
    }
    
    // Highlight node and its connections
    highlightNode(nodeId) {
        const connectedLinks = this.links.filter(l => 
            l.source.id === nodeId || l.target.id === nodeId
        );
        const connectedNodes = new Set([nodeId]);
        connectedLinks.forEach(l => {
            connectedNodes.add(l.source.id);
            connectedNodes.add(l.target.id);
        });
        
        this.node
            .style("opacity", d => connectedNodes.has(d.id) ? 1 : 0.1);
        this.label
            .style("opacity", d => connectedNodes.has(d.id) ? 1 : 0.1);
        this.link
            .style("opacity", d => 
                connectedNodes.has(d.source.id) && connectedNodes.has(d.target.id) ? 0.7 : 0.1
            );
    }
}

// Export for use in other scripts
window.CodeMindMap = CodeMindMap;