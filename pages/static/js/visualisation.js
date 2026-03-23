// ═══════════════════════════════════════════════════════════════
// STATE MANAGEMENT
// ═══════════════════════════════════════════════════════════════

let instance = { locations: {}, demands: [], depotSupplies: {} };
let solution = { routes: {}, objective: 0 };

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let width, height;

// Cached transform from instance coordinates to screen coordinates
let coordTransform = null;

// Pan and zoom state
let panOffset = { x: 0, y: 0 };
let zoomLevel = 1;
let isPanning = false;
let lastMousePos = { x: 0, y: 0 };

let isPlaying = false;
let progress = 0;
let speed = 1;
let maxProgress = 0;
let animationId;
let lastTime = 0;
let trucks = [];
let stationDemands = {};
let stationVisits = {};
let depotWithdrawals = {}; // Track withdrawals from depots per product
let dataLoaded = false;

// Exchange tracking
let totalExchanges = 0;
let currentExchanges = 0;

// Product swap tracking for notifications
let lastProductByTruck = {}; // Track last product for each truck
let shownSwapNotifications = {}; // Track which swaps have been notified

// Station deliveries tracking (per product)
let stationDeliveriesPerProduct = {}; // { stationId: { productIdx: delivered } }
let stationDemandsPerProduct = {}; // { stationId: { productIdx: demand } }

// Tooltip state
let hoveredNode = null;

const TRUCK_COLORS = [
    '#6366f1', '#22d3ee', '#f472b6', '#34d399', '#fbbf24',
    '#f87171', '#a78bfa', '#2dd4bf', '#fb923c', '#e879f9'
];

// ═══════════════════════════════════════════════════════════════
// THEME MANAGEMENT
// ═══════════════════════════════════════════════════════════════

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    document.getElementById('themeIcon').textContent = next === 'light' ? '☀️' : '🌙';
    draw();
}

// ═══════════════════════════════════════════════════════════════
// NOTIFICATION SYSTEM
// ═══════════════════════════════════════════════════════════════

function showSwapNotification(truckId, fromProduct, toProduct, truckColor) {
    const container = document.getElementById('notificationContainer');
    if (!container) return;

    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.innerHTML = `
        <div class="notification-icon">🔄</div>
        <div class="notification-content">
            <div class="notification-title">
                <span class="notification-truck" style="background: ${truckColor}"></span>
                ${truckId} Truck
            </div>
            <div class="notification-message">P${fromProduct} → P${toProduct}</div>
        </div>
    `;

    container.appendChild(notification);

    // Remove notification after animation completes
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

function clearAllNotifications() {
    const container = document.getElementById('notificationContainer');
    if (container) {
        container.innerHTML = '';
    }
}

// ═══════════════════════════════════════════════════════════════
// FILE UPLOAD HANDLING
// ═══════════════════════════════════════════════════════════════

function setupDragDrop(zoneId, inputId, type) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        zone.addEventListener(eventName, () => zone.classList.add('dragover'));
    });

    ['dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, () => zone.classList.remove('dragover'));
    });

    zone.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file, type);
    });

    input.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleFile(file, type);
    });
}

function handleFile(file, type) {
    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            const content = event.target.result;
            if (type === 'instance') {
                if (file.name.endsWith('.dat') || file.name.endsWith('.txt')) {
                    instance = parseDatInstance(content);
                } else {
                    instance = JSON.parse(content);
                }
                updateFileStatus('instance', file.name);
            } else {
                if (file.name.endsWith('.dat') || file.name.endsWith('.txt')) {
                    solution = parseDatSolution(content);
                } else {
                    solution = JSON.parse(content);
                }
                updateFileStatus('solution', file.name);
            }
            initData();
            resize();
        } catch (err) {
            alert('Error parsing file: ' + err.message);
            console.error(err);
        }
    };
    reader.readAsText(file);
}

function parseDatInstance(text) {
    const lines = text.trim().split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
    let lineIdx = 0;

    // Dimensions
    // Two conventions exist in the project history:
    //  A) num_products num_depots num_garages num_stations num_vehicles  (used by core/model parser)
    //  B) num_vehicles num_depots num_garages num_stations num_products  (seen in some docs)
    // We auto-detect by validating the change-cost matrix shape.
    const dims = lines[lineIdx++].split(/\s+/).map(Number);
    if (dims.length !== 5 || dims.some(n => Number.isNaN(n))) {
        throw new Error('Invalid dimensions line in instance .dat');
    }

    const candidates = [
        {
            name: 'products-first',
            numProducts: dims[0],
            numDepots: dims[1],
            numGarages: dims[2],
            numStations: dims[3],
            numVehicles: dims[4]
        },
        {
            name: 'vehicles-first',
            numVehicles: dims[0],
            numDepots: dims[1],
            numGarages: dims[2],
            numStations: dims[3],
            numProducts: dims[4]
        }
    ];

    function matrixLooksValid(startIdx, n) {
        if (!Number.isFinite(n) || n <= 0) return false;
        if (startIdx + n > lines.length) return false;
        for (let r = 0; r < n; r++) {
            const row = lines[startIdx + r].split(/\s+/).filter(Boolean);
            if (row.length < n) return false;
            if (row.slice(0, n).some(v => Number.isNaN(parseFloat(v)))) return false;
        }
        return true;
    }

    const chosen = candidates.find(c => matrixLooksValid(lineIdx, c.numProducts)) || candidates[0];
    const { numVehicles, numDepots, numProducts, numStations, numGarages } = chosen;

    // Skip Change Costs (numProducts lines)
    lineIdx += numProducts;

    // Skip Vehicles (numVehicles lines)
    lineIdx += numVehicles;

    const locations = {};
    const demands = [];
    const depotSupplies = {};

    // Parse Depots
    for (let i = 0; i < numDepots; i++) {
        const parts = lines[lineIdx++].split(/\s+/);
        const id = parts[0];
        const x = parseFloat(parts[1]);
        const y = parseFloat(parts[2]);
        locations[`D${id}`] = [x, y];

        // Parse depot supplies for each product
        const supplies = [];
        for (let p = 0; p < numProducts; p++) {
            supplies.push(parseFloat(parts[3 + p] || 0));
        }
        depotSupplies[`D${id}`] = supplies;
    }

    // Parse Garages
    for (let i = 0; i < numGarages; i++) {
        const parts = lines[lineIdx++].split(/\s+/);
        const id = parts[0];
        const x = parseFloat(parts[1]);
        const y = parseFloat(parts[2]);
        locations[`G${id}`] = [x, y];
    }

    // Parse Stations
    const stationDemandsPerProductLocal = {}; // Track per-product demands
    for (let i = 0; i < numStations; i++) {
        const parts = lines[lineIdx++].split(/\s+/);
        const id = parts[0];
        const x = parseFloat(parts[1]);
        const y = parseFloat(parts[2]);
        locations[`S${id}`] = [x, y];

        // Store per-product demands
        const productDemands = [];
        let totalDemand = 0;
        for (let p = 0; p < numProducts; p++) {
            const demand = parseFloat(parts[3 + p] || 0);
            productDemands.push(demand);
            totalDemand += demand;
        }
        stationDemandsPerProductLocal[`S${id}`] = productDemands;
        demands.push({ station: `S${id}`, quantity: totalDemand });
    }

    return {
        locations,
        demands,
        depotSupplies,
        stationDemandsPerProduct: stationDemandsPerProductLocal,
        num_vehicles: numVehicles,
        num_depots: numDepots,
        num_products: numProducts,
        num_stations: numStations,
        num_garages: numGarages
    };
}

function parseDatSolution(text) {
    const lines = text.trim().split('\n').map(l => l.trim()).filter(l => l);
    let lineIdx = 0;

    const solution = {
        routes: {},
        depotLoads: {}, // Track loading quantities at depots
        metrics: {}
    };

    // Parse vehicle routes until we reach metrics
    while (lineIdx < lines.length) {
        const line = lines[lineIdx];

        // Check if this is a vehicle line in format "ID: <route>"
        const idMatch = line.match(/^\s*(\d+)\s*:\s*(.*)$/);
        if (idMatch) {
            const vehicleId = parseInt(idMatch[1]);
            // route content after the colon
            let routeLine = idMatch[2].trim();
            lineIdx++;

            // Find next non-empty line for products
            while (lineIdx < lines.length && lines[lineIdx].trim() === '') {
                lineIdx++;
            }
            if (lineIdx >= lines.length) break;

            let productsLineRaw = lines[lineIdx].trim();
            // Remove optional "ID: " prefix from products line
            productsLineRaw = productsLineRaw.replace(/^\s*\d+\s*:\s*/, '');
            lineIdx++;

            // Parse the route (split by " - ") and build segments
            const routeParts = routeLine.split(' - ').map(p => p.trim());
            const segments = [];
            const vehicleLoads = []; // Track loads for this vehicle

            const extractNodeInfo = (token, position, lastPosition) => {
                // Token may be: "12", "12 [qty]", "12 (qty)", or typed "G2"/"D1"/"S5".
                const raw = String(token).trim();
                const base = raw.split('[', 1)[0].split('(', 1)[0].trim();

                // Extract quantity from brackets [qty] (depot load)
                const bracketMatch = raw.match(/\[(\d+(?:\.\d+)?)\]/);
                const loadQty = bracketMatch ? parseFloat(bracketMatch[1]) : 0;

                const typed = base.match(/^([GDS])(\d+)$/i);
                if (typed) {
                    return {
                        id: `${typed[1].toUpperCase()}${parseInt(typed[2], 10)}`,
                        loadQty
                    };
                }

                const numeric = base.match(/^(?:N)?(\d+)$/);
                if (!numeric) return { id: null, loadQty: 0 };
                const n = parseInt(numeric[1], 10);

                // New convention (no prefixes): infer by markers/position.
                let nodeId;
                if (raw.includes('[')) nodeId = `D#${n}`;
                else if (raw.includes('(')) nodeId = `S#${n}`;
                else if (position === 0 || position === lastPosition) nodeId = `G#${n}`;
                else nodeId = `G#${n}`;

                return { id: nodeId, loadQty };
            };

            const lastPos = routeParts.length - 1;
            for (let i = 0; i < routeParts.length - 1; i++) {
                const current = routeParts[i];
                const next = routeParts[i + 1];

                const fromInfo = extractNodeInfo(current, i, lastPos);
                const toInfo = extractNodeInfo(next, i + 1, lastPos);

                if (fromInfo.id && toInfo.id) {
                    segments.push([fromInfo.id, toInfo.id]);
                    // Track depot load if going to a depot with a load qty
                    if (toInfo.loadQty > 0) {
                        vehicleLoads.push({
                            segmentIdx: segments.length - 1,
                            nodeId: toInfo.id,
                            quantity: toInfo.loadQty
                        });
                    }
                }
            }

            solution.routes[`V${vehicleId}`] = segments;
            solution.depotLoads[`V${vehicleId}`] = vehicleLoads;

            // Skip empty line separators
            while (lineIdx < lines.length && lines[lineIdx].trim() === '') {
                lineIdx++;
            }
        } else {
            // We've reached the metrics section
            break;
        }
    }

    // Parse metrics (last 6 lines)
    if (lineIdx + 5 < lines.length) {
        solution.metrics = {
            vehicles_used: parseInt(lines[lineIdx]),
            product_changes: parseInt(lines[lineIdx + 1]),
            routing_cost: parseFloat(lines[lineIdx + 2]),
            total_cost: parseFloat(lines[lineIdx + 3]),
            solver: lines[lineIdx + 4],
            time: parseFloat(lines[lineIdx + 5])
        };

        solution.objective = solution.metrics.total_cost;
        solution.status = 'Solved';
    }

    return solution;
}

function mapNodeNumber(nodeStr, numGarages, numDepots, numStations) {
    // If already typed, pass through
    const typed = String(nodeStr).match(/^([GDS])(\d+)$/i);
    if (typed) return `${typed[1].toUpperCase()}${parseInt(typed[2], 10)}`;

    // Internal marked tokens from parseDatSolution: G#12 / D#3 / S#5
    const marked = String(nodeStr).match(/^([GDS])#(\d+)$/i);
    if (marked) {
        const kind = marked[1].toUpperCase();
        const n = parseInt(marked[2], 10);

        // If n fits the natural range for the kind, use it directly (no accumulation)
        if (kind === 'G' && n <= numGarages) return `G${n}`;
        if (kind === 'D' && n <= numDepots) return `D${n}`;
        if (kind === 'S' && n <= numStations) return `S${n}`;

        // Otherwise assume legacy offset numeric and map by accumulation
        if (kind === 'G') return (n <= numGarages) ? `G${n}` : `G${Math.max(1, n)}`;
        if (kind === 'D') {
            if (n <= numGarages + numDepots) return `D${n - numGarages}`;
            return `D${Math.max(1, n - numGarages)}`;
        }
        // S
        return `S${Math.max(1, n - numGarages - numDepots)}`;
    }

    // Accept both "N123" and "123"
    const match = String(nodeStr).match(/^(?:N)?(\d+)$/);
    if (!match) return nodeStr;

    const nodeNum = parseInt(match[1], 10);

    if (nodeNum <= numGarages) {
        return `G${nodeNum}`;
    } else if (nodeNum <= numGarages + numDepots) {
        return `D${nodeNum - numGarages}`;
    } else {
        return `S${nodeNum - numGarages - numDepots}`;
    }
}

function setTextContentById(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
}

function updateFileStatus(type, filename) {
    const statusEl = document.getElementById(type + 'Status');
    const zoneEl = document.getElementById(type + 'Zone');
    statusEl.textContent = '✅';
    zoneEl.classList.add('loaded');
    zoneEl.querySelector('.upload-label').textContent = filename.length > 15
        ? filename.substring(0, 12) + '...'
        : filename;
}

setupDragDrop('instanceZone', 'instanceUpload', 'instance');
setupDragDrop('solutionZone', 'solutionUpload', 'solution');

// ═══════════════════════════════════════════════════════════════
// DATA INITIALIZATION
// ═══════════════════════════════════════════════════════════════

function initData() {
    trucks = [];
    maxProgress = 0;
    progress = 0;
    isPlaying = false;
    stationDemands = {};
    stationVisits = {};
    depotWithdrawals = {};

    // Reset exchange tracking
    totalExchanges = solution.metrics?.product_changes || 0;
    currentExchanges = 0;

    // Reset product swap notification tracking
    lastProductByTruck = {};
    shownSwapNotifications = {};
    clearAllNotifications();

    // Reset station per-product tracking
    stationDemandsPerProduct = instance.stationDemandsPerProduct || {};
    stationDeliveriesPerProduct = {};

    // Initialize station deliveries
    Object.keys(stationDemandsPerProduct).forEach(stationId => {
        stationDeliveriesPerProduct[stationId] = stationDemandsPerProduct[stationId].map(() => 0);
    });

    // Reset pan/zoom
    panOffset = { x: 0, y: 0 };
    zoomLevel = 1;

    updatePlayBtn();

    // Process Demands
    (instance.demands || []).forEach(d => {
        stationDemands[d.station] = (stationDemands[d.station] || 0) + d.quantity;
    });

    // Get instance dimensions for node mapping
    const numGarages = instance.num_garages || 3;
    const numDepots = instance.num_depots || 2;
    const numStations = instance.num_stations || 5;

    // Process Routes
    Object.entries(solution.routes || {}).forEach(([id, segments], idx) => {
        if (!segments || segments.length === 0) return;

        // Convert node numbers to proper IDs
        const convertedSegments = segments.map(([from, to]) => {
            const fromId = mapNodeNumber(from, numGarages, numDepots, numStations);
            const toId = mapNodeNumber(to, numGarages, numDepots, numStations);
            return [fromId, toId];
        });

        trucks.push({
            id,
            color: TRUCK_COLORS[idx % TRUCK_COLORS.length],
            segments: convertedSegments,
            totalDist: 0
        });

        convertedSegments.forEach(([from, to]) => {
            if (to && to.startsWith('S')) {
                stationVisits[to] = (stationVisits[to] || 0) + 1;
            }
        });

        maxProgress = Math.max(maxProgress, convertedSegments.length);
    });

    // Update Stats
    const metrics = solution.metrics || {};
    setTextContentById('stat-dist', (metrics.total_cost || solution.objective || 0).toFixed(2));
    setTextContentById('stat-routing', (metrics.routing_cost || 0).toFixed(2));
    // setTextContentById('stat-exchanges', `0/${totalExchanges}`);
    setTextContentById('stat-trucks', metrics.vehicles_used || trucks.length);

    let totalSegs = trucks.reduce((sum, t) => sum + t.segments.length, 0);
    setTextContentById('stat-segments', totalSegs);
    setTextContentById('stat-status', solution.status || 'Loaded');

    // Update Fleet Legend
    const legendEl = document.getElementById('fleet-legend');
    if (trucks.length > 0) {
        legendEl.innerHTML = trucks.map(t => `
            <div class="fleet-item">
                <div class="fleet-color" style="background: ${t.color}"></div>
                <span>${t.id}</span>
            </div>
        `).join('');
    } else {
        legendEl.innerHTML = `<div class="fleet-placeholder">Load a solution</div>`;
    }

    // Update UI State
    dataLoaded = Object.keys(instance.locations).length > 0 && trucks.length > 0;
    document.getElementById('emptyState').style.display = dataLoaded ? 'none' : 'flex';
    document.getElementById('mapOverlay').style.display = dataLoaded ? 'flex' : 'none';

    updateUI();
}

// ═══════════════════════════════════════════════════════════════
// CANVAS & DRAWING
// ═══════════════════════════════════════════════════════════════

function resize() {
    const container = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = container.clientWidth * dpr;
    canvas.height = container.clientHeight * dpr;
    canvas.style.width = container.clientWidth + 'px';
    canvas.style.height = container.clientHeight + 'px';

    // Reset transform before applying device-pixel scaling; otherwise it accumulates
    // and the drawing progressively shrinks/grows on each resize.
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    width = container.clientWidth;
    height = container.clientHeight;

    computeCoordTransform();

    draw();
}

window.addEventListener('resize', resize);

function computeCoordTransform() {
    if (!instance.locations || Object.keys(instance.locations).length === 0 || !width || !height) {
        coordTransform = null;
        return;
    }

    // Compute tight bounds then add 30% margin on each axis (world-units) for better spacing
    const allPoints = Object.values(instance.locations);
    const allX = allPoints.map(p => p[0]);
    const allY = allPoints.map(p => p[1]);
    const rawMinX = Math.min(...allX), rawMaxX = Math.max(...allX);
    const rawMinY = Math.min(...allY), rawMaxY = Math.max(...allY);

    const rawW = rawMaxX - rawMinX;
    const rawH = rawMaxY - rawMinY;

    // Use 30% margin for better spacing, with minimum spacing of 50 units
    const marginX = Math.max(rawW > 0 ? 0.3 * rawW : 50, 50);
    const marginY = Math.max(rawH > 0 ? 0.3 * rawH : 50, 50);

    const minX = rawMinX - marginX;
    const maxX = rawMaxX + marginX;
    const minY = rawMinY - marginY;
    const maxY = rawMaxY + marginY;

    const worldW = (maxX - minX) || 1;
    const worldH = (maxY - minY) || 1;

    const scale = Math.min(width / worldW, height / worldH) * 1.5;

    // Center the drawing area
    const offsetX = (width - worldW * scale) / 2;
    const offsetY = (height - worldH * scale) / 2;

    coordTransform = { minX, minY, scale, offsetX, offsetY };
}

function getCoords(locId) {
    if (!instance.locations || !instance.locations[locId]) return { x: 0, y: 0 };

    if (!coordTransform) {
        computeCoordTransform();
    }
    if (!coordTransform) {
        return { x: 0, y: 0 };
    }

    const [x, y] = instance.locations[locId];
    const { minX, minY, scale, offsetX, offsetY } = coordTransform;

    // Apply base transform
    let screenX = offsetX + (x - minX) * scale;
    let screenY = offsetY + (y - minY) * scale;

    // Apply pan and zoom (zoom centered on canvas center)
    const centerX = width / 2;
    const centerY = height / 2;
    screenX = centerX + (screenX - centerX) * zoomLevel + panOffset.x;
    screenY = centerY + (screenY - centerY) * zoomLevel + panOffset.y;

    return { x: screenX, y: screenY };
}

function getThemeColor(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function drawGrid() {
    const gridSize = 40;
    ctx.strokeStyle = getThemeColor('--grid-color');
    ctx.lineWidth = 1;

    for (let x = 0; x <= width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }

    for (let y = 0; y <= height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }
}

function getStationSatisfaction(stationId, currentProgress) {
    if (!stationDemands[stationId]) return 1;

    let visitsSoFar = 0;
    const totalVisits = stationVisits[stationId] || 1;

    trucks.forEach(t => {
        const completedSegs = Math.floor(Math.min(currentProgress, t.segments.length));
        for (let i = 0; i < completedSegs; i++) {
            if (t.segments[i][1] === stationId) {
                visitsSoFar++;
            }
        }
    });

    return Math.min(1, visitsSoFar / totalVisits);
}

function drawNode(id, type) {
    const { x, y } = getCoords(id);

    // Glow effect
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, 35);
    if (type === 'garage') {
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    } else if (type === 'depot') {
        gradient.addColorStop(0, 'rgba(34, 211, 238, 0.3)');
    } else {
        gradient.addColorStop(0, 'rgba(244, 114, 182, 0.3)');
    }
    gradient.addColorStop(1, 'transparent');

    ctx.beginPath();
    ctx.arc(x, y, 35, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    // Base circle
    ctx.beginPath();
    ctx.arc(x, y, 22, 0, Math.PI * 2);
    ctx.fillStyle = getThemeColor('--node-bg');
    ctx.fill();
    ctx.strokeStyle = getThemeColor('--border-light');
    ctx.lineWidth = 2;
    ctx.stroke();

    // Icon
    ctx.font = '22px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    let icon = type === 'garage' ? '🏢' : type === 'depot' ? '🏪' : '⛽';
    ctx.fillText(icon, x, y + 1);

    // Label
    ctx.font = '600 11px Lato';
    ctx.fillStyle = getThemeColor('--text');
    ctx.fillText(id, x, y + 38);

    // Demand bar for stations
    if (type === 'station') {
        const satisfaction = getStationSatisfaction(id, progress);
        const demand = stationDemands[id] || 0;

        if (demand > 0) {
            const barWidth = 44;
            const barHeight = 6;
            const barX = x - barWidth / 2;
            const barY = y + 48;

            // Background
            ctx.fillStyle = getThemeColor('--input-bg');
            ctx.beginPath();
            ctx.roundRect(barX, barY, barWidth, barHeight, 3);
            ctx.fill();

            // Progress
            const fillColor = satisfaction >= 1 ? '#34d399' : '#fbbf24';
            ctx.fillStyle = fillColor;
            ctx.beginPath();
            ctx.roundRect(barX, barY, barWidth * satisfaction, barHeight, 3);
            ctx.fill();

            // Text
            ctx.font = '500 9px Lato';
            ctx.fillStyle = getThemeColor('--text-dim');
            ctx.fillText(`${Math.floor(demand * satisfaction)}/${demand}`, x, barY + 16);
        }
    }
}

function drawTruck(truck, currentProgress) {
    if (truck.segments.length === 0) return;

    let activeSegmentIdx = Math.floor(currentProgress);
    let t = currentProgress - activeSegmentIdx;

    if (activeSegmentIdx >= truck.segments.length) {
        activeSegmentIdx = truck.segments.length - 1;
        t = 1;
    }

    const [startId, endId] = truck.segments[activeSegmentIdx];
    const start = getCoords(startId);
    const end = getCoords(endId);

    const curX = start.x + (end.x - start.x) * t;
    const curY = start.y + (end.y - start.y) * t;

    // Draw completed route
    ctx.strokeStyle = truck.color;
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.setLineDash([]);

    ctx.beginPath();
    for (let i = 0; i < activeSegmentIdx; i++) {
        const [s, e] = truck.segments[i];
        const p1 = getCoords(s);
        const p2 = getCoords(e);
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
    }
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(curX, curY);
    ctx.stroke();

    // Draw remaining route (dashed)
    ctx.setLineDash([8, 8]);
    ctx.strokeStyle = truck.color + '40';
    ctx.beginPath();
    ctx.moveTo(curX, curY);
    ctx.lineTo(end.x, end.y);
    for (let i = activeSegmentIdx + 1; i < truck.segments.length; i++) {
        const [s, e] = truck.segments[i];
        const p1 = getCoords(s);
        const p2 = getCoords(e);
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw truck
    ctx.save();
    ctx.translate(curX, curY);

    const angle = Math.atan2(end.y - start.y, end.x - start.x);
    ctx.rotate(angle);

    // Glow
    const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, 25);
    glow.addColorStop(0, truck.color + '60');
    glow.addColorStop(1, 'transparent');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(0, 0, 25, 0, Math.PI * 2);
    ctx.fill();

    // Body
    ctx.fillStyle = truck.color;
    ctx.beginPath();
    ctx.roundRect(-16, -10, 26, 20, 5);
    ctx.fill();

    // Cabin
    ctx.fillStyle = 'rgba(255,255,255,0.9)';
    ctx.beginPath();
    ctx.roundRect(2, -7, 7, 14, 2);
    ctx.fill();

    // Wheels
    ctx.fillStyle = '#1a1a2e';
    ctx.beginPath();
    ctx.arc(-9, 12, 4, 0, Math.PI * 2);
    ctx.arc(4, 12, 4, 0, Math.PI * 2);
    ctx.arc(-9, -12, 4, 0, Math.PI * 2);
    ctx.arc(4, -12, 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}

function draw() {
    ctx.clearRect(0, 0, width, height);

    if (!dataLoaded) return;

    drawGrid();

    // Draw all routes first (background)
    trucks.forEach(truck => {
        if (truck.segments.length === 0) return;

        ctx.strokeStyle = truck.color + '20';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();

        truck.segments.forEach(([s, e]) => {
            const p1 = getCoords(s);
            const p2 = getCoords(e);
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
        });
        ctx.stroke();
        ctx.setLineDash([]);
    });

    // Draw nodes
    Object.keys(instance.locations).forEach(id => {
        let type = 'station';
        if (id.startsWith('G')) type = 'garage';
        if (id.startsWith('D')) type = 'depot';
        drawNode(id, type);
    });

    // Draw trucks on top
    trucks.forEach(truck => drawTruck(truck, progress));

    // Update overlay
    document.getElementById('overlayStatus').textContent =
        isPlaying ? 'Animating...' : `Step ${Math.floor(progress)} of ${maxProgress}`;
}

// ═══════════════════════════════════════════════════════════════
// ANIMATION & CONTROLS
// ═══════════════════════════════════════════════════════════════

function animate(timestamp) {
    if (!isPlaying) return;
    if (!lastTime) lastTime = timestamp;

    const dt = (timestamp - lastTime) / 1000;
    lastTime = timestamp;

    progress += dt * speed;

    if (progress >= maxProgress) {
        progress = maxProgress;
        isPlaying = false;
        updatePlayBtn();
    }

    updateUI();
    draw();

    if (isPlaying) {
        animationId = requestAnimationFrame(animate);
    }
}

function togglePlay() {
    if (!dataLoaded) return;

    isPlaying = !isPlaying;
    updatePlayBtn();

    if (isPlaying) {
        lastTime = 0;
        if (progress >= maxProgress) progress = 0;
        animationId = requestAnimationFrame(animate);
    } else {
        cancelAnimationFrame(animationId);
    }
}

function updatePlayBtn() {
    const btn = document.getElementById('playBtn');
    const icon = document.getElementById('playIcon');

    if (isPlaying) {
        btn.classList.add('playing');
        icon.textContent = '⏸';
    } else {
        btn.classList.remove('playing');
        icon.textContent = '▶';
    }
}

function reset() {
    isPlaying = false;
    progress = 0;
    cancelAnimationFrame(animationId);

    // Reset product swap notification tracking
    lastProductByTruck = {};
    shownSwapNotifications = {};
    clearAllNotifications();

    updatePlayBtn();
    updateUI();
    draw();
}

function stepForward() {
    if (!dataLoaded) return;
    progress = Math.min(maxProgress, Math.floor(progress) + 1);
    updateUI();
    draw();
}

function stepBackward() {
    if (!dataLoaded) return;
    progress = Math.max(0, Math.ceil(progress) - 1);
    updateUI();
    draw();
}

function seek(val) {
    progress = parseFloat(val);
    updateUI();
    draw();
}

function setSpeed(val) {
    speed = parseFloat(val);
    document.getElementById('speedText').textContent = speed + 'x';
}

function updateUI() {
    const slider = document.getElementById('timeline');
    slider.max = maxProgress || 1;
    slider.value = progress;

    document.getElementById('progressText').textContent =
        `${Math.floor(progress)}/${maxProgress}`;

    // Calculate current exchanges and station deliveries based on progress
    calculateCurrentExchangesAndDeliveries();

    // Update exchanges display
    // document.getElementById('stat-exchanges').textContent = `${currentExchanges}/${totalExchanges}`;

    // Update depot inventory panel
    updateDepotInventoryPanel();
}

// Calculate exchanges and station deliveries based on current progress
function calculateCurrentExchangesAndDeliveries() {
    currentExchanges = 0;

    // Reset station deliveries
    Object.keys(stationDemandsPerProduct).forEach(stationId => {
        stationDeliveriesPerProduct[stationId] = stationDemandsPerProduct[stationId].map(() => 0);
    });

    const numProducts = instance.num_products || 1;
    const numGarages = instance.num_garages || 1;
    const numDepots = instance.num_depots || 2;
    const numStations = instance.num_stations || 5;

    // Parse product lines from solution if available
    const productLines = solution.productLines || {};

    trucks.forEach((t, truckIdx) => {
        const vehicleKey = t.id;
        const completedSegs = Math.floor(Math.min(progress, t.segments.length));

        let lastProduct = null;

        for (let i = 0; i < completedSegs; i++) {
            const toNode = t.segments[i][1];

            // Check for product changes (exchanges)
            // In absence of detailed product tracking, estimate based on segment transitions
            // A product change typically happens when visiting different types of stations

            // Track deliveries to stations
            if (toNode && toNode.startsWith('S')) {
                const stationId = toNode;
                // Simulate delivery - distribute evenly across products for now
                // In a real implementation, this would use the solution's product line
                if (stationDeliveriesPerProduct[stationId]) {
                    const stationDemand = stationDemandsPerProduct[stationId] || [];
                    stationDemand.forEach((demand, pIdx) => {
                        if (demand > 0) {
                            // Calculate how much should be delivered per visit
                            const totalVisits = stationVisits[stationId] || 1;
                            const deliveryPerVisit = demand / totalVisits;
                            stationDeliveriesPerProduct[stationId][pIdx] += deliveryPerVisit;
                        }
                    });
                }
            }
        }

        // Estimate exchanges: count transitions between depot visits
        // (simplified - actual exchanges depend on product line in solution)
        let depotVisitCount = 0;
        let lastDepotProduct = lastProductByTruck[vehicleKey] || 1;

        for (let i = 0; i < completedSegs; i++) {
            const toNode = t.segments[i][1];
            if (toNode && toNode.startsWith('D')) {
                depotVisitCount++;
                if (depotVisitCount > 1) {
                    // Potential product change
                    currentExchanges++;

                    // Calculate a simulated product change (cycling through products)
                    const newProduct = ((lastDepotProduct % numProducts) + 1);
                    const swapKey = `${vehicleKey}-${i}`;

                    // Show notification if this swap hasn't been shown yet
                    if (!shownSwapNotifications[swapKey]) {
                        shownSwapNotifications[swapKey] = true;
                        showSwapNotification(vehicleKey, lastDepotProduct, newProduct, t.color);
                    }

                    lastDepotProduct = newProduct;
                }
            }
        }

        // Update last product tracking for this truck
        lastProductByTruck[vehicleKey] = lastDepotProduct;
    });

    // Cap exchanges at total (estimation may overshoot)
    currentExchanges = Math.min(currentExchanges, totalExchanges);
}

// ═══════════════════════════════════════════════════════════════
// SIDEBAR TOGGLE
// ═══════════════════════════════════════════════════════════════

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');

    sidebar.classList.toggle('collapsed');

    // Update toggle button position
    if (sidebar.classList.contains('collapsed')) {
        toggle.style.left = '0';
    } else {
        toggle.style.left = 'var(--sidebar-width)';
    }

    // Trigger resize after transition
    setTimeout(() => {
        resize();
    }, 300);
}

// ═══════════════════════════════════════════════════════════════
// PAN & ZOOM
// ═══════════════════════════════════════════════════════════════

canvas.addEventListener('mousedown', (e) => {
    isPanning = true;
    lastMousePos = { x: e.clientX, y: e.clientY };
    canvas.style.cursor = 'grabbing';
});

canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Handle panning
    if (isPanning) {
        const dx = e.clientX - lastMousePos.x;
        const dy = e.clientY - lastMousePos.y;

        panOffset.x += dx;
        panOffset.y += dy;

        lastMousePos = { x: e.clientX, y: e.clientY };
        draw();
        return;
    }

    // Handle tooltip for station hover
    handleNodeHover(mouseX, mouseY, e.clientX, e.clientY);
});

canvas.addEventListener('mouseup', () => {
    isPanning = false;
    canvas.style.cursor = 'grab';
});

canvas.addEventListener('mouseleave', () => {
    isPanning = false;
    canvas.style.cursor = 'grab';
    hideTooltip();
});

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();

    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.3, Math.min(5, zoomLevel * zoomFactor));

    // Zoom towards mouse position
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const centerX = width / 2;
    const centerY = height / 2;

    // Adjust pan to zoom towards mouse
    const zoomRatio = newZoom / zoomLevel;
    panOffset.x = mouseX - (mouseX - panOffset.x - centerX) * zoomRatio - centerX;
    panOffset.y = mouseY - (mouseY - panOffset.y - centerY) * zoomRatio - centerY;

    zoomLevel = newZoom;
    draw();
}, { passive: false });

// Double-click to reset view
canvas.addEventListener('dblclick', () => {
    panOffset = { x: 0, y: 0 };
    zoomLevel = 1;
    draw();
});

// Touch support for mobile
let touchStartDist = 0;
let touchStartZoom = 1;

canvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
        isPanning = true;
        lastMousePos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    } else if (e.touches.length === 2) {
        // Pinch zoom
        touchStartDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
        );
        touchStartZoom = zoomLevel;
    }
}, { passive: true });

canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();

    if (e.touches.length === 1 && isPanning) {
        const dx = e.touches[0].clientX - lastMousePos.x;
        const dy = e.touches[0].clientY - lastMousePos.y;

        panOffset.x += dx;
        panOffset.y += dy;

        lastMousePos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        draw();
    } else if (e.touches.length === 2) {
        const dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
        );
        zoomLevel = Math.max(0.3, Math.min(5, touchStartZoom * (dist / touchStartDist)));
        draw();
    }
}, { passive: false });

canvas.addEventListener('touchend', () => {
    isPanning = false;
});

// ═══════════════════════════════════════════════════════════════
// DEPOT INVENTORY TRACKING
// ═══════════════════════════════════════════════════════════════

function toggleDepotPanel() {
    const panel = document.getElementById('depotInventoryPanel');
    const btn = panel.querySelector('.depot-toggle');
    panel.classList.toggle('collapsed');
    btn.textContent = panel.classList.contains('collapsed') ? '+' : '−';
}

function updateDepotInventoryPanel() {
    const panel = document.getElementById('depotInventory');
    if (!panel) return;

    const numProducts = instance.num_products || 0;
    const depotSupplies = instance.depotSupplies || {};

    if (Object.keys(depotSupplies).length === 0) {
        panel.innerHTML = '<div class="depot-placeholder">Load an instance</div>';
        return;
    }

    // Calculate current inventory based on progress
    // Initialize with original supplies
    const currentInventory = {};
    const depotVisitCounts = {};
    const depotWithdrawalsTotal = {};

    for (const [depotId, supplies] of Object.entries(depotSupplies)) {
        currentInventory[depotId] = [...supplies];
        depotVisitCounts[depotId] = 0;
        depotWithdrawalsTotal[depotId] = supplies.map(() => 0);
    }

    // Get instance dimensions for node mapping
    const numGarages = instance.num_garages || 1;
    const numDepots = instance.num_depots || 2;
    const numStations = instance.num_stations || 5;

    // Calculate withdrawals from depots based on solution loads and current progress
    trucks.forEach((t, truckIdx) => {
        const vehicleKey = t.id;
        const vehicleLoads = solution.depotLoads?.[vehicleKey] || [];
        const completedSegs = Math.floor(Math.min(progress, t.segments.length));

        for (let i = 0; i < completedSegs; i++) {
            const toNode = t.segments[i][1];

            // Check if this segment ends at a depot
            if (toNode && toNode.startsWith('D')) {
                // Find the mapped depot ID
                const depotId = toNode;

                if (currentInventory[depotId]) {
                    depotVisitCounts[depotId] = (depotVisitCounts[depotId] || 0) + 1;

                    // Find the load for this segment
                    const loadInfo = vehicleLoads.find(l => l.segmentIdx === i);

                    if (loadInfo && loadInfo.quantity > 0) {
                        // We have actual load data - subtract from ALL products proportionally
                        // (simplified: in real scenario we'd track which product)
                        // For now, distribute withdrawal across products based on their ratios
                        const totalSupply = depotSupplies[depotId].reduce((a, b) => a + b, 0);
                        for (let p = 0; p < currentInventory[depotId].length; p++) {
                            const ratio = totalSupply > 0 ? depotSupplies[depotId][p] / totalSupply : 1 / numProducts;
                            const withdrawal = loadInfo.quantity * ratio;
                            currentInventory[depotId][p] -= withdrawal;
                            depotWithdrawalsTotal[depotId][p] += withdrawal;
                        }
                    }
                }
            }
        }
    });

    // Build HTML
    let html = '';
    const productColors = ['#6366f1', '#22d3ee', '#f472b6', '#34d399', '#fbbf24'];

    for (const [depotId, originalSupplies] of Object.entries(depotSupplies)) {
        const visits = depotVisitCounts[depotId] || 0;
        const currentStock = currentInventory[depotId];
        const hasNegative = currentStock.some(qty => qty < 0);

        html += `<div class="depot-card ${hasNegative ? 'depot-warning' : ''}">
            <div class="depot-header">
                <span class="depot-name">🏪 ${depotId}</span>
                <span class="depot-visits">${visits} visit${visits !== 1 ? 's' : ''}</span>
            </div>
            <div class="depot-products">`;

        currentStock.forEach((currentQty, idx) => {
            const color = productColors[idx % productColors.length];
            const originalQty = originalSupplies[idx];
            const isNegative = currentQty < 0;

            // Calculate percentage (can go below 0)
            const percent = originalQty > 0 ? Math.max(0, (currentQty / originalQty) * 100) : 0;

            // Format the quantity display
            const displayQty = Math.round(currentQty);
            const qtyClass = isNegative ? 'product-qty negative' : 'product-qty';

            html += `<div class="product-row ${isNegative ? 'negative' : ''}">
                <span class="product-label" style="background: ${color}20; color: ${color}">P${idx + 1}</span>
                <div class="product-bar-bg">
                    <div class="product-bar" style="width: ${percent}%; background: ${isNegative ? '#ef4444' : color}"></div>
                </div>
                <span class="${qtyClass}">${displayQty}</span>
            </div>`;
        });

        html += `</div></div>`;
    }

    panel.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════
// STATION TOOLTIP
// ═══════════════════════════════════════════════════════════════

function handleNodeHover(mouseX, mouseY, clientX, clientY) {
    if (!dataLoaded) return;

    const tooltip = document.getElementById('tooltip');
    let foundNode = null;
    const hitRadius = 30; // Pixel radius for hover detection

    // Check if mouse is over any node
    for (const [id, coords] of Object.entries(instance.locations)) {
        const { x, y } = getCoords(id);
        const dist = Math.sqrt((mouseX - x) ** 2 + (mouseY - y) ** 2);

        if (dist < hitRadius) {
            foundNode = id;
            break;
        }
    }

    if (foundNode) {
        hoveredNode = foundNode;
        showTooltip(foundNode, clientX, clientY);
    } else {
        hoveredNode = null;
        hideTooltip();
    }
}

function showTooltip(nodeId, clientX, clientY) {
    const tooltip = document.getElementById('tooltip');

    let content = '';
    const productColors = ['#6366f1', '#22d3ee', '#f472b6', '#34d399', '#fbbf24'];

    if (nodeId.startsWith('S')) {
        // Station tooltip - show demand fulfillment
        const demands = stationDemandsPerProduct[nodeId] || [];
        const deliveries = stationDeliveriesPerProduct[nodeId] || [];

        content = `<div class="tooltip-header">⛽ ${nodeId}</div>`;
        content += '<div class="tooltip-content">';

        if (demands.length > 0) {
            demands.forEach((demand, idx) => {
                const delivered = Math.round(deliveries[idx] || 0);
                const demandRounded = Math.round(demand);
                const excess = delivered - demandRounded;
                const isExcess = excess > 0;
                const isShortage = delivered < demandRounded && demand > 0;
                const color = productColors[idx % productColors.length];

                const percent = demand > 0 ? Math.min(100, (delivered / demand) * 100) : 100;

                let statusClass = '';
                let statusText = '';
                if (isExcess) {
                    statusClass = 'excess';
                    statusText = ` (+${excess})`;
                } else if (isShortage) {
                    statusClass = 'shortage';
                }

                content += `<div class="tooltip-product ${statusClass}">
                    <span class="tooltip-product-label" style="background: ${color}20; color: ${color}">P${idx + 1}</span>
                    <div class="tooltip-bar-bg">
                        <div class="tooltip-bar" style="width: ${percent}%; background: ${isExcess ? '#f59e0b' : color}"></div>
                    </div>
                    <span class="tooltip-qty ${statusClass}">${delivered}/${demandRounded}${statusText}</span>
                </div>`;
            });

            // Summary
            const totalDemand = demands.reduce((a, b) => a + b, 0);
            const totalDelivered = deliveries.reduce((a, b) => a + b, 0);
            const totalExcess = totalDelivered - totalDemand;

            content += `<div class="tooltip-summary">`;
            content += `<span>Total: ${Math.round(totalDelivered)}/${Math.round(totalDemand)}</span>`;
            if (totalExcess > 0) {
                content += `<span class="tooltip-excess-badge">+${Math.round(totalExcess)} excess</span>`;
            } else if (totalExcess < 0) {
                content += `<span class="tooltip-shortage-badge">${Math.round(totalExcess)} remaining</span>`;
            }
            content += `</div>`;
        } else {
            content += '<div class="tooltip-empty">No demand data</div>';
        }

        content += '</div>';
    } else if (nodeId.startsWith('D')) {
        // Depot tooltip
        const supplies = instance.depotSupplies?.[nodeId] || [];
        content = `<div class="tooltip-header">🏪 ${nodeId}</div>`;
        content += '<div class="tooltip-content">';

        if (supplies.length > 0) {
            supplies.forEach((supply, idx) => {
                const color = productColors[idx % productColors.length];
                content += `<div class="tooltip-product">
                    <span class="tooltip-product-label" style="background: ${color}20; color: ${color}">P${idx + 1}</span>
                    <span class="tooltip-qty">${Math.round(supply)} units</span>
                </div>`;
            });
        }
        content += '</div>';
    } else if (nodeId.startsWith('G')) {
        // Garage tooltip
        content = `<div class="tooltip-header">🏢 ${nodeId}</div>`;
        content += '<div class="tooltip-content"><div class="tooltip-empty">Vehicle depot</div></div>';
    }

    tooltip.innerHTML = content;
    tooltip.style.opacity = '1';

    // Position tooltip
    const tooltipRect = tooltip.getBoundingClientRect();
    let left = clientX + 15;
    let top = clientY + 15;

    // Keep tooltip on screen
    if (left + tooltipRect.width > window.innerWidth) {
        left = clientX - tooltipRect.width - 15;
    }
    if (top + tooltipRect.height > window.innerHeight) {
        top = clientY - tooltipRect.height - 15;
    }

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('tooltip');
    tooltip.style.opacity = '0';
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Press 'B' to toggle sidebar
    if (e.key === 'b' || e.key === 'B') {
        if (e.target.tagName !== 'INPUT') {
            toggleSidebar();
        }
    }
    // Press 'T' to toggle theme
    if (e.key === 't' || e.key === 'T') {
        if (e.target.tagName !== 'INPUT') {
            toggleTheme();
        }
    }
    // Press Space to play/pause
    if (e.key === ' ') {
        if (e.target.tagName !== 'INPUT') {
            e.preventDefault();
            togglePlay();
        }
    }
    // Press 'R' to reset view
    if (e.key === 'r' || e.key === 'R') {
        if (e.target.tagName !== 'INPUT') {
            panOffset = { x: 0, y: 0 };
            zoomLevel = 1;
            draw();
        }
    }
});

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

resize();
updateUI();
draw();
