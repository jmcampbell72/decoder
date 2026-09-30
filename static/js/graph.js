/* ── Codebase Relationship Graph ─────────────────────────────────────── */
(function () {
    'use strict';

    /* ── Config ────────────────────────────────────────────────────────── */
    const NODE_COLORS = {
        file:         '#4e9af1',
        class:        '#f97316',
        function:     '#22c55e',
        api_endpoint: '#a855f7',
        package:      '#64748b',
    };

    const EDGE_COLORS = {
        contains:         '#475569',
        imports:          '#64748b',
        exposes:          '#a855f7',
        inherits:         '#f97316',
        cross_repo_call:  '#06b6d4',
    };

    const NODE_BASE_RADIUS = 7;
    const NODE_MAX_RADIUS  = 26;

    /* ── State ─────────────────────────────────────────────────────────── */
    let allNodes = [], allEdges = [];
    let simulation, svg, linkGroup, nodeGroup, zoomBehavior;
    let simNodeById    = new Map();
    let selectedNodeId = null;
    let focusNodeId    = null;
    let hiddenTypes    = new Set();
    let searchTerm     = '';
    let inspectorHistory = [];
    let insightsCache    = {};

    /* ── DOM refs ──────────────────────────────────────────────────────── */
    const svgEl         = document.getElementById('graph-svg');
    const loading       = document.getElementById('graph-loading');
    const tooltip       = document.getElementById('graph-tooltip');
    const sidebar       = document.getElementById('graph-sidebar');
    const sidebarBody   = document.getElementById('sidebar-body');
    const focusBadge    = document.getElementById('focus-mode-badge');
    const searchInput   = document.getElementById('graph-search');
    const statNodes     = document.getElementById('stat-nodes');
    const statEdges     = document.getElementById('stat-edges');
    const statVisible   = document.getElementById('stat-visible');
    const backBtn       = document.getElementById('btn-inspector-back');

    /* ── Bootstrap ─────────────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        const dataUrl  = svgEl.dataset.url;
        const regenUrl = svgEl.dataset.regenUrl;

        fetch(dataUrl)
            .then(r => r.json())
            .then(data => {
                allNodes = data.nodes || [];
                allEdges = data.edges || [];
                initGraph();
                updateStats();
                loading.classList.add('hidden');
            })
            .catch(err => {
                loading.innerHTML = `<i class="fas fa-exclamation-triangle text-warning fa-2x"></i>
                    <p class="mt-2">Failed to load graph data.<br><small>${err.message}</small></p>`;
            });

        /* Search */
        searchInput.addEventListener('input', () => {
            searchTerm = searchInput.value.trim().toLowerCase();
            applyVisibility();
        });

        /* Filter pills */
        document.querySelectorAll('.filter-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const type = pill.dataset.type;
                if (hiddenTypes.has(type)) {
                    hiddenTypes.delete(type);
                    pill.classList.remove('inactive');
                    pill.classList.add('active');
                } else {
                    hiddenTypes.add(type);
                    pill.classList.remove('active');
                    pill.classList.add('inactive');
                }
                applyVisibility();
            });
        });

        /* Reset view */
        document.getElementById('btn-reset-view').addEventListener('click', resetView);

        /* Regenerate */
        const regenBtn = document.getElementById('btn-regen');
        if (regenBtn) regenBtn.addEventListener('click', () => {
            loading.classList.remove('hidden');
            loading.innerHTML = `<div class="spinner-border text-primary" role="status"></div>
                <p class="mt-2">Regenerating graph…</p>`;
            fetch(regenUrl, { method: 'POST',
                headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' } })
                .then(r => r.json())
                .then(res => {
                    if (res.status === 'success') {
                        allNodes = res.data.nodes || [];
                        allEdges = res.data.edges || [];
                        selectedNodeId = null;
                        focusNodeId    = null;
                        initGraph();
                        updateStats();
                        loading.classList.add('hidden');
                    }
                })
                .catch(() => {
                    loading.innerHTML = `<p class="text-danger">Regeneration failed.</p>`;
                });
        });

        /* Sidebar toggle */
        document.getElementById('btn-close-sidebar').addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
        });

        /* Back button */
        backBtn.addEventListener('click', () => {
            if (inspectorHistory.length > 0) {
                const prev = inspectorHistory.pop();
                navigateToNode(prev.id, false);
            }
        });

        /* Focus badge exit */
        focusBadge.addEventListener('click', exitFocusMode);
    });

    /* ── Graph init ────────────────────────────────────────────────────── */
    function initGraph() {
        /* Clear */
        d3.select(svgEl).selectAll('*').remove();
        if (simulation) simulation.stop();

        const width  = svgEl.clientWidth  || 900;
        const height = svgEl.clientHeight || 600;

        svg = d3.select(svgEl);

        /* Defs: arrowhead markers per edge type */
        const defs = svg.append('defs');
        Object.entries(EDGE_COLORS).forEach(([type, color]) => {
            defs.append('marker')
                .attr('id',           `arrow-${type}`)
                .attr('viewBox',      '0 -5 10 10')
                .attr('refX',         28)
                .attr('refY',         0)
                .attr('markerWidth',  6)
                .attr('markerHeight', 6)
                .attr('orient',       'auto')
              .append('path')
                .attr('d',    'M0,-5L10,0L0,5')
                .attr('fill', color)
                .attr('opacity', 0.8);
        });

        /* Zoom layer */
        const g = svg.append('g').attr('class', 'zoom-layer');

        zoomBehavior = d3.zoom()
            .scaleExtent([0.05, 4])
            .on('zoom', event => g.attr('transform', event.transform));

        svg.call(zoomBehavior);

        /* Double-click on background: exit focus mode */
        svg.on('dblclick.zoom', null);
        svg.on('dblclick', exitFocusMode);

        /* Degree scale for radius */
        const maxDegree = d3.max(allNodes, d => d.degree) || 1;
        const rScale = d3.scaleSqrt()
            .domain([0, maxDegree])
            .range([NODE_BASE_RADIUS, NODE_MAX_RADIUS]);

        /* Copy nodes/edges for simulation (D3 mutates them) */
        const nodes = allNodes.map(n => ({ ...n, _r: rScale(n.degree) }));
        const nodeById = new Map(nodes.map(n => [n.id, n]));
        simNodeById = nodeById;

        const links = allEdges
            .filter(e => nodeById.has(e.source) && nodeById.has(e.target))
            .map(e => ({ ...e, source: nodeById.get(e.source), target: nodeById.get(e.target) }));

        /* Simulation */
        simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
                const sr = d.source._r || NODE_BASE_RADIUS;
                const tr = d.target._r || NODE_BASE_RADIUS;
                return sr + tr + 40;
            }).strength(0.5))
            .force('charge', d3.forceManyBody().strength(-220))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => d._r + 4));

        /* Links */
        linkGroup = g.append('g').attr('class', 'links');
        const linkEls = linkGroup.selectAll('line')
            .data(links)
            .join('line')
            .attr('class', 'link')
            .attr('stroke', d => EDGE_COLORS[d.type] || '#475569')
            .attr('stroke-width', d => d.type === 'cross_repo_call' ? 2 : 1.4)
            .attr('stroke-opacity', d => d.type === 'cross_repo_call' ? 0.9 : 0.7)
            .attr('stroke-dasharray', d => d.type === 'cross_repo_call' ? '7 3' : null)
            .attr('marker-end', d => `url(#arrow-${d.type})`)
            .attr('data-type', d => d.type)
            .attr('data-source', d => d.source.id)
            .attr('data-target', d => d.target.id);

        /* Edge label on hover */
        linkEls
            .on('mouseenter', (event, d) => showEdgeTooltip(event, d))
            .on('mouseleave', hideTooltip);

        /* Nodes */
        nodeGroup = g.append('g').attr('class', 'nodes');
        const nodeEls = nodeGroup.selectAll('g.node')
            .data(nodes)
            .join('g')
            .attr('class', 'node')
            .attr('data-id',   d => d.id)
            .attr('data-type', d => d.type)
            .call(d3.drag()
                .on('start', dragStarted)
                .on('drag',  dragged)
                .on('end',   dragEnded));

        nodeEls.append('circle')
            .attr('r',    d => d._r)
            .attr('fill', d => d.color || NODE_COLORS[d.type] || '#94a3b8')
            .attr('stroke', d => lighten(d.color || NODE_COLORS[d.type] || '#94a3b8', 40))
            .attr('stroke-width', 1.5);

        nodeEls.append('text')
            .attr('dy', d => d._r + 13)
            .attr('text-anchor', 'middle')
            .text(d => truncateLabel(d.label, 20));

        nodeEls
            .on('mouseenter', (event, d) => { event.stopPropagation(); showNodeTooltip(event, d); })
            .on('mouseleave', hideTooltip)
            .on('click',      (event, d) => { event.stopPropagation(); selectNode(d, nodeEls, linkEls); })
            .on('dblclick',   (event, d) => {
                event.stopPropagation();
                if (d._pinned) {
                    unpinNode(d);
                } else {
                    enterFocusMode(d, nodeEls, linkEls);
                }
            });

        /* Tick */
        simulation.on('tick', () => {
            linkEls
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            nodeEls.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        /* Apply current filter/search state */
        applyVisibility();
    }

    /* ── Visibility (filter + search + focus) ──────────────────────────── */
    function applyVisibility() {
        if (!nodeGroup) return;

        const nodeEls = nodeGroup.selectAll('g.node');
        const linkEls = linkGroup.selectAll('line.link');

        /* Build sets of visible node IDs */
        const visibleIds = new Set();

        nodeEls.each(function (d) {
            const typeHidden    = hiddenTypes.has(d.type);
            const searchMiss    = searchTerm && !d.label.toLowerCase().includes(searchTerm);
            const focusMiss     = focusNodeId && !isFocusRelated(d.id);
            const visible       = !typeHidden && !searchMiss && !focusMiss;
            if (visible) visibleIds.add(d.id);
        });

        nodeEls.each(function (d) {
            const el      = d3.select(this);
            const visible = visibleIds.has(d.id);
            el.style('display', visible ? null : 'none');
            el.classed('selected',    d.id === selectedNodeId);
            el.classed('highlighted', d.id !== selectedNodeId && selectedNodeId && isDirectlyConnected(selectedNodeId, d.id));
            el.classed('dimmed',      false);
        });

        linkEls.each(function (d) {
            const srcId = d.source.id || d.source;
            const tgtId = d.target.id || d.target;
            const visible = visibleIds.has(srcId) && visibleIds.has(tgtId);
            d3.select(this).style('display', visible ? null : 'none');
            d3.select(this).classed('highlighted', selectedNodeId && (srcId === selectedNodeId || tgtId === selectedNodeId));
        });

        /* Update stat */
        if (statVisible) statVisible.textContent = visibleIds.size;
    }

    /* ── Selection / highlight ─────────────────────────────────────────── */
    function selectNode(d, nodeEls, linkEls) {
        if (selectedNodeId === d.id) {
            selectedNodeId = null;
        } else {
            const prevId = selectedNodeId;
            selectedNodeId = d.id;
            showInspector(d, prevId);
        }
        applyVisibility();
    }

    function isDirectlyConnected(aId, bId) {
        return allEdges.some(e => {
            const s = e.source.id || e.source;
            const t = e.target.id || e.target;
            return (s === aId && t === bId) || (s === bId && t === aId);
        });
    }

    /* ── Focus / subgraph mode ─────────────────────────────────────────── */
    function enterFocusMode(d, nodeEls, linkEls) {
        focusNodeId = d.id;
        focusBadge.classList.add('visible');
        focusBadge.textContent = `Focus: ${d.label} — click to exit`;
        applyVisibility();
    }

    function exitFocusMode() {
        focusNodeId = null;
        focusBadge.classList.remove('visible');
        applyVisibility();
    }

    function unpinNode(d) {
        d.fx = null;
        d.fy = null;
        d._pinned = false;
        /* Restore original stroke */
        const color = d.color || NODE_COLORS[d.type] || '#94a3b8';
        nodeGroup.selectAll('g.node')
            .filter(n => n.id === d.id)
            .classed('pinned', false)
            .select('circle')
            .attr('stroke', lighten(color, 40))
            .attr('stroke-width', 1.5)
            .attr('stroke-dasharray', null);
        simulation.alphaTarget(0.1).restart();
        setTimeout(() => simulation.alphaTarget(0), 600);
    }

    function isFocusRelated(nodeId) {
        if (nodeId === focusNodeId) return true;
        return allEdges.some(e => {
            const s = e.source.id || e.source;
            const t = e.target.id || e.target;
            return (s === focusNodeId && t === nodeId) || (t === focusNodeId && s === nodeId);
        });
    }

    /* ── Inspector sidebar ─────────────────────────────────────────────── */
    function showInspector(d, prevNodeId) {
        sidebar.classList.remove('collapsed');

        if (prevNodeId && prevNodeId !== d.id) {
            inspectorHistory.push({ id: prevNodeId });
        }
        backBtn.classList.toggle('d-none', inspectorHistory.length === 0);

        const connectedEdges = allEdges.filter(e => {
            const s = e.source.id || e.source;
            const t = e.target.id || e.target;
            return s === d.id || t === d.id;
        });

        const nodeMap = simNodeById.size > 0 ? simNodeById : new Map(allNodes.map(n => [n.id, n]));
        const color  = d.color || NODE_COLORS[d.type] || '#94a3b8';
        const meta   = d.metadata || {};

        let metaRows = '';
        if (meta.language)      metaRows += metaRow('Language', meta.language);
        if (meta.line_count)    metaRows += metaRow('Lines', meta.line_count);
        if (meta.methods_count != null) metaRows += metaRow('Methods', meta.methods_count);
        if (meta.parent_class)  metaRows += metaRow('Extends', meta.parent_class);
        if (meta.is_abstract)   metaRows += metaRow('Abstract', 'Yes');
        if (meta.is_async)      metaRows += metaRow('Async', 'Yes');
        if (meta.return_type)   metaRows += metaRow('Returns', meta.return_type);
        if (meta.method)        metaRows += metaRow('HTTP Method', meta.method);
        if (meta.path)          metaRows += metaRow('Path', meta.path);
        if (meta.is_external != null) metaRows += metaRow('External', meta.is_external ? 'Yes' : 'No');
        if (meta.line_number)   metaRows += metaRow('Line', meta.line_number);
        metaRows += metaRow('Connections', d.degree);

        let edgeItems = '';
        connectedEdges.slice(0, 30).forEach(e => {
            const s    = e.source.id || e.source;
            const t    = e.target.id || e.target;
            const otherId = s === d.id ? t : s;
            const other   = nodeMap.get(otherId);
            const dir     = s === d.id ? '→' : '←';
            const label   = other ? other.label : otherId;
            const ec      = EDGE_COLORS[e.type] || '#64748b';
            edgeItems += `
                <div class="inspector-edge-item inspector-edge-clickable" data-node-id="${escHtml(otherId)}">
                    <span class="edge-type-badge" style="background:${ec}22;color:${ec};">${e.type}</span>
                    <span class="edge-label">${dir} ${escHtml(label)}</span>
                </div>`;
        });
        if (connectedEdges.length > 30) {
            edgeItems += `<p class="text-muted" style="font-size:0.75rem;margin-top:6px;">…and ${connectedEdges.length - 30} more</p>`;
        }

        const filename = d.file || (d.metadata && d.metadata.full_path) || (d.type === 'file' ? d.label : null);
        const fileNodeId = filename ? findFileNodeId(filename, nodeMap) : null;
        const fileLink = d.file
            ? (fileNodeId
                ? `<div class="inspector-file inspector-file-clickable" data-node-id="${escHtml(fileNodeId)}"><i class="fas fa-file-code me-1"></i>${escHtml(d.file)}</div>`
                : `<div class="inspector-file"><i class="fas fa-file-code me-1"></i>${escHtml(d.file)}</div>`)
            : '';

        sidebarBody.innerHTML = `
            <span class="inspector-type-badge" style="background:${color}22;color:${color};">${d.type.replace('_', ' ')}</span>
            <div class="inspector-name">${escHtml(d.label)}</div>
            ${fileLink}
            <div id="inspector-insights-area"></div>
            <div id="inspector-findings-area"></div>
            <div class="inspector-meta">
                ${metaRows}
            </div>
            ${connectedEdges.length > 0 ? `
                <div class="inspector-edges-title">Relationships (${connectedEdges.length})</div>
                ${edgeItems}
            ` : ''}
        `;

        sidebarBody.querySelectorAll('.inspector-edge-clickable').forEach(el => {
            el.addEventListener('click', () => {
                const nid = el.dataset.nodeId;
                navigateToNode(nid, true);
            });
        });

        const clickableFile = sidebarBody.querySelector('.inspector-file-clickable');
        if (clickableFile) {
            clickableFile.addEventListener('click', () => {
                navigateToNode(clickableFile.dataset.nodeId, true);
            });
        }

        if (filename) {
            const analysisId = meta.analysis_id || null;
            fetchInsights(filename, d.type, d.label, analysisId);
        }

        const tags = d.system_tags || [];
        if (tags.length > 0 && d.type !== 'repo') {
            fetchSystemFindings(d);
        }
    }

    function findFileNodeId(filename, nodeMap) {
        for (const [id, n] of nodeMap) {
            if (n.type === 'file' && (n.file === filename || n.label === filename ||
                (n.metadata && n.metadata.full_path === filename))) return id;
        }
        return null;
    }

    function fetchInsights(filename, nodeType, nodeLabel, analysisId) {
        const insightsArea = document.getElementById('inspector-insights-area');
        if (!insightsArea) return;

        const cacheKey = analysisId ? (filename + '::' + analysisId) : filename;

        if (insightsCache[cacheKey]) {
            renderInsights(insightsCache[cacheKey], insightsArea, nodeType, nodeLabel);
            return;
        }

        const insightsUrl = svgEl.dataset.insightsUrl;
        if (!insightsUrl) return;

        insightsArea.innerHTML = '<div class="insights-loading"><i class="fas fa-spinner fa-spin me-1"></i>Loading overview…</div>';

        let url = insightsUrl + '?file=' + encodeURIComponent(filename);
        if (analysisId) url += '&analysis_id=' + encodeURIComponent(analysisId);

        fetch(url)
            .then(r => r.json())
            .then(data => {
                insightsCache[cacheKey] = data;
                const area = document.getElementById('inspector-insights-area');
                if (area) renderInsights(data, area, nodeType, nodeLabel);
            })
            .catch(() => {
                const area = document.getElementById('inspector-insights-area');
                if (area) area.innerHTML = '';
            });
    }

    const findingsCache = {};

    function fetchSystemFindings(d) {
        const findingsArea = document.getElementById('inspector-findings-area');
        if (!findingsArea) return;

        const tag  = (d.system_tags || [])[0];
        if (!tag) return;

        const cacheKey = d.id + '::' + tag;
        if (findingsCache[cacheKey]) {
            renderSystemFindings(findingsCache[cacheKey], findingsArea, tag);
            return;
        }

        const findingsUrl = svgEl.dataset.findingsUrl;
        if (!findingsUrl) return;

        findingsArea.innerHTML = '<div class="insights-loading"><i class="fas fa-spinner fa-spin me-1"></i>Loading findings…</div>';

        const file = d.file || (d.metadata && d.metadata.full_path) || (d.type === 'file' ? d.label : '') || '';
        const url = findingsUrl
            + '?label='       + encodeURIComponent(d.label)
            + '&node_type='   + encodeURIComponent(d.type)
            + '&system_tag='  + encodeURIComponent(tag)
            + (file ? '&file=' + encodeURIComponent(file) : '');

        fetch(url)
            .then(r => r.json())
            .then(data => {
                findingsCache[cacheKey] = data;
                const area = document.getElementById('inspector-findings-area');
                if (area) renderSystemFindings(data, area, tag);
            })
            .catch(() => {
                const area = document.getElementById('inspector-findings-area');
                if (area) area.innerHTML = '';
            });
    }

    function renderSystemFindings(data, container, tag) {
        if (!data || !data.found || !data.finding) {
            container.innerHTML = '';
            return;
        }

        const f = data.finding;
        const TAG_LABELS = {
            duplicate:      'Duplicate',
            common_pattern: 'Common Pattern',
            cross_api:      'Cross-Repo API',
            smell_hotspot:  'Smell Hotspot',
        };
        const TAG_ICONS = {
            duplicate:      'fa-copy',
            common_pattern: 'fa-layer-group',
            cross_api:      'fa-plug',
            smell_hotspot:  'fa-exclamation-triangle',
        };
        const tagLabel = TAG_LABELS[tag] || tag;
        const tagIcon  = TAG_ICONS[tag]  || 'fa-tag';

        let bodyHtml = '';

        if (tag === 'duplicate') {
            const repos  = f.repos || [];
            const occs   = f.occurrences || [];
            const mtype  = f.match_type ? `<span class="finding-match-badge">${escHtml(f.match_type.replace('_', ' '))}</span>` : '';
            bodyHtml += `<div class="finding-repo-count">Found in <strong>${repos.length}</strong> repo${repos.length !== 1 ? 's' : ''} ${mtype}</div>`;
            occs.slice(0, 8).forEach(o => {
                bodyHtml += `
                    <div class="finding-occurrence">
                        <span class="finding-repo-name">${escHtml(o.repo)}</span>
                        <span class="finding-file">${escHtml(o.file || '')}</span>
                        ${o.line ? `<span class="finding-line">L${o.line}</span>` : ''}
                    </div>`;
            });
            if (occs.length > 8) {
                bodyHtml += `<div class="finding-overflow">…and ${occs.length - 8} more occurrences</div>`;
            }

        } else if (tag === 'common_pattern') {
            const repos  = f.repos || [];
            const ptype  = f.type === 'shared_dependency' ? 'Shared dependency' : 'Class hierarchy';
            const classes = f.classes || [];
            bodyHtml += `<div class="finding-repo-count"><span class="finding-match-badge">${escHtml(ptype)}</span> across <strong>${repos.length}</strong> repo${repos.length !== 1 ? 's' : ''}</div>`;
            bodyHtml += `<div class="finding-repo-list">${repos.map(r => `<span class="finding-repo-pill">${escHtml(r)}</span>`).join('')}</div>`;
            if (classes.length > 0) {
                bodyHtml += '<div class="finding-sub-header">Classes</div>';
                classes.slice(0, 6).forEach(c => {
                    bodyHtml += `<div class="finding-occurrence"><span class="finding-repo-name">${escHtml(c.repo)}</span><span class="finding-file">${escHtml(c.class || '')}</span></div>`;
                });
            }

        } else if (tag === 'cross_api') {
            const repos      = f.repos || [];
            const endpoints  = f.endpoints || [];
            const mtype      = f.match_type ? `<span class="finding-match-badge">${escHtml(f.match_type.replace('_', ' '))}</span>` : '';
            bodyHtml += `<div class="finding-repo-count">Shared across <strong>${repos.length}</strong> repo${repos.length !== 1 ? 's' : ''} ${mtype}</div>`;
            endpoints.slice(0, 6).forEach(ep => {
                const method = ep.method || '';
                const methodColors = {GET:'#22c55e',POST:'#4e9af1',PUT:'#f59e0b',DELETE:'#ef4444',PATCH:'#a855f7'};
                const mc = methodColors[method.toUpperCase()] || '#64748b';
                bodyHtml += `
                    <div class="finding-occurrence">
                        <span class="finding-method" style="color:${mc};">${escHtml(method)}</span>
                        <span class="finding-file">${escHtml(ep.path || '')}</span>
                        <span class="finding-repo-name">${escHtml(ep.repo || '')}</span>
                    </div>`;
            });
            if (endpoints.length > 6) {
                bodyHtml += `<div class="finding-overflow">…and ${endpoints.length - 6} more endpoints</div>`;
            }

        } else if (tag === 'smell_hotspot') {
            const smells = f.smells || [];
            const SEV_COLORS = {high:'#ef4444', medium:'#f59e0b', low:'#22c55e'};
            smells.forEach(s => {
                bodyHtml += `<div class="finding-smell-name">${escHtml(s.smell || '')}</div>`;
                (s.examples || []).slice(0, 3).forEach(ex => {
                    const sev = (ex.severity || '').toLowerCase();
                    const sc  = SEV_COLORS[sev] || '#94a3b8';
                    bodyHtml += `
                        <div class="finding-smell-row">
                            <span class="finding-sev-badge" style="background:${sc}22;color:${sc};">${escHtml(ex.severity || '')}</span>
                            <span class="finding-smell-desc">${escHtml(ex.description || '')}</span>
                            ${ex.impact ? `<span class="finding-smell-impact">${escHtml(ex.impact)}</span>` : ''}
                        </div>`;
                });
            });
        }

        container.innerHTML = `
            <div class="inspector-findings">
                <div class="finding-header">
                    <i class="fas ${tagIcon} me-1"></i>${tagLabel}
                </div>
                <div class="finding-body">${bodyHtml}</div>
            </div>`;
    }

    function renderInsights(data, container, nodeType, nodeLabel) {
        if (!data || !data.what_it_does) {
            container.innerHTML = '';
            return;
        }

        const isFile = !nodeType || nodeType === 'file';

        const scoreVal = data.code_quality_score;
        let scoreBadgeClass = 'score-good';
        if (scoreVal != null) {
            if (scoreVal >= 80) scoreBadgeClass = 'score-great';
            else if (scoreVal >= 60) scoreBadgeClass = 'score-good';
            else if (scoreVal >= 40) scoreBadgeClass = 'score-fair';
            else scoreBadgeClass = 'score-poor';
        }

        let descriptionText;
        let descriptionTitle;
        if (isFile) {
            descriptionTitle = 'What This Code Does';
            descriptionText = data.what_it_does;
        } else {
            const typeLabel = (nodeType || '').replace(/_/g, ' ');
            descriptionTitle = 'About This ' + typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1);
            descriptionText = buildEntitySummary(nodeType, nodeLabel, data);
        }

        let obsHtml = '';
        if (isFile && data.observations && data.observations.length > 0) {
            const items = data.observations.map(o => `<div class="insight-list-item"><i class="fas fa-chevron-right me-1"></i>${escHtml(o)}</div>`).join('');
            obsHtml = `
                <div class="insight-section">
                    <div class="insight-section-header insight-collapsible" data-target="insight-obs">
                        <span><i class="fas fa-eye me-1" style="color:#22d3ee;"></i> Key Observations</span>
                        <i class="fas fa-chevron-down insight-chevron"></i>
                    </div>
                    <div class="insight-section-body" id="insight-obs">${items}</div>
                </div>`;
        }

        let recHtml = '';
        if (isFile && data.recommendations && data.recommendations.length > 0) {
            const items = data.recommendations.map(r => `<div class="insight-list-item"><i class="fas fa-arrow-right me-1"></i>${escHtml(r)}</div>`).join('');
            recHtml = `
                <div class="insight-section">
                    <div class="insight-section-header insight-collapsible" data-target="insight-rec">
                        <span><i class="fas fa-lightbulb me-1" style="color:#facc15;"></i> Improvement Recommendations</span>
                        <i class="fas fa-chevron-down insight-chevron"></i>
                    </div>
                    <div class="insight-section-body" id="insight-rec">${items}</div>
                </div>`;
        }

        let perfHtml = '';
        if (isFile && data.performance_notes) {
            perfHtml = `<div class="insight-perf-note"><i class="fas fa-info-circle me-1" style="color:#64748b;"></i> <strong>Performance Notes:</strong> ${escHtml(data.performance_notes)}</div>`;
        }

        let statsHtml = '';
        if (isFile) {
            statsHtml = `
                <div class="insight-stats-bar">
                    <div class="insight-stat">
                        <div class="insight-stat-value">${data.complexity_level || '–'}</div>
                        <div class="insight-stat-label">Complexity</div>
                    </div>
                    <div class="insight-stat ${scoreBadgeClass}">
                        <div class="insight-stat-value">${scoreVal != null ? scoreVal : '–'}</div>
                        <div class="insight-stat-label">Quality Score</div>
                    </div>
                    <div class="insight-stat">
                        <div class="insight-stat-value">${data.function_count != null ? data.function_count : '–'}</div>
                        <div class="insight-stat-label">Functions</div>
                    </div>
                </div>`;
        } else {
            statsHtml = `
                <div class="insight-stats-bar">
                    <div class="insight-stat ${scoreBadgeClass}">
                        <div class="insight-stat-value">${scoreVal != null ? scoreVal : '–'}</div>
                        <div class="insight-stat-label">File Quality</div>
                    </div>
                    <div class="insight-stat">
                        <div class="insight-stat-value">${data.complexity_level || '–'}</div>
                        <div class="insight-stat-label">File Complexity</div>
                    </div>
                </div>`;
        }

        container.innerHTML = `
            <div class="inspector-insights">
                <div class="insight-section">
                    <div class="insight-section-header">
                        <span><i class="fas fa-info-circle me-1" style="color:#ef4444;"></i> ${escHtml(descriptionTitle)}</span>
                    </div>
                    <div class="insight-description">${escHtml(descriptionText)}</div>
                </div>
                ${obsHtml}
                ${recHtml}
                ${statsHtml}
                ${perfHtml}
            </div>
        `;

        container.querySelectorAll('.insight-collapsible').forEach(header => {
            header.addEventListener('click', () => {
                const target = document.getElementById(header.dataset.target);
                if (target) {
                    target.classList.toggle('collapsed');
                    header.querySelector('.insight-chevron').classList.toggle('rotated');
                }
            });
        });
    }

    function buildEntitySummary(nodeType, nodeLabel, data) {
        const typeName = (nodeType || '').replace(/_/g, ' ');
        const lang = data.language ? ' (' + data.language + ')' : '';
        let summary = '';

        if (nodeType === 'function') {
            summary = 'The function "' + nodeLabel + '"' + lang + ' is defined in a file that ' + (data.what_it_does || '').toLowerCase().replace(/^the code /, '');
        } else if (nodeType === 'class') {
            summary = 'The class "' + nodeLabel + '"' + lang + ' is part of a module that ' + (data.what_it_does || '').toLowerCase().replace(/^the code /, '');
        } else if (nodeType === 'api_endpoint') {
            summary = 'This API endpoint "' + nodeLabel + '"' + lang + ' belongs to a file that ' + (data.what_it_does || '').toLowerCase().replace(/^the code /, '');
        } else {
            summary = 'This ' + typeName + ' "' + nodeLabel + '"' + lang + ' is part of code that ' + (data.what_it_does || '').toLowerCase().replace(/^the code /, '');
        }

        return summary;
    }

    function navigateToNode(nodeId, addHistory) {
        const target = simNodeById.get(nodeId);
        if (!target) return;

        const prevId = addHistory ? selectedNodeId : null;
        selectedNodeId = target.id;
        showInspector(target, prevId);
        applyVisibility();
        panToNode(target);
    }

    function panToNode(d) {
        if (!svg || !zoomBehavior) return;
        const width  = svgEl.clientWidth  || 900;
        const height = svgEl.clientHeight || 600;
        const scale  = 1.5;
        const tx = width / 2 - d.x * scale;
        const ty = height / 2 - d.y * scale;

        svg.transition().duration(500)
            .call(zoomBehavior.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    }

    function metaRow(key, val) {
        return `<div class="inspector-meta-item"><span class="meta-key">${escHtml(String(key))}</span><span>${escHtml(String(val))}</span></div>`;
    }

    /* ── Tooltips ──────────────────────────────────────────────────────── */
    function showNodeTooltip(event, d) {
        tooltip.style.display = 'block';
        tooltip.querySelector('.tt-type').textContent = d.type.replace(/_/g, ' ');
        tooltip.querySelector('.tt-name').textContent = d.label;
        tooltip.querySelector('.tt-file').textContent = d.file || '';
        positionTooltip(event);
    }

    function showEdgeTooltip(event, d) {
        tooltip.style.display = 'block';
        tooltip.querySelector('.tt-type').textContent = 'relationship';
        tooltip.querySelector('.tt-name').textContent = d.type;
        const s = d.source.label || d.source;
        const t = d.target.label || d.target;
        tooltip.querySelector('.tt-file').textContent = `${s} → ${t}`;
        positionTooltip(event);
    }

    function hideTooltip() {
        tooltip.style.display = 'none';
    }

    function positionTooltip(event) {
        const x = event.clientX + 14;
        const y = event.clientY - 10;
        tooltip.style.left = `${Math.min(x, window.innerWidth - 260)}px`;
        tooltip.style.top  = `${Math.min(y, window.innerHeight - 120)}px`;
    }

    /* ── Zoom / drag ───────────────────────────────────────────────────── */
    function resetView() {
        /* Unpin all nodes */
        if (nodeGroup) {
            nodeGroup.selectAll('g.node').each(function(d) {
                if (d._pinned) {
                    d.fx = null;
                    d.fy = null;
                    d._pinned = false;
                    const color = d.color || NODE_COLORS[d.type] || '#94a3b8';
                    d3.select(this)
                        .classed('pinned', false)
                        .select('circle')
                        .attr('stroke', lighten(color, 40))
                        .attr('stroke-width', 1.5)
                        .attr('stroke-dasharray', null);
                }
            });
            simulation.alphaTarget(0.2).restart();
            setTimeout(() => simulation.alphaTarget(0), 800);
        }
        svg.transition().duration(500)
            .call(zoomBehavior.transform, d3.zoomIdentity);
    }

    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        /* Node stays pinned — fx/fy intentionally kept set */
        d._pinned = true;
        /* Update circle stroke to show pinned state */
        nodeGroup.selectAll('g.node')
            .filter(n => n.id === d.id)
            .classed('pinned', true)
            .select('circle')
            .attr('stroke', '#facc15')
            .attr('stroke-width', 2.5)
            .attr('stroke-dasharray', '4 2');
    }

    /* ── Stats ─────────────────────────────────────────────────────────── */
    function updateStats() {
        if (statNodes)  statNodes.textContent  = allNodes.length;
        if (statEdges)  statEdges.textContent  = allEdges.length;
        if (statVisible) statVisible.textContent = allNodes.length;
    }

    /* ── Helpers ───────────────────────────────────────────────────────── */
    function truncateLabel(str, max) {
        if (!str) return '';
        return str.length > max ? str.slice(0, max - 1) + '…' : str;
    }

    function escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function lighten(hex, amount) {
        const num = parseInt(hex.slice(1), 16);
        const r = Math.min(255, (num >> 16) + amount);
        const g = Math.min(255, ((num >> 8) & 0xff) + amount);
        const b = Math.min(255, (num & 0xff) + amount);
        return `rgb(${r},${g},${b})`;
    }

    function getCsrf() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }
})();
