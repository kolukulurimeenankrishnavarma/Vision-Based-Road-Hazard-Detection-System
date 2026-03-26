const API_BASE = `${window.location.origin}/admin`;

document.getElementById('login-btn').addEventListener('click', async () => {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errObj = document.getElementById('login-error');

    // Hardcoded bypass for the user's specific request
    if (username === "admin" && password === "GITAM") {
        document.getElementById('login-section').style.display = 'none';
        document.getElementById('dashboard-section').style.display = 'block';
        initDashboard();
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: username, password})
        });

        const data = await res.json();
        if (data.status === 'success') {
            document.getElementById('login-section').style.display = 'none';
            document.getElementById('dashboard-section').style.display = 'block';
            initDashboard();
        } else {
            errObj.textContent = "Invalid Admin Credentials.";
            errObj.style.display = "block";
        }
    } catch (e) {
        errObj.textContent = "Server offline or error";
        errObj.style.display = "block";
    }
});

let currentHazards = [];

function initDashboard() {
    loadHazards();
    loadUploads();
    
    // Refresh data periodically
    setInterval(loadHazards, 5000);
    setInterval(loadUploads, 5000);
}

// ============== Hazards Management ==============
async function loadHazards() {
    try {
        const res = await fetch(`${API_BASE}/hazards`);
        const data = await res.json();
        currentHazards = data.hazards || [];
        
        const tbody = document.querySelector('#hazards-table tbody');
        tbody.innerHTML = '';

        if(currentHazards.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8b949e;">No potholes detected yet.</td></tr>';
            return;
        }
        
        currentHazards.forEach(h => {
            const isResolved = h.status === 'RESOLVED';
            const className = h.hazard_classes ? h.hazard_classes.name : `Class ${h.class_id}`;
            // Removed strict 'pothole' filter to allow generic COCO objects
            
            const imageUrl = `${window.location.origin}/static/images/${h.id}.jpg`;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="font-family:monospace; font-size:12px; color:#8b949e;" title="${h.id}">${h.id.substring(0,8)}...</td>
                <td>
                    <a href="${imageUrl}" target="_blank">
                        <img src="${imageUrl}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px; border: 1px solid #30363d;" onerror="this.style.display='none'">
                    </a>
                </td>
                <td style="font-weight: 500;">${className}</td>
                <td>${(h.confidence * 100).toFixed(1)}%</td>
                <td style="font-family:monospace;">${h.lat.toFixed(5)}, ${h.lng.toFixed(5)}</td>
                <td><span class="status-badge ${isResolved ? 'status-resolved' : 'status-active'}">${h.status}</span></td>
                <td>
                    ${!isResolved ? `<button class="btn btn-outline" onclick="resolveHazard('${h.id}')">Mark Resolved</button>` : '—'}
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (e) {
        console.error("Failed to load hazards", e);
    }
}

async function resolveHazard(id) {
    if(!confirm("Mark this pothole as resolved/repaired?")) return;
    try {
        await fetch(`${API_BASE}/resolve/${id}`, { method: 'POST' });
        loadHazards();
    } catch (e) {
        alert("Action failed.");
    }
}

document.getElementById('export-csv-btn').addEventListener('click', () => {
    if (currentHazards.length === 0) {
        alert("No data to export.");
        return;
    }
    
    // Filter to only potholes
    const potholes = currentHazards.filter(h => {
        const cname = h.hazard_classes ? h.hazard_classes.name : '';
        return cname.toLowerCase() === 'pothole';
    });

    // Create CSV content
    const headers = ["ID", "Photo_URL", "Type", "Confidence", "Latitude", "Longitude", "Detection Count", "Status", "Last Detected"];
    const rows = potholes.map(h => [
        h.id,
        `${window.location.origin}/static/images/${h.id}.jpg`,
        h.hazard_classes ? h.hazard_classes.name : "Pothole",
        (h.confidence * 100).toFixed(2),
        h.lat,
        h.lng,
        h.detection_count,
        h.status,
        h.last_detected
    ]);

    let csvContent = "data:text/csv;charset=utf-8," 
        + headers.join(",") + "\n"
        + rows.map(e => e.join(",")).join("\n");

    // Trigger Download
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `potholes_export_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

// ============== Manual Uploads Management ==============
async function loadUploads() {
    try {
        const res = await fetch(`${API_BASE}/uploads`);
        const data = await res.json();
        
        const tbody = document.querySelector('#uploads-table tbody');
        tbody.innerHTML = '';
        
        if(!data.uploads || data.uploads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#8b949e;">No manual uploads found.</td></tr>';
            return;
        }

        data.uploads.forEach(u => {
            const isActive = u.status === 'active';
            const statusClass = isActive ? 'status-active' : 'status-inactive';
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="font-family:monospace; font-size:12px; color:#8b949e;" title="${u.id}">${u.id.substring(0,8)}...</td>
                <td style="font-weight: 500;">${u.filename}</td>
                <td>${new Date(u.upload_date).toLocaleString()}</td>
                <td><span class="status-badge ${statusClass}">${u.status}</span></td>
                <td class="action-cell">
                    ${isActive ? `<button class="btn btn-outline" onclick="deactivateUpload('${u.id}')">Deactivate</button>` : '—'}
                    <button class="btn btn-danger" onclick="deleteUpload('${u.id}')">Delete</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (e) {
        console.error("Failed to load uploads", e);
    }
}

async function deactivateUpload(id) {
    if(!confirm("Deactivate data from this manual upload?")) return;
    try {
        await fetch(`${API_BASE}/uploads/${id}/deactivate`, { method: 'POST' });
        loadUploads();
    } catch (e) {
        alert("Action failed.");
    }
}

async function deleteUpload(id) {
    if(!confirm("Permanently delete this manual upload from records?")) return;
    try {
        await fetch(`${API_BASE}/uploads/${id}`, { method: 'DELETE' });
        loadUploads();
    } catch (e) {
        alert("Action failed.");
    }
}
