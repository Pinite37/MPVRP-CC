// Tab switching functionality
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const tabName = this.getAttribute('data-tab');
        switchTab(tabName);
    });
});

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Add active class to clicked button
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}

// Mobile menu toggle
const menuToggle = document.getElementById('mobile-menu');
const navLinks = document.getElementById('nav-links');

if (menuToggle) {
    menuToggle.addEventListener('click', function() {
        navLinks.classList.toggle('active');
    });

    // Close menu when a link is clicked
    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', function() {
            navLinks.classList.remove('active');
        });
    });
}

// Generator form submission
async function handleGeneratorSubmit(event) {
    event.preventDefault();

    const btn = document.getElementById('gen-submit-btn');
    const statusDiv = document.getElementById('gen-status');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating...';

    // Show loading status
    statusDiv.style.display = 'block';
    statusDiv.className = 'status-message info';
    statusDiv.innerHTML = 'Generating instance...';

    try {
        // Collect form data
        const formData = {
            id_instance: document.getElementById('gen-id').value,
            nb_vehicules: parseInt(document.getElementById('gen-vehicles').value),
            nb_depots: parseInt(document.getElementById('gen-depots').value),
            nb_garages: parseInt(document.getElementById('gen-garages').value),
            nb_stations: parseInt(document.getElementById('gen-stations').value),
            nb_produits: parseInt(document.getElementById('gen-products').value),
            max_coord: parseInt(document.getElementById('gen-maxcoord').value) || null,
            min_capacite: parseInt(document.getElementById('gen-mincap').value) || null,
            max_capacite: parseInt(document.getElementById('gen-maxcap').value) || null,
            min_transition_cost: parseInt(document.getElementById('gen-mintrans').value) || null,
            max_transition_cost: parseInt(document.getElementById('gen-maxtrans').value) || null,
            min_demand: parseInt(document.getElementById('gen-mindemand').value) || null,
            max_demand: parseInt(document.getElementById('gen-maxdemand').value) || null,
            seed: document.getElementById('gen-seed').value ? parseInt(document.getElementById('gen-seed').value) : null
        };

        // Remove null values
        Object.keys(formData).forEach(key => formData[key] === null && delete formData[key]);

        const response = await fetch(`${window.APP_CONFIG.API_URL}/generator/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            // Get filename from response header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'instance.dat';
            if (contentDisposition) {
                const match = contentDisposition.match(/filename=([^;]+)/);
                if (match && match[1]) {
                    filename = match[1].replace(/"/g, '');
                }
            }

            // Download the file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            // Show success message
            statusDiv.className = 'status-message success';
            statusDiv.innerHTML = `✓ Instance generated successfully! File: <strong>${filename}</strong>`;
        } else {
            const errorData = await response.json();
            statusDiv.className = 'status-message error';
            statusDiv.innerHTML = `✗ Error: ${errorData.detail || 'Generation failed'}`;
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.innerHTML = `✗ Network error: ${error.message}`;
        console.error('Error:', error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Generate Instance';
    }
}

// Verifier form submission
async function handleVerifierSubmit(event) {
    event.preventDefault();

    const btn = document.getElementById('ver-submit-btn');
    const statusDiv = document.getElementById('ver-status');
    const resultsDiv = document.getElementById('ver-results');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Verifying...';

    // Show loading status
    statusDiv.style.display = 'block';
    statusDiv.className = 'status-message info';
    statusDiv.innerHTML = 'Verifying solution...';

    // Hide previous results
    resultsDiv.style.display = 'none';

    try {
        // Create FormData for file upload
        const formData = new FormData();
        const instanceFile = document.getElementById('ver-instance').files[0];
        const solutionFile = document.getElementById('ver-solution').files[0];

        if (!instanceFile || !solutionFile) {
            throw new Error('Both files are required');
        }

        formData.append('instance_file', instanceFile);
        formData.append('solution_file', solutionFile);

        const response = await fetch(`${window.APP_CONFIG.API_URL}/model/verify`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();

            statusDiv.className = 'status-message success';
            statusDiv.innerHTML = '✓ Verification complete!';

            displayVerificationResults(result);
        } else {
            const errorData = await response.json();
            statusDiv.className = 'status-message error';
            statusDiv.innerHTML = `✗ Error: ${errorData.detail || 'Verification failed'}`;
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.innerHTML = `✗ Error: ${error.message}`;
        console.error('Error:', error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Verify Solution';
    }
}

// Display verification results
function displayVerificationResults(result) {
    const resultsDiv = document.getElementById('ver-results');
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = '';

    // Header with feasibility status
    const header = document.createElement('div');
    header.className = 'results-header';
    header.innerHTML = `
        <h4>Verification Results</h4>
        <span class="result-status-badge ${result.feasible ? 'feasible' : 'infeasible'}">
            ${result.feasible ? '✓ FEASIBLE' : '✗ INFEASIBLE'}
        </span>
    `;
    resultsDiv.appendChild(header);

    // Errors section
    if (result.errors && result.errors.length > 0) {
        const errorSection = document.createElement('div');
        errorSection.className = 'results-section';
        errorSection.innerHTML = '<h5>Detected Issues</h5>';

        const errorsList = document.createElement('ul');
        errorsList.className = 'errors-list';
        result.errors.forEach(error => {
            const li = document.createElement('li');
            li.textContent = error;
            errorsList.appendChild(li);
        });

        errorSection.appendChild(errorsList);
        resultsDiv.appendChild(errorSection);
    } else if (result.feasible) {
        const noErrorsMsg = document.createElement('div');
        noErrorsMsg.className = 'results-section';
        noErrorsMsg.innerHTML = '<p style="color: #2e7d32; margin: 0;">✓ No feasibility issues detected.</p>';
        resultsDiv.appendChild(noErrorsMsg);
    }

    // Metrics section
    if (result.metrics) {
        const metricsSection = document.createElement('div');
        metricsSection.className = 'results-section';
        metricsSection.innerHTML = '<h5>Solution Metrics</h5>';

        const table = document.createElement('table');
        table.className = 'metrics-table';

        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        const th1 = document.createElement('th');
        th1.textContent = 'Metric';
        const th2 = document.createElement('th');
        th2.textContent = 'Value';
        headerRow.appendChild(th1);
        headerRow.appendChild(th2);
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Create body
        const tbody = document.createElement('tbody');
        for (const [key, value] of Object.entries(result.metrics)) {
            const row = document.createElement('tr');
            const td1 = document.createElement('td');
            td1.textContent = formatMetricName(key);
            const td2 = document.createElement('td');
            td2.textContent = formatMetricValue(value);
            row.appendChild(td1);
            row.appendChild(td2);
            tbody.appendChild(row);
        }
        table.appendChild(tbody);

        metricsSection.appendChild(table);
        resultsDiv.appendChild(metricsSection);
    }
}

// Format metric names for display
function formatMetricName(name) {
    // Convert snake_case to Title Case
    return name
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Format metric values for display
function formatMetricValue(value) {
    if (typeof value === 'number') {
        if (Number.isInteger(value)) {
            return value.toString();
        } else {
            return value.toFixed(2);
        }
    }
    return String(value);
}

