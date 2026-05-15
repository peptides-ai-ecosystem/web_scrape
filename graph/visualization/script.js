document.addEventListener('DOMContentLoaded', async () => {
    let graphData = null;
    let currentRange = '24h';

    // Elements
    const peakEl = document.getElementById('peak-value');
    const hlEl = document.getElementById('hl-value');
    const clearedEl = document.getElementById('cleared-value');
    const graphPath = document.getElementById('graph-path');
    const gridLayer = document.getElementById('grid-layer');
    const markersLayer = document.getElementById('markers-layer');
    const labelsLayer = document.getElementById('labels-layer');
    const tabBtns = document.querySelectorAll('.tab-btn');

    // Load Data
    try {
        // Assuming the json is in the parent directory relative to index.html
        const response = await fetch('../graph_data.json');
        graphData = await response.json();
        renderGraph(currentRange);
    } catch (error) {
        console.error('Error loading graph data:', error);
        alert('Failed to load graph data. Please ensure graph_data.json exists in the graph/ directory.');
    }

    // Tab Switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const range = btn.dataset.range;
            if (range === currentRange) return;

            // Update UI State
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            currentRange = range;
            renderGraph(range);
        });
    });

    function renderGraph(range) {
        const data = graphData[range];
        if (!data) return;

        // 1. Update Metadata
        peakEl.textContent = data.metadata.peak || '--';
        hlEl.textContent = data.metadata.half_life || '--';
        clearedEl.textContent = data.metadata.cleared || '--';

        // 2. Update Main Path
        graphPath.setAttribute('d', data.path_data);

        // 3. Update Markers
        updateMarkers(data.markers);

        // 4. Update Axes/Grid/Labels
        renderAxes(data.x_labels, data.y_labels);
    }

    function updateMarkers(markers) {
        markersLayer.innerHTML = '';
        markers.forEach(m => {
            // Create a vertical dashed line to the X-axis (y=35 is base)
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', m.cx);
            line.setAttribute('x2', m.cx);
            line.setAttribute('y1', m.cy);
            line.setAttribute('y2', '35');
            line.setAttribute('stroke', m.fill);
            line.setAttribute('class', 'marker-line');
            line.setAttribute('opacity', '0.5');
            markersLayer.appendChild(line);

            // Create the dot
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', m.cx);
            circle.setAttribute('cy', m.cy);
            circle.setAttribute('r', '0.8');
            circle.setAttribute('fill', m.fill);
            circle.setAttribute('class', 'marker-dot');
            markersLayer.appendChild(circle);
        });
    }

    function renderAxes(xLabels, yLabels) {
        gridLayer.innerHTML = '';
        labelsLayer.innerHTML = '';

        // Base X-axis line (assuming baseline is at y=35)
        const xAxisLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        xAxisLine.setAttribute('x1', '10');
        xAxisLine.setAttribute('x2', '96');
        xAxisLine.setAttribute('y1', '35');
        xAxisLine.setAttribute('y2', '35');
        xAxisLine.setAttribute('class', 'axis-line');
        gridLayer.appendChild(xAxisLine);

        // Render Grid Lines and Labels
        xLabels.forEach(label => {
            // Label text
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', label.pos);
            text.setAttribute('y', '40');
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('class', 'axis-text');
            text.textContent = label.text;
            labelsLayer.appendChild(text);
        });

        yLabels.forEach(label => {
            // Horizontal grid line
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', '10');
            line.setAttribute('x2', '96');
            line.setAttribute('y1', label.pos);
            line.setAttribute('y2', label.pos);
            line.setAttribute('class', 'grid-line');
            gridLayer.appendChild(line);

            // Label text
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', '8');
            text.setAttribute('y', label.pos);
            text.setAttribute('text-anchor', 'end');
            text.setAttribute('dominant-baseline', 'middle');
            text.setAttribute('class', 'axis-text');
            text.textContent = label.text;
            labelsLayer.appendChild(text);
        });
    }

    // ── Hover Tooltip Logic ──

    const svg = document.getElementById('main-graph');
    const tooltip = document.getElementById('tooltip');
    const hoverGuide = document.getElementById('hover-guide');
    const hoverPoint = document.getElementById('hover-point');
    const graphViewport = document.querySelector('.graph-viewport');

    /**
     * Convert an SVG x-coordinate to a human-readable time label
     * by linearly interpolating between the axis labels.
     */
    function interpolateXLabel(svgX, xLabels) {
        if (!xLabels || xLabels.length < 2) return svgX.toFixed(1);

        // Clamp to range
        if (svgX <= xLabels[0].pos) return xLabels[0].text;
        if (svgX >= xLabels[xLabels.length - 1].pos) return xLabels[xLabels.length - 1].text;

        // Find the two surrounding labels
        for (let i = 0; i < xLabels.length - 1; i++) {
            const a = xLabels[i];
            const b = xLabels[i + 1];
            if (svgX >= a.pos && svgX <= b.pos) {
                const t = (svgX - a.pos) / (b.pos - a.pos);
                // Parse numeric values from labels for interpolation
                const aVal = parseTimeLabel(a.text);
                const bVal = parseTimeLabel(b.text);
                if (aVal !== null && bVal !== null) {
                    const interpolated = aVal + t * (bVal - aVal);
                    return formatTimeValue(interpolated, b.text);
                }
                // Fallback: show fraction between the two
                return `${a.text} + ${(t * 100).toFixed(0)}%`;
            }
        }
        return svgX.toFixed(1);
    }

    /**
     * Parse a time label like "6h", "1d", "7d", "Dose" into hours.
     */
    function parseTimeLabel(label) {
        if (label === 'Dose') return 0;
        const hMatch = label.match(/^(\d+\.?\d*)h$/);
        if (hMatch) return parseFloat(hMatch[1]);
        const dMatch = label.match(/^(\d+\.?\d*)d$/);
        if (dMatch) return parseFloat(dMatch[1]) * 24;
        return null;
    }

    /**
     * Format an interpolated hour value back into a readable label.
     */
    function formatTimeValue(hours, contextLabel) {
        // If context uses days, format in days when > 24h
        if (contextLabel && contextLabel.includes('d') && hours >= 24) {
            const days = hours / 24;
            return days % 1 === 0 ? `${days}d` : `${days.toFixed(1)}d`;
        }
        if (hours >= 24) {
            const days = hours / 24;
            return days % 1 === 0 ? `${days}d` : `${days.toFixed(1)}d`;
        }
        if (hours % 1 === 0) return `${hours}h`;
        return `${hours.toFixed(1)}h`;
    }

    /**
     * Convert an SVG y-coordinate to a percentage.
     * The graph runs from y=8 (100%) to y=35 (0%).
     */
    function interpolateYValue(svgY) {
        const yTop = 8;    // 100%
        const yBottom = 35; // 0%
        const pct = ((yBottom - svgY) / (yBottom - yTop)) * 100;
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
     */
    function findNearestPoint(svgX, points) {
        let nearest = points[0];
        let minDist = Math.abs(svgX - nearest.x);
        for (const p of points) {
            const dist = Math.abs(svgX - p.x);
            if (dist < minDist) {
                minDist = dist;
                nearest = p;
            }
        }
        return nearest;
    }

    // Mouse Events
    svg.addEventListener('mousemove', (e) => {
        const data = graphData?.[currentRange];
        if (!data || !data.points || data.points.length === 0) return;

        const svgCoord = mouseToSVG(e);
        const nearest = findNearestPoint(svgCoord.x, data.points);

        // Position hover elements
        hoverGuide.setAttribute('x1', nearest.x);
        hoverGuide.setAttribute('x2', nearest.x);
        hoverGuide.style.opacity = '1';

        hoverPoint.setAttribute('cx', nearest.x);
        hoverPoint.setAttribute('cy', nearest.y);
        hoverPoint.style.opacity = '1';

        // Calculate real values
        const timeLabel = interpolateXLabel(nearest.x, data.x_labels);
        const pctValue = interpolateYValue(nearest.y);

        // Position tooltip (in DOM pixel space)
        const rect = graphViewport.getBoundingClientRect();
        const svgRect = svg.getBoundingClientRect();
        const scaleX = svgRect.width / 100; // viewBox is 0-100
        const tooltipX = (nearest.x * scaleX) + svgRect.left - rect.left;
        const tooltipY = (nearest.y / 50) * svgRect.height + svgRect.top - rect.top;

        tooltip.textContent = `${timeLabel} : ${pctValue}% remaining`;
        tooltip.style.opacity = '1';
        tooltip.style.left = `${tooltipX + 10}px`;
        tooltip.style.top = `${tooltipY - 30}px`;
    });

    svg.addEventListener('mouseleave', () => {
        hoverGuide.style.opacity = '0';
        hoverPoint.style.opacity = '0';
        tooltip.style.opacity = '0';
    });
});
