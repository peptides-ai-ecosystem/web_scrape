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
});
