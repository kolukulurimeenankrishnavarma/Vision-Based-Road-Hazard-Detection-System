const API_BASE = window.location.origin;

let isRunning = false;
let currentLat = null;
let currentLng = null;
let lastDetectionResult = false; 
const validatedHazards = new Set(); 
const announcedHazards = new Set(); // Prevent audio spam

// Settings State
let settings = {
    audioAlerts: true,
    visualAlerts: true
};

// DOM Elements
const video = document.getElementById("camera-feed");
const overlay = document.getElementById("detection-overlay");
const ctx = overlay.getContext("2d");
const startBtn = document.getElementById("start-btn");
const toggleViewBtn = document.getElementById("toggle-view-btn");
const toggleIcon = document.getElementById("toggle-icon");
const mapContainer = document.getElementById("map-container");
const cameraContainer = document.getElementById("camera-container");
const gpsStatus = document.getElementById("gps-status");
const backendStatus = document.getElementById("backend-status");
const nearbyCount = document.getElementById("nearby-count");
const nearbyCard = document.getElementById("nearby-card");
const alertBanner = document.getElementById("alert-banner");
const alertTextElement = document.querySelector(".alert-text");
const alertTitleElement = document.querySelector(".alert-title");
const captureCanvas = document.getElementById("capture-canvas");
const captureCtx = captureCanvas.getContext("2d");
const totalDetected = document.getElementById("total-detected");

// New UI Elements
const recordingIndicator = document.getElementById("recording-indicator");
const settingsBtn = document.getElementById("settings-btn");
const settingsMenu = document.getElementById("settings-menu");
const toggleVisual = document.getElementById("toggle-visual");
const toggleAudio = document.getElementById("toggle-audio");
const closeSettings = document.getElementById("close-settings");
const manualUpload = document.getElementById("manual-upload");
const stopBtn = document.getElementById("stop-btn");

// Leaflet Map Data
let map;
let marker;
let hazardMarkers = {}; 
let userPath = [];
let pathPolyline = null;
let sessionDetectionCount = 0;

let isCameraView = false;

// Initialize map right away so it is visible before "Start" is clicked
initMap();

startBtn.addEventListener("click", startRoadGuard);
stopBtn.addEventListener("click", stopRoadGuard);
toggleViewBtn.addEventListener("click", toggleView);

// Settings Listeners
// Fix: ensure the click area isn't blocked by other z-index elements
settingsBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    settingsMenu.classList.toggle("hidden");
});
closeSettings.addEventListener("click", () => settingsMenu.classList.add("hidden"));

// Global click to close settings menu if clicking outside
document.addEventListener("click", (e) => {
    if (!settingsMenu.classList.contains("hidden") && !settingsMenu.contains(e.target) && e.target !== settingsBtn) {
        settingsMenu.classList.add("hidden");
    }
});

const opMode = document.getElementById("op-mode");
opMode.addEventListener("change", (e) => {
    settings.mode = e.target.value;
    
    // Dynamically update UI if the system is actively running when the setting is changed
    if (isRunning) {
        if (settings.mode === "alerts") {
            // Stop Camera
            if (video.srcObject) {
                const tracks = video.srcObject.getTracks();
                tracks.forEach(track => track.stop());
                video.srcObject = null;
            }
            recordingIndicator.classList.add("hidden");
            toggleViewBtn.classList.add("hidden-view");
            if (isCameraView) toggleView(); // Force switch back to map view
            
            backendStatus.textContent = "Standby (Alerts Only)";
            backendStatus.className = "value waiting";
        } else {
            // "both" or "sending" modes require the camera to be active
            recordingIndicator.classList.remove("hidden");
            toggleViewBtn.classList.remove("hidden-view");
            if (!video.srcObject) {
                startCamera(); // Restart camera
            }
        }
    }
});

toggleVisual.addEventListener("change", (e) => settings.visualAlerts = e.target.checked);
toggleAudio.addEventListener("change", (e) => settings.audioAlerts = e.target.checked);

// Manual File Upload
manualUpload.addEventListener("change", handleFileUpload);

function toggleView() {
    isCameraView = !isCameraView;
    if (isCameraView) {
        mapContainer.classList.add("hidden-view");
        cameraContainer.classList.remove("hidden-view");
        toggleIcon.textContent = "🗺️";
    } else {
        cameraContainer.classList.add("hidden-view");
        mapContainer.classList.remove("hidden-view");
        toggleIcon.textContent = "📸";
        // Give map a moment to resize rendering after being unhidden
        setTimeout(() => map.invalidateSize(), 100);
    }
}

async function startRoadGuard() {
    // Hide start overlay panel completely to show the map underneath
    document.getElementById("start-overlay").classList.add("hidden"); 
    
    // Show Top Header controls that were hidden
    stopBtn.classList.remove("hidden");
    
    isRunning = true;
    startGPS();
    
    // Apply UI based on requested logic
    if (settings.mode !== "alerts") {
        recordingIndicator.classList.remove("hidden");
        toggleViewBtn.classList.remove("hidden-view"); // Show toggle button
        
        // Start the camera. It remains fully hidden from the user unless toggled.
        await startCamera();
    }
    
    // Start The Dual Loops
    startDetectionLoop();
    startAlertLoop();
}

function stopRoadGuard() {
    isRunning = false;
    
    // Stop camera stream
    if (video.srcObject) {
        const tracks = video.srcObject.getTracks();
        tracks.forEach(track => track.stop());
        video.srcObject = null;
    }
    
    document.getElementById("start-overlay").classList.remove("hidden");
    recordingIndicator.classList.add("hidden");
    stopBtn.classList.add("hidden");
    toggleViewBtn.classList.add("hidden-view");
    
    gpsStatus.textContent = "-";
    gpsStatus.className = "value waiting";
    backendStatus.textContent = "Offline";
    backendStatus.className = "value waiting";
    
    // Clear Map
    for (const id in hazardMarkers) {
        map.removeLayer(hazardMarkers[id]);
    }
    hazardMarkers = {};
    if (pathPolyline) {
        pathPolyline.setLatLngs([]);
    }
    userPath = [];
    sessionDetectionCount = 0;
    totalDetected.textContent = "0";
    nearbyCount.textContent = "0";
    alertBanner.classList.add("hidden");
}

function initMap() {
    // Initialize map centered roughly on a default coordinate, zoom 16
    map = L.map('map').setView([0, 0], 16);
    
    // Use free OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    // User path
    pathPolyline = L.polyline([], {color: '#0071e3', weight: 5, opacity: 0.8}).addTo(map);

    // Define a custom blue icon for the user's car
    const userIcon = L.divIcon({
        className: 'user-marker',
        html: '<div style="background-color: #2f81f7; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5);"></div>',
        iconSize: [26, 26],
        iconAnchor: [13, 13]
    });
    
    marker = L.marker([0, 0], {icon: userIcon}).addTo(map);
}

function startGPS() {
    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Center map on first fix
                if (!currentLat) {
                    map.setView([lat, lng], 16);
                }
                
                // Re-center gently
                map.panTo([lat, lng]);
                
                currentLat = lat;
                currentLng = lng;
                marker.setLatLng([lat, lng]);
                
                userPath.push([lat, lng]);
                pathPolyline.setLatLngs(userPath);
                
                gpsStatus.textContent = "Tracking";
                gpsStatus.className = "value active";
            },
            (err) => {
                console.error("GPS Error:", err);
                gpsStatus.textContent = "Error locating";
                gpsStatus.className = "value alert";
            },
            { enableHighAccuracy: true, maximumAge: 0, timeout: 5000 }
        );
    } else {
        gpsStatus.textContent = "Not supported";
    }
}

async function startCamera() {
    try {
        // Try strict rear camera first
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { exact: "environment" } },
                audio: false
            });
        } catch(e) {
            // Fallback to any camera if environment camera is not explicitly available
            console.warn("Could not get exact environment camera, falling back to any available video source.", e);
            stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: false
            });
        }
        
        video.srcObject = stream;
        
        // Wait for video to actually start playing to get accurate dimensions
        video.addEventListener('loadedmetadata', () => {
            overlay.width = video.videoWidth;
            overlay.height = video.videoHeight;
        }, { once: true });
        
        // Fix for iOS Safari blank video issue
        try {
            await video.play();
        } catch (e) {
            console.log("Auto-play prevented by browser, waiting for interaction.");
        }

    } catch (err) {
        console.error("Camera error:", err);
        alert("Camera error (or running in manual mode): " + err.message);
    }
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    backendStatus.textContent = "Processing Upload...";
    backendStatus.className = "value active";

    // Stop live tracking for the moment to favor video
    toggleAudio.checked = false; // Mute until processed? User preference.
    
    // Send to the backend endpoint
    try {
        const formData = new FormData();
        formData.append("video", file);
        
        const res = await fetch(`${API_BASE}/admin/uploads`, {
            method: 'POST',
            body: formData,
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        if(res.ok) {
            alert("File uploaded successfully.");
            backendStatus.textContent = "Upload Complete";
        } else {
            alert("Upload failed server-side.");
            backendStatus.textContent = "Upload Failed";
        }
    } catch (e) {
        console.error("Upload error:", e);
        alert("Error connecting to server for upload.");
        backendStatus.textContent = "Error";
    }
}


// Detection Loop (Send Frames to Backend)
async function startDetectionLoop() {
    while (isRunning) {
        if (settings.mode !== "alerts" && currentLat && currentLng && video.readyState === video.HAVE_ENOUGH_DATA) {
            captureCanvas.width = video.videoWidth;
            captureCanvas.height = video.videoHeight;
            captureCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
            
            const blob = await new Promise(resolve => captureCanvas.toBlob(resolve, 'image/jpeg', 0.8));
            
            if (blob) {
                const formData = new FormData();
                formData.append('lat', currentLat);
                formData.append('lng', currentLng);
                formData.append('frame', blob, 'frame.jpg');

                try {
                    const res = await fetch(`${API_BASE}/api/detect`, {
                        method: "POST",
                        body: formData,
                        headers: { 'ngrok-skip-browser-warning': 'true' }
                    });
                    
                    if (res.ok) {
                        const data = await res.json();
                        backendStatus.textContent = "Active / Detecting";
                        backendStatus.className = "value active";
                        lastDetectionResult = data.detected;
                        
                        if (data.detected && data.boxes) {
                            sessionDetectionCount += data.boxes.length;
                            totalDetected.textContent = sessionDetectionCount;
                        }

                        if (isCameraView) {
                            drawBoxes(data.boxes);
                        }
                    } else {
                        backendStatus.textContent = `API Error ${res.status}`;
                        backendStatus.className = "value alert";
                    }
                } catch (e) {
                    backendStatus.textContent = `Offline: ${e.message}`;
                    backendStatus.className = "value alert";
                }
            }
        }
        await new Promise(r => setTimeout(r, 1000)); // ≈ 1 FPS
    }
}

function drawBoxes(boxes) {
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    if (!boxes || boxes.length === 0) return;
    
    const scaleX = overlay.width / video.videoWidth;
    const scaleY = overlay.height / video.videoHeight;
    
    boxes.forEach(b => {
        let [xmin, ymin, xmax, ymax] = b.box;
        
        xmin *= scaleX;
        xmax *= scaleX;
        ymin *= scaleY;
        ymax *= scaleY;

        ctx.strokeStyle = "#f85149";
        ctx.lineWidth = 4;
        ctx.strokeRect(xmin, ymin, xmax - xmin, ymax - ymin);
        
        ctx.fillStyle = "#f85149";
        ctx.font = "bold 20px Inter";
        ctx.fillStyle = "rgba(0,0,0,0.7)";
        ctx.fillRect(xmin, ymin - 30, 200, 30);
        ctx.fillStyle = "#f85149";
        ctx.fillText(`HAZARD ${(b.confidence * 100).toFixed(0)}%`, xmin + 5, ymin - 8);
    });
}

function playAudioAlert(alertText) {
    if (!settings.audioAlerts) return; // Respect User Settings Toggle
    
    if ('speechSynthesis' in window) {
        // Cancel any currently playing speech to prioritize this alert
        window.speechSynthesis.cancel();
        
        const msg = new SpeechSynthesisUtterance(alertText || "Hazard ahead");
        msg.rate = 1.1; // Slightly faster for urgency
        msg.pitch = 1.0;
        window.speechSynthesis.speak(msg);
    }
}

// Alert & Validation Loop (Pull surrounding data)
async function startAlertLoop() {
    while (isRunning) {
        if (settings.mode !== "sending" && currentLat && currentLng) {
            try {
                const url = new URL(`${API_BASE}/api/nearby`);
                url.searchParams.append('lat', currentLat);
                url.searchParams.append('lng', currentLng);

                const res = await fetch(url, {
                    headers: { 'ngrok-skip-browser-warning': 'true' }
                });
                if (res.ok) {
                    const data = await res.json();
                    const hazards = data.hazards || [];
                    
                    nearbyCount.textContent = hazards.length;
                    
                    // Track valid IDs to remove stale markers
                    const activeHazardIds = new Set();
                    
                    let hasImminentThreat = false;

                    hazards.forEach(p => {
                        activeHazardIds.add(p.id);
                        
                        // Check threat level
                        if (p.distance <= 50) {
                            hasImminentThreat = true;
                            
                            // Audio Trigger: Output sound once per session per distinct hazard
                            if (!announcedHazards.has(p.id)) {
                                playAudioAlert(p.alert_text);
                                announcedHazards.add(p.id);
                            }
                        }

                        // Plot/Update on map
                        if (!hazardMarkers[p.id]) {
                            const customIcon = L.divIcon({
                                className: 'hazard-marker',
                                html: `<div style="background-color: ${p.color_hex || '#f85149'}; width: 24px; height: 24px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 15px ${p.color_hex || '#f85149'}cc; animation: pulseRed 1s infinite alternate;"></div>`,
                                iconSize: [30, 30],
                                iconAnchor: [15, 15]
                            });
                            hazardMarkers[p.id] = L.marker([p.lat, p.lng], {icon: customIcon}).addTo(map);
                            hazardMarkers[p.id].bindPopup(`⚠️ ${p.class_name || 'Hazard'} Detected!`);
                        }
                        
                        // Client-Side Validation check (auto-removal tagging)
                        if (p.distance <= 15.0 && !lastDetectionResult && !validatedHazards.has(p.id)) {
                            validatedHazards.add(p.id);
                            const vData = new FormData();
                            vData.append("hazard_id", p.id);
                            vData.append("detected", "false");
                            fetch(`${API_BASE}/api/validate`, { method: "POST", body: vData, headers: { 'ngrok-skip-browser-warning': 'true' } }).catch(e=>e);
                        }
                    });

                    // Remove markers that are no longer nearby or resolved
                    for (const id in hazardMarkers) {
                        if (!activeHazardIds.has(id)) {
                            map.removeLayer(hazardMarkers[id]);
                            delete hazardMarkers[id];
                        }
                    }

                    // Handle full UI banner logic
                    if (hasImminentThreat && settings.visualAlerts) { // Respect User Settings Toggle
                        // Find the closest hazard to display on the banner
                        let closest = hazards.reduce((prev, curr) => (prev.distance < curr.distance) ? prev : curr, hazards[0]);
                        if (closest) {
                            alertTitleElement.textContent = "HEADS UP";
                            alertTextElement.textContent = `${closest.class_name.toUpperCase()} AHEAD`;
                        }
                        alertBanner.classList.remove("hidden");
                        if ("vibrate" in navigator) navigator.vibrate([200, 100, 200]);
                    } else {
                        alertBanner.classList.add("hidden");
                    }
                }
            } catch (e) {
                console.error("Alert Loop Error:", e);
            }
        } else if (settings.mode === "sending") {
            // When exclusively sending data, hide all alerts and markers on the UI
            alertBanner.classList.add("hidden");
            for(const id in hazardMarkers) {
                map.removeLayer(hazardMarkers[id]);
                delete hazardMarkers[id];
            }
            nearbyCount.textContent = "0";
        }
        await new Promise(r => setTimeout(r, 3000));
    }
}
