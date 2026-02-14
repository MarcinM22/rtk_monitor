# 🏗️ Architektura RTK Monitor

## Diagram systemu

```
┌─────────────────────────────────────────────────────────────┐
│                     SMARTFON (Klient)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Przeglądarka Web                           │   │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  │   │
│  │  │   HTML     │  │     CSS      │  │ JavaScript  │  │   │
│  │  │ (widoki)   │  │  (styl UI)   │  │ (logika)    │  │   │
│  │  └────────────┘  └──────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ WebSocket (Socket.IO)
                            │ Real-time, bidirectional
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 RASPBERRY PI 4 (Serwer)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Flask + Flask-SocketIO                  │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  app.py - Backend HTTP + WebSocket            │  │   │
│  │  │  • Routing (/)                                 │  │   │
│  │  │  • WebSocket events (connect/disconnect)       │  │   │
│  │  │  • Background task (wysyłanie danych GPS)      │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            gps_reader.py - GPS Parser                │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  • Wątek czytający port szeregowy             │  │   │
│  │  │  • Parser NMEA (pynmea2)                       │  │   │
│  │  │  • Thread-safe data storage                    │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ↓ UART (115200 baud)             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          /dev/ttyAMA0 (UART interface)               │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓ GPIO Pins (40-pin header)
┌─────────────────────────────────────────────────────────────┐
│                  LC29H(DA) RTK HAT                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Quectel LC29H GNSS Receiver                         │   │
│  │  • GPS, GLONASS, BeiDou, Galileo                     │   │
│  │  • RTK capable (L1 + L5)                             │   │
│  │  • UART TX/RX ↔ RPi GPIO                             │   │
│  │  • NMEA 0183 output                                  │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓ RF Cable (IPEX connector)
                      ┌──────────┐
                      │  ANTENA  │
                      │  GPS/GNSS│
                      └──────────┘
                            │
                            ↓ Sygnał satelitarny
                      ☁ ☁ ☁ ☁ ☁
                    (Satelity GPS/GNSS)

┌─────────────────────────────────────────────────────────────┐
│             OPCJONALNIE: NTRIP dla RTK                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          ntrip_client.py - NTRIP Client              │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  • Połączenie TCP z serwerem ASG-EUPOS         │  │   │
│  │  │  • Odbieranie korekt RTCM                      │  │   │
│  │  │  • Przekazywanie do GPS przez UART             │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ Internet
                            ↓
                   www.asgeupos.pl:2101
                 (Stacje referencyjne RTK)
```

## Przepływ danych

### 1. GPS → Raspberry Pi

```
LC29H HAT → UART → /dev/ttyAMA0 → gps_reader.py
```

**Format danych:** NMEA 0183 (ASCII)

Przykładowe zdania NMEA:
```
$GNGGA,123519,5223.123,N,02101.234,E,4,12,0.9,100.5,M,45.0,M,3.5,0000*6A
$GNGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.2,0.9,0.8*3C
$GNRMC,123519,A,5223.123,N,02101.234,E,0.5,54.7,230218,003.1,W*6A
```

**Parser:**
- `pynmea2` dekoduje zdania NMEA
- Ekstrahuje: pozycję, fix type, DOP, satelity, prędkość, kurs

### 2. Raspberry Pi → Smartfon

```
gps_reader.py → app.py → WebSocket → Smartfon (JavaScript)
```

**Format danych:** JSON

```json
{
  "latitude": 52.2297,
  "longitude": 21.0122,
  "altitude": 100.5,
  "fix_type": "RTK Fixed",
  "fix_quality": 4,
  "satellites": 12,
  "satellites_visible": 15,
  "hdop": 0.8,
  "pdop": 1.2,
  "vdop": 0.7,
  "speed": 5.2,
  "course": 45.0,
  "rtk_age": 2.1,
  "timestamp": "12:35:19"
}
```

**Częstotliwość:** 1 Hz (co 1 sekundę)

### 3. NTRIP (RTK corrections)

```
ASG-EUPOS → Internet → ntrip_client.py → UART → LC29H HAT
```

**Format danych:** RTCM 3.x (binary)

**Proces:**
1. `ntrip_client.py` łączy się z `www.asgeupos.pl:2101`
2. Autoryzacja Basic Auth (login/hasło)
3. Wybór mountpoint (stacja referencyjna)
4. Odbieranie strumienia RTCM
5. Przekazywanie do GPS przez `/dev/ttyAMA0`
6. GPS używa korekt do RTK Fixed

## Komponenty backendu

### app.py - Główna aplikacja

**Zadania:**
- Serwer HTTP (Flask) - serwuje HTML/CSS/JS
- Serwer WebSocket (Socket.IO) - real-time komunikacja
- Background task - wysyła dane GPS co 1s
- Event handlers - obsługuje connect/disconnect

**Endpointy:**
- `GET /` - strona główna (index.html)
- `GET /static/*` - pliki statyczne (CSS/JS)

**WebSocket events:**
- `connect` - nowe połączenie klienta
- `disconnect` - rozłączenie
- `request_data` - żądanie danych GPS
- `gps_data` - wysyłanie danych do klienta

### gps_reader.py - Parser GPS

**Klasa GPSReader:**
```python
class GPSReader:
    def __init__(port, baudrate)
    def connect() -> bool
    def start() -> bool
    def stop()
    def get_data() -> dict
    def _read_loop()        # wątek
    def _parse_nmea(line)   # parser
```

**Thread safety:**
- Używa `threading.Lock()` do ochrony danych
- Wątek czytający działa w tle (daemon)
- `get_data()` zwraca kopię danych (thread-safe)

**Parsowane zdania NMEA:**
- `GGA` - pozycja, fix, satelity, HDOP
- `GSA` - DOP values, fix type
- `GSV` - widoczne satelity
- `RMC` - prędkość, kurs

### ntrip_client.py - Klient NTRIP

**Klasa NTRIPClient:**
```python
class NTRIPClient:
    def __init__(host, port, mountpoint, user, pass)
    def connect() -> bool
    def start() -> bool
    def stop()
    def _rtcm_loop()  # wątek odbierający RTCM
```

**Protokół:**
1. TCP connect do serwera
2. HTTP GET request z Basic Auth
3. Response: `ICY 200 OK`
4. Ciągły strumień RTCM bytes
5. Forward do GPS przez UART

## Frontend

### index.html - Struktura

**Layout:**
```
Header (tytuł, status połączenia)
  ↓
Cards (Status Fix, Satelity, DOP, Pozycja, RTK)
  ↓
Footer (linki)
```

**Responsive design:**
- Mobile-first (320px+)
- Grid layout dla kart
- Breakpoint @ 768px

### script.js - Logika

**Inicjalizacja:**
```javascript
const socket = io();  // WebSocket connection
```

**Event listeners:**
```javascript
socket.on('connect', ...)
socket.on('disconnect', ...)
socket.on('gps_data', updateDisplay)
```

**Update UI:**
```javascript
updateDisplay(data) {
  // Aktualizuj wszystkie elementy DOM
  // Formatuj współrzędne
  // Klasyfikuj DOP quality
  // Koloruj fix status
}
```

### style.css - Styling

**Design system:**
- Dark theme (granatowe tło)
- Color coding dla statusów:
  - 🔴 Red - No Fix
  - 🟠 Orange - GPS Fix
  - 🔵 Blue - DGPS
  - 🟣 Purple - RTK Float
  - 🟢 Green - RTK Fixed

**CSS Variables:**
```css
:root {
  --primary: #2563eb;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  ...
}
```

## Konfiguracja UART

### Raspberry Pi setup

**1. Enable UART in config.txt:**
```
enable_uart=1
dtoverlay=disable-bt
```

**2. Disable serial console:**
```bash
sudo systemctl disable serial-getty@ttyAMA0.service
```

**3. Pin mapping:**
```
GPIO 14 (TXD) → LC29H RXD
GPIO 15 (RXD) → LC29H TXD
```

**Baudrate:** 115200 (domyślnie dla LC29H)

## Performance

### Optymalizacje

**Backend:**
- Async I/O (eventlet)
- Thread pool dla WebSocket
- Minimalne parsowanie (tylko potrzebne pola)

**Frontend:**
- Vanilla JS (brak overhead frameworków)
- CSS animations w GPU (transform, opacity)
- Debouncing dla update (max 1 Hz)

### Resource usage

**Raspberry Pi 4:**
- CPU: ~5-10% (Python + WebSocket)
- RAM: ~50-80 MB
- Network: ~1 KB/s (WebSocket)

## Security

### Wbudowane zabezpieczenia

- **CORS:** Enabled (`cors_allowed_origins="*"`)
  - Dla produkcji: ustaw konkretne domeny
- **Secret key:** Zmień w app.py dla produkcji
- **NTRIP credentials:** Przechowuj w pliku config (nie w git)

### Rekomendacje

1. Firewall: `sudo ufw allow 5000`
2. HTTPS: Użyj reverse proxy (nginx)
3. Auth: Dodaj Basic Auth jeśli potrzeba

## Deployment

### Development
```bash
python3 app.py
```

### Production
```bash
# systemd service
sudo systemctl start rtk-monitor

# lub screen/tmux
screen -S rtk
python3 app.py
```

### Auto-start
```bash
sudo systemctl enable rtk-monitor
```

## Troubleshooting

### Debug logs

**Backend:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Frontend:**
```javascript
console.log('Debug:', data);
```

### Sprawdzanie portu

```bash
# Czy UART działa?
sudo cat /dev/ttyAMA0

# Czy aplikacja słucha?
sudo netstat -tlnp | grep 5000

# Czy proces działa?
ps aux | grep python
```

## Rozwój projektu

### Przyszłe funkcje

- ✨ Mapa na żywo (Leaflet.js)
- ✨ Historia pozycji (wykres trasy)
- ✨ Export do GPX/KML
- ✨ Multi-user support
- ✨ API REST dla danych GPS
- ✨ Notyfikacje (RTK Fixed achieved)

### Wkład

1. Fork repo
2. Stwórz branch (`git checkout -b feature/xyz`)
3. Commit (`git commit -am 'Add xyz'`)
4. Push (`git push origin feature/xyz`)
5. Pull Request

---

**Pytania?** Sprawdź README.md lub Issues na GitHub.
