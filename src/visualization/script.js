document.addEventListener('DOMContentLoaded', async () => {
    let graphData = null;
    let currentRange = '24h';

    // ── SVG coordinate system constants (from graph_analysis.md) ──
    const SVG_Y_TOP = 6;      // Top of the graph area (100% level, where guide lines start)
    const SVG_Y_BOTTOM = 35;  // Bottom of the graph area (0% level / baseline)
    const SVG_X_MIN = 10;     // Left edge of the graph area
    const SVG_X_MAX = 96;     // Right edge of the graph area
    const SVG_Y_RANGE = SVG_Y_BOTTOM - SVG_Y_TOP; // 29

    // ── DOM Elements ──
    const peakEl = document.getElementById('peak-value');
    const hlEl = document.getElementById('hl-value');
    const clearedEl = document.getElementById('cleared-value');
    const graphPath = document.getElementById('graph-path');
    const graphFill = document.getElementById('graph-fill');
    const gridLayer = document.getElementById('grid-layer');
    const markersLayer = document.getElementById('markers-layer');
    const labelsLayer = document.getElementById('labels-layer');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const svg = document.getElementById('main-graph');
    const tooltip = document.getElementById('tooltip');
    const hoverGuide = document.getElementById('hover-guide');
    const hoverPoint = document.getElementById('hover-point');
    const graphViewport = document.getElementById('graph-viewport');
    const peptideTitle = document.getElementById('peptide-title');
    const methodInfo = document.getElementById('method-info');

    // ── Load Data ──
    async function loadGraphData() {
        try {
            // Get peptide ID from URL parameter or return early
            const params = new URLSearchParams(window.location.search);
            const peptideId = params.get('peptideId');
            const method = params.get('method') || 'Injectable';

            if (!peptideId) {
                console.log('No peptideId parameter - waiting for user selection');
                return;
            }

            // Fetch from API endpoint
            const apiUrl = `/api/graph/${peptideId}?method=${encodeURIComponent(method)}`;
            console.log('Fetching:', apiUrl);
            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            graphData = await response.json();
            console.log('API Response:', graphData);
            updateHeaderInfo();
            renderGraph(currentRange);
        } catch (error) {
            console.error('Error loading graph data:', error);
        }
    }

    // Update header with peptide name and method
    function updateHeaderInfo() {
        if (graphData) {
            peptideTitle.textContent = graphData.peptide_name || 'Peptide Visualization';
            methodInfo.textContent = graphData.administration_method || 'Method';
        }
    }

    // Load data on page load
    loadGraphData();

    // ── Tab Switching ──
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const range = btn.dataset.range;
            if (range === currentRange) return;

            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentRange = range;
            renderGraph(range);
        });
    });

    // ══════════════════════════════════════════
    // ── RENDER GRAPH ──
    // ══════════════════════════════════════════

    function renderGraph(range) {
        const data = graphData[range];
        if (!data) return;

        // 1. Update Metadata
        peakEl.textContent = data.metadata.peak || '--';
        hlEl.textContent = data.metadata.half_life || '--';
        clearedEl.textContent = data.metadata.cleared || '--';

        // 2. Update Main Path — use the exact path_data from the JSON, no transformation
        graphPath.setAttribute('d', data.path_data);

        // 3. Update Fill Path — close the curve to baseline for gradient fill
        if (graphFill && data.path_data) {
            graphFill.setAttribute('d', `${data.path_data} L ${SVG_X_MAX} ${SVG_Y_BOTTOM} L ${SVG_X_MIN} ${SVG_Y_BOTTOM} Z`);
        }

        // 4. Update Markers — use exact marker coordinates from JSON
        updateMarkers(data.markers);

        // 5. Update Axes/Grid/Labels — use website-matching positions
        renderAxes(data.x_labels, data.y_labels);
    }

    // ══════════════════════════════════════════
    // ── MARKERS ──
    // Uses exact (cx, cy) from graph_data.json markers array
    // ══════════════════════════════════════════

    function updateMarkers(markers) {
        markersLayer.innerHTML = '';
        if (!markers) return;

        markers.forEach(m => {
            const isHalfLife = isHalfLifeColor(m.fill);
            const isPeak = isPeakColor(m.fill);

            // Draw vertical guide line for the Half-life marker (y=6 to y=35)
            if (isHalfLife) {
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', m.cx);
                line.setAttribute('x2', m.cx);
                line.setAttribute('y1', SVG_Y_TOP);  // Fixed: use y=6, matching the website
                line.setAttribute('y2', SVG_Y_BOTTOM);
                line.setAttribute('stroke', m.fill);
                line.setAttribute('class', 'marker-line');
                markersLayer.appendChild(line);
            }

            // Pulse ring animation behind the dot
            const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            pulse.setAttribute('cx', m.cx);
            pulse.setAttribute('cy', m.cy);
            pulse.setAttribute('r', m.r || 0.7);
            pulse.setAttribute('fill', 'none');
            pulse.setAttribute('stroke', m.fill);
            pulse.setAttribute('stroke-width', '0.15');
            pulse.setAttribute('class', 'marker-pulse');
            markersLayer.appendChild(pulse);

            // The dot itself — use exact radius from data (0.7)
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', m.cx);
            circle.setAttribute('cy', m.cy);
            circle.setAttribute('r', m.r || 0.7);
            circle.setAttribute('fill', m.fill);
            circle.setAttribute('class', 'marker-dot');
            markersLayer.appendChild(circle);
        });
    }

    // ══════════════════════════════════════════
    // ── AXES / GRID ──
    // Matches the website's exact SVG structure
    // ══════════════════════════════════════════

    function renderAxes(xLabels, yLabels) {
        gridLayer.innerHTML = '';
        labelsLayer.innerHTML = '';

        // 50% dashed grid line at y=20.5 (from analysis: the website uses y=20.5)
        const gridLine50 = createLine(SVG_X_MIN, 20.5, SVG_X_MAX, 20.5);
        gridLine50.setAttribute('class', 'grid-line grid-line-50');
        gridLayer.appendChild(gridLine50);

        // Baseline at y=35
        const baselineLine = createLine(SVG_X_MIN, SVG_Y_BOTTOM, SVG_X_MAX, SVG_Y_BOTTOM);
        baselineLine.setAttribute('class', 'grid-line grid-line-baseline');
        gridLayer.appendChild(baselineLine);

        // X-axis labels at y=43 (matching the website, not y=40)
        xLabels.forEach(label => {
            const text = createSvgText(label.pos, 43, label.text, 'middle');
            text.setAttribute('class', 'axis-text axis-text-x');
            labelsLayer.appendChild(text);
        });

        // Y-axis labels — use exact positions from data, placed at x=8.5 (matching website)
        yLabels.forEach(label => {
            const text = createSvgText(8.5, label.pos, label.text, 'end');
            text.setAttribute('class', 'axis-text axis-text-y');
            text.setAttribute('dominant-baseline', 'middle');
            labelsLayer.appendChild(text);
        });
    }

    // ── SVG Element Helpers ──

    function createLine(x1, y1, x2, y2) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x1);
        line.setAttribute('y1', y1);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y2);
        return line;
    }

    function createSvgText(x, y, content, anchor) {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', x);
        text.setAttribute('y', y);
        text.setAttribute('text-anchor', anchor);
        text.textContent = content;
        return text;
    }

    // ── Color Detection ──

    function isHalfLifeColor(fill) {
        const f = fill.toLowerCase();
        return f === '#f59e0b' || f === 'rgb(245, 158, 11)';
    }

    function isPeakColor(fill) {
        const f = fill.toLowerCase();
        return f === '#22c55e' || f === 'rgb(34, 197, 94)';
    }

    // ══════════════════════════════════════════
    // ── HOVER / TOOLTIP ──
    // ══════════════════════════════════════════

    /**
     * Get the total hours represented by the current range tab.
     */
    function getTotalHours(range) {
        const map = { '24h': 24, '7d': 168, '14d': 336, '30d': 720 };
        return map[range] || 24;
    }

    /**
     * Convert an SVG x-coordinate to a time value in hours using direct linear mapping.
     */
    function svgXToTime(svgX) {
        const totalHours = getTotalHours(currentRange);
        return ((svgX - SVG_X_MIN) / (SVG_X_MAX - SVG_X_MIN)) * totalHours;
    }

    /**
     * Format time in hours as a rounded readable label (e.g., "6h", "2d").
     */
    function formatTime(hours) {
        if (hours >= 24) {
            const days = Math.round(hours / 24);
            return `${days}d`;
        }
        if (hours < 1) {
            return `${Math.round(hours * 60)}m`;
        }
        return `${Math.round(hours)}h`;
    }

    /**
     * Convert an SVG y-coordinate to a percentage.
     * Uses y=6 (top, 100%) to y=35 (bottom, 0%) — fixed from analysis.
     */
    function interpolateYValue(svgY) {
        const pct = ((SVG_Y_BOTTOM - svgY) / SVG_Y_RANGE) * 100;
        return Math.max(0, Math.min(100, pct)).toFixed(1);
    }

    /**
     * Convert a mouse event to SVG coordinates.
     */
    function mouseToSVG(event) {
        const pt = svg.createSVGPoint();
        pt.x = event.clientX;
        pt.y = event.clientY;
        const ctm = svg.getScreenCTM().inverse();
        return pt.matrixTransform(ctm);
    }

    /**
     * Find the nearest data point to a given SVG x-coordinate.
     * Uses binary search for efficiency (points are sorted by x).
     */
    function findNearestPoint(svgX, points) {
        let lo = 0, hi = points.length - 1;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (points[mid].x < svgX) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        // Check if the previous point is closer
        if (lo > 0 && Math.abs(points[lo - 1].x - svgX) < Math.abs(points[lo].x - svgX)) {
            lo = lo - 1;
        }
        return points[lo];
    }

    // ── Mouse / Touch Event Handlers ──

    function handleHover(e) {
        const data = graphData?.[currentRange];
        if (!data || !data.points || data.points.length === 0) return;

        const svgCoord = mouseToSVG(e);

        // Only respond when within the graph area
        if (svgCoord.x < SVG_X_MIN - 1 || svgCoord.x > SVG_X_MAX + 1) {
            hideHover();
            return;
        }

        const nearest = findNearestPoint(svgCoord.x, data.points);

        // Position hover elements
        hoverGuide.setAttribute('x1', nearest.x);
        hoverGuide.setAttribute('x2', nearest.x);
        hoverGuide.style.opacity = '1';

        hoverPoint.setAttribute('cx', nearest.x);
        hoverPoint.setAttribute('cy', nearest.y);
        hoverPoint.style.opacity = '1';

        // Determine if hovering near a marker (within 1.5 SVG units in 2D space)
        let isPeakHovered = false;
        let isHLHovered = false;

        if (data.markers) {
            for (const m of data.markers) {
                const dx = nearest.x - m.cx;
                const dy = nearest.y - m.cy;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 1.5) {
                    if (isPeakColor(m.fill)) isPeakHovered = true;
                    if (isHalfLifeColor(m.fill)) isHLHovered = true;
                }
            }
        }

        // Calculate actual time label for the hovered point
        let actualTimeLabel = formatTime(svgXToTime(nearest.x));

        // Build tooltip content & style hover point
        let timeLabel = '';
        if (isPeakHovered && isHLHovered) {
            timeLabel = `Peak & Half-life (${actualTimeLabel})`;
            hoverPoint.setAttribute('fill', '#ef4444');
        } else if (isPeakHovered) {
            timeLabel = `Peak (${actualTimeLabel})`;
            hoverPoint.setAttribute('fill', '#22c55e');
        } else if (isHLHovered) {
            timeLabel = `Half-life (${actualTimeLabel})`;
            hoverPoint.setAttribute('fill', '#f59e0b');
        } else {
            timeLabel = actualTimeLabel;
            hoverPoint.setAttribute('fill', '#3b82f6');
        }

        // Get the interpolated percentage value
        let pctValueRaw = parseFloat(interpolateYValue(nearest.y));
        let pctValue = Math.round(pctValueRaw);

        // Position tooltip in DOM pixel space
        // Account for the corrected viewBox (100x45)
        const svgRect = svg.getBoundingClientRect();
        const viewportRect = graphViewport.getBoundingClientRect();
        const scaleX = svgRect.width / 100;   // viewBox width is 100
        const scaleY = svgRect.height / 45;    // viewBox height is 45 (FIXED from 50)

        const tooltipX = (nearest.x * scaleX) + svgRect.left - viewportRect.left;
        const tooltipY = (nearest.y * scaleY) + svgRect.top - viewportRect.top;

        tooltip.textContent = `${timeLabel} · ${pctValue}%`;
        tooltip.style.opacity = '1';
        tooltip.classList.add('visible');

        // Smart positioning: flip tooltip if it would overflow right
        const estimatedWidth = tooltip.offsetWidth || 150;
        if (tooltipX + estimatedWidth + 16 > viewportRect.width) {
            tooltip.style.left = `${tooltipX - estimatedWidth - 10}px`;
        } else {
            tooltip.style.left = `${tooltipX + 12}px`;
        }
        tooltip.style.top = `${tooltipY - 36}px`;
    }

    function hideHover() {
        hoverGuide.style.opacity = '0';
        hoverPoint.style.opacity = '0';
        tooltip.style.opacity = '0';
        tooltip.classList.remove('visible');
    }

    svg.addEventListener('mousemove', handleHover);
    svg.addEventListener('mouseleave', hideHover);

    // Touch support
    svg.addEventListener('touchmove', (e) => {
        e.preventDefault();
        const touch = e.touches[0];
        handleHover(touch);
    }, { passive: false });

    svg.addEventListener('touchend', hideHover);

    // ── Peptide Selector Handler ──
    const peptideSelect = document.getElementById('peptide-select');
    const methodSelect = document.getElementById('method-select');

    // Load peptide list on page load
    async function loadPeptidesList() {
        try {
            const response = await fetch('/api/peptides');
            if (!response.ok) throw new Error('Failed to load peptides list');
            const peptides = await response.json();
            peptideSelect.innerHTML = '<option value="">-- Select a peptide --</option>';
            peptides.forEach(p => {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = p.name;
                peptideSelect.appendChild(option);
            });

            // Pre-select from URL if available
            const params = new URLSearchParams(window.location.search);
            if (params.get('peptideId')) {
                peptideSelect.value = params.get('peptideId');
                if (params.get('method')) {
                    methodSelect.value = params.get('method');
                }
            }
        } catch (error) {
            console.error('Error loading peptides list:', error);
        }
    }

    // Load methods for selected peptide
    async function loadMethodsForPeptide(peptideId) {
        if (!peptideId) {
            methodSelect.innerHTML = '<option value="">-- Select method --</option>';
            return;
        }

        try {
            const response = await fetch(`/api/peptide/${peptideId}/methods`);
            if (!response.ok) throw new Error('Failed to load methods');
            const methods = await response.json();

            methodSelect.innerHTML = '<option value="">-- Select method --</option>';
            methods.forEach(m => {
                const option = document.createElement('option');
                option.value = m.name;
                option.textContent = m.name;
                methodSelect.appendChild(option);
            });

            // Auto-select first method if available
            if (methods.length > 0) {
                methodSelect.value = methods[0].name;
                currentRange = '24h';
                await loadAndRenderGraph(peptideId, methods[0].name);
            }
        } catch (error) {
            console.error('Error loading methods:', error);
        }
    }

    // Load and render graph
    async function loadAndRenderGraph(peptideId, method) {
        try {
            const response = await fetch(`/api/graph/${peptideId}?method=${encodeURIComponent(method)}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            graphData = await response.json();
            console.log('API Response:', graphData);
            updateHeaderInfo();
            renderGraph(currentRange);
        } catch (error) {
            console.error('Error loading graph data:', error);
        }
    }

    // Peptide selector change handler
    peptideSelect.addEventListener('change', () => {
        const peptideId = peptideSelect.value.trim();
        if (peptideId) {
            loadMethodsForPeptide(peptideId);
        }
    });

    // Method selector change handler
    methodSelect.addEventListener('change', () => {
        const peptideId = peptideSelect.value.trim();
        const method = methodSelect.value.trim();
        if (peptideId && method) {
            currentRange = '24h';
            loadAndRenderGraph(peptideId, method);
        }
    });

    // Load peptide list
    loadPeptidesList();
});
