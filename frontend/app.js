const API_BASE = "http://localhost:8000";

let isRunning = false;
let currentLat = null;
let currentLng = null;
let lastDetectionResult = false; 
const validatedPotholes = new Set(); 

// DOM Elements
const video = document.getElementById("camera-feed");
const overlay = document.getElementById("detection-overlay");
const ctx = overlay.getContext("2d");
const startBtn = document.getElementById("start-btn");
const gpsStatus = document.getElementById("gps-status");
const backendStatus = document.getElementById("backend-status");
const nearbyCount = document.getElementById("nearby-count");
const alertBanner = document.getElementById("alert-banner");
const captureCanvas = document.getElementById("capture-canvas");
const captureCtx = captureCanvas.getContext("2d");

startBtn.addEventListener("click", startRoadGuard);

async function startRoadGuard() {
    startBtn.style.display = "none";
    isRunning = true;
    
    startGPS();
    await startCamera();
    
    // Start The Dual Loops
    startDetectionLoop();
    startAlertLoop();
}

function startGPS() {
    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(
            (position) => {
                currentLat = position.coords.latitude;
                currentLng = position.coords.longitude;
                gpsStatus.textContent = `${currentLat.toFixed(5)}, ${currentLng.toFixed(5)}`;
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
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" },
            audio: false
        });
        video.srcObject = stream;
        
        // Match canvas to video size
        video.onloadedmetadata = () => {
            overlay.width = video.videoWidth;
            overlay.height = video.videoHeight;
        };
    } catch (err) {
        console.error("Camera error:", err);
        alert("Please allow camera access.");
    }
}

async function startDetectionLoop() {
    while (isRunning) {
        if (currentLat && currentLng && video.readyState === video.HAVE_ENOUGH_DATA) {
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
                    const res = await fetch(`${API_BASE}/detect`, {
                        method: "POST",
                        body: formData
                    });
                    
                    if (res.ok) {
                        const data = await res.json();
                        backendStatus.textContent = "Active / Detecting";
                        backendStatus.className = "value active";
                        lastDetectionResult = data.detected;
                        
                        drawBoxes(data.boxes);
                    } else {
                        backendStatus.textContent = "API Error";
                        backendStatus.className = "value alert";
                    }
                } catch (e) {
                    backendStatus.textContent = "Backend Offline";
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
    
    // Scale tracking since the video is object-fit: cover, but we simplify 
    // by assuming canvas size perfectly matches actual intrinsic video frames.
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
        ctx.fillRect(xmin, ymin - 30, 150, 30);
        ctx.fillStyle = "#f85149";
        ctx.fillText(`POTHOLE ${(b.confidence * 100).toFixed(0)}%`, xmin + 5, ymin - 8);
    });
}

async function startAlertLoop() {
    while (isRunning) {
        if (currentLat && currentLng) {
            try {
                const res = await fetch(`${API_BASE}/nearby?lat=${currentLat}&lng=${currentLng}`);
                if (res.ok) {
                    const data = await res.json();
                    const potholes = data.potholes || [];
                    
                    nearbyCount.textContent = potholes.length;
                    
                    const hasImminentThreat = potholes.some(p => p.distance <= 50);
                    
                    if (hasImminentThreat) {
                        alertBanner.classList.remove("hidden");
                        if ("vibrate" in navigator) navigator.vibrate([200, 100, 200]);
                    } else {
                        alertBanner.classList.add("hidden");
                    }
                    
                    // Client-Side Validation check
                    potholes.forEach(p => {
                        // If near pothole but YOLO didn't detect it recently
                        if (p.distance <= 15.0 && !lastDetectionResult && !validatedPotholes.has(p.id)) {
                            validatedPotholes.add(p.id);
                            
                            const vData = new FormData();
                            vData.append("pothole_id", p.id);
                            vData.append("detected", "false");
                            
                            fetch(`${API_BASE}/validate`, { method: "POST", body: vData })
                                .catch(e => console.error("Validation err:", e));
                        }
                    });
                }
            } catch (e) {
                console.error("Alert Loop Error:", e);
            }
        }
        await new Promise(r => setTimeout(r, 3000));
    }
}
