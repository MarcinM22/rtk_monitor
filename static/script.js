// RTK Monitor - Frontend JavaScript

const socket = io();

// Elementy DOM
const elements = {
    connectionStatus: document.getElementById('connection-status'),
    fixType: document.getElementById('fix-type'),
    fixQuality: document.getElementById('fix-quality'),
    satellites: document.getElementById('satellites'),
    satellitesVisible: document.getElementById('satellites-visible'),
    hdop: document.getElementById('hdop'),
    pdop: document.getElementById('pdop'),
    vdop: document.getElementById('vdop'),
    hdopQuality: document.getElementById('hdop-quality'),
    pdopQuality: document.getElementById('pdop-quality'),
    vdopQuality: document.getElementById('vdop-quality'),
    latitude: document.getElementById('latitude'),
    longitude: document.getElementById('longitude'),
    altitude: document.getElementById('altitude'),
    rtkAge: document.getElementById('rtk-age'),
    speed: document.getElementById('speed'),
    course: document.getElementById('course'),
    timestamp: document.getElementById('timestamp')
};

// Połączenie WebSocket
socket.on('connect', () => {
    console.log('✓ Połączono z serwerem');
    updateConnectionStatus(true);
});

socket.on('disconnect', () => {
    console.log('✗ Rozłączono z serwerem');
    updateConnectionStatus(false);
});

socket.on('status', (data) => {
    console.log('Status:', data.message);
});

// Odbieranie danych GPS
socket.on('gps_data', (data) => {
    updateDisplay(data);
});

// Funkcje aktualizacji UI
function updateConnectionStatus(connected) {
    if (connected) {
        elements.connectionStatus.textContent = 'Połączono';
        elements.connectionStatus.className = 'status-badge connected';
    } else {
        elements.connectionStatus.textContent = 'Rozłączono';
        elements.connectionStatus.className = 'status-badge disconnected';
    }
}

function updateDisplay(data) {
    // Fix Type
    if (data.fix_type) {
        elements.fixType.textContent = data.fix_type;
        elements.fixType.className = 'fix-status ' + getFixClass(data.fix_type);
    }
    
    elements.fixQuality.textContent = data.fix_quality || '-';
    
    // Satelity
    elements.satellites.textContent = data.satellites || 0;
    elements.satellitesVisible.textContent = data.satellites_visible || 0;
    
    // DOP
    updateDOP('hdop', data.hdop);
    updateDOP('pdop', data.pdop);
    updateDOP('vdop', data.vdop);
    
    // Pozycja
    elements.latitude.textContent = formatCoordinate(data.latitude, 'lat');
    elements.longitude.textContent = formatCoordinate(data.longitude, 'lon');
    elements.altitude.textContent = data.altitude ? `${data.altitude.toFixed(2)} m` : '-';
    
    // RTK
    elements.rtkAge.textContent = data.rtk_age ? `${data.rtk_age.toFixed(1)} s` : '-';
    
    // Prędkość i kurs
    elements.speed.innerHTML = data.speed ? `${data.speed.toFixed(1)} <small>km/h</small>` : '0.0 <small>km/h</small>';
    elements.course.textContent = data.course ? `${data.course.toFixed(1)}°` : '0.0°';
    
    // Timestamp
    if (data.timestamp) {
        elements.timestamp.textContent = data.timestamp;
    } else {
        const now = new Date();
        elements.timestamp.textContent = now.toLocaleTimeString('pl-PL');
    }
}

function getFixClass(fixType) {
    const fixTypeNormalized = fixType.toLowerCase().replace(/\s+/g, '-');
    
    if (fixType.includes('No Fix') || fixType.includes('Brak')) {
        return 'no-fix';
    } else if (fixType.includes('RTK Fixed')) {
        return 'rtk-fixed';
    } else if (fixType.includes('RTK Float')) {
        return 'rtk-float';
    } else if (fixType.includes('DGPS')) {
        return 'dgps-fix';
    } else if (fixType.includes('3D')) {
        return 'fix-3d';
    } else if (fixType.includes('2D')) {
        return 'fix-2d';
    } else if (fixType.includes('GPS')) {
        return 'gps-fix';
    }
    
    return 'no-fix';
}

function updateDOP(type, value) {
    const dopValue = elements[type];
    const dopQuality = elements[type + 'Quality'];
    
    if (value !== null && value !== undefined) {
        dopValue.textContent = value.toFixed(1);
        
        // Klasyfikacja jakości DOP
        let quality, className;
        if (value < 2) {
            quality = 'Idealnie';
            className = 'excellent';
        } else if (value < 5) {
            quality = 'Doskonale';
            className = 'excellent';
        } else if (value < 10) {
            quality = 'Dobrze';
            className = 'good';
        } else if (value < 20) {
            quality = 'Umiarkowanie';
            className = 'moderate';
        } else {
            quality = 'Słabo';
            className = 'poor';
        }
        
        dopQuality.textContent = quality;
        dopQuality.className = 'dop-quality ' + className;
    } else {
        dopValue.textContent = '99.9';
        dopQuality.textContent = '-';
        dopQuality.className = 'dop-quality';
    }
}

function formatCoordinate(value, type) {
    if (!value || value === 0) {
        return '-';
    }
    
    const hemisphere = type === 'lat' 
        ? (value >= 0 ? 'N' : 'S')
        : (value >= 0 ? 'E' : 'W');
    
    return `${Math.abs(value).toFixed(6)}° ${hemisphere}`;
}

// Żądaj danych co 1 sekundę (backup - WebSocket wysyła dane automatycznie)
setInterval(() => {
    socket.emit('request_data');
}, 1000);

console.log('RTK Monitor - Frontend załadowany');
