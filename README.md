# 📡 RTK Monitor - LC29H GPS/RTK HAT

Aplikacja webowa do monitorowania GPS/RTK dla Raspberry Pi 4 z modułem Waveshare LC29H(DA) RTK HAT.

## 🎯 Funkcje

- ✅ **Status Fix** - No Fix / 2D / 3D / RTK Float / RTK Fixed
- ✅ **Dokładność pomiaru** - HDOP, PDOP, VDOP z interpretacją jakości
- ✅ **Satelity** - liczba używanych i widocznych satelitów
- ✅ **Pozycja GPS** - szerokość, długość, wysokość
- ✅ **Status RTK** - wiek korekcji różnicowych
- ✅ **Dane dodatkowe** - prędkość, kurs, timestamp
- ✅ **Real-time** - aktualizacja danych co 1 sekundę przez WebSocket
- ✅ **Responsywny** - działa na smartfonie i tablecie

## 📋 Wymagania

### Hardware
- Raspberry Pi 4 (lub nowszy)
- Waveshare LC29H(DA) RTK HAT
- Antena GPS/GNSS
- Karta microSD (min. 8GB)
- Zasilanie 5V/3A

### Software
- Raspberry Pi OS (Bullseye lub nowszy)
- Python 3.7+
- Dostęp do WiFi (do łączenia się ze smartfona)

## 🚀 Instalacja

### Krok 1: Montaż modułu LC29H HAT

1. Wyłącz Raspberry Pi
2. Nałóż moduł LC29H HAT na piny GPIO (40-pin header)
3. Podłącz antenę GPS do złącza IPEX na module
4. Umieść antenę w miejscu z widokiem na niebo

### Krok 2: Pobranie aplikacji

```bash
cd ~
git clone https://github.com/TWOJA_NAZWA/rtk_monitor.git
cd rtk_monitor
```

Lub skopiuj folder `rtk_monitor` na Raspberry Pi.

### Krok 3: Uruchomienie instalatora

```bash
chmod +x install.sh
./install.sh
```

Skrypt automatycznie:
- Zaktualizuje system
- Zainstaluje Python i zależności
- Włączy UART w konfiguracji
- Wyłączy konsolę szeregową na UART
- Utworzy środowisko wirtualne Python

⚠️ **WAŻNE**: Po instalacji może być wymagany restart systemu!

### Krok 4: Uruchomienie aplikacji

Po restarcie (jeśli był wymagany):

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 app.py
```

Powinieneś zobaczyć:

```
====================================================================
RTK Monitor - Aplikacja GPS/RTK dla Raspberry Pi
====================================================================

✓ Połączono z /dev/ttyAMA0 @ 115200 baud
✓ GPS Reader uruchomiony pomyślnie

📡 Czekam na dane GPS...

🌐 Aplikacja dostępna pod adresem:
   http://localhost:5000
   http://192.168.1.XXX:5000

💡 Użyj CTRL+C aby zatrzymać
```

### Krok 5: Połączenie ze smartfona

1. Upewnij się, że smartfon i Raspberry Pi są w tej samej sieci WiFi
2. Sprawdź IP Raspberry Pi: `hostname -I`
3. Otwórz przeglądarkę na smartfonie
4. Wejdź na adres: `http://IP_RASPBERRY_PI:5000`

Przykład: `http://192.168.1.100:5000`

## 🛠️ Konfiguracja

### Zmiana portu UART

Jeśli `/dev/ttyAMA0` nie działa, edytuj `app.py`:

```python
gps = GPSReader(port='/dev/ttyS0', baudrate=115200)  # lub /dev/serial0
```

Sprawdź dostępne porty:

```bash
ls -l /dev/tty*
```

### Weryfikacja połączenia GPS

Test czy moduł wysyła dane:

```bash
sudo cat /dev/ttyAMA0
```

Powinieneś zobaczyć strumień zdań NMEA zaczynających się od `$`.

Jeśli nic się nie pojawia:
1. Sprawdź fizyczne połączenie HAT z pinami GPIO
2. Sprawdź konfigurację UART w `/boot/firmware/config.txt`
3. Upewnij się, że antena GPS ma widok na niebo

## 🌐 Połączenie z ASG-EUPOS (RTK)

Aby uzyskać RTK Fixed (dokładność centymetrowa), podłącz się do sieci ASG-EUPOS.

### Krok 1: Rejestracja w ASG-EUPOS

1. Wejdź na: http://www.asgeupos.pl
2. Zarejestruj się (bezpłatne konto)
3. Otrzymasz login i hasło do NTRIP

### Krok 2: Konfiguracja NTRIP Client

Edytuj plik `ntrip_client.py`, sekcja `CONFIG`:

```python
CONFIG = {
    'host': 'www.asgeupos.pl',
    'port': 2101,
    'mountpoint': 'WARZ',  # wybierz najbliższy punkt
    'username': 'TWOJ_LOGIN',
    'password': 'TWOJE_HASLO',
    'lat': 52.2297,  # Twoja pozycja (przybliżona)
    'lon': 21.0122,
}
```

**Dostępne mountpointy** (stacje referencyjne):
- `WARZ` - Warszawa
- `KRAK` - Kraków
- `POZN` - Poznań
- `WROC` - Wrocław
- `GDNS` - Gdańsk
- `LODZ` - Łódź
- `KATO` - Katowice

Wybierz najbliższy punkt (zwykle w promieniu 50km).

### Krok 3: Uruchomienie NTRIP Client

W **nowym terminalu** (oprócz app.py):

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 ntrip_client.py
```

Po chwili powinieneś zobaczyć:

```
✓ Połączono z serwerem NTRIP
✓ Połączono z GPS na /dev/ttyAMA0
✓ NTRIP Client uruchomiony
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
```

### Krok 4: Czekaj na RTK Fix

Po otrzymaniu korekt RTK, moduł GPS zacznie konwergować do RTK Fixed:

- `GPS Fix` → `RTK Float` (po ~30 sek) → `RTK Fixed` (po ~2-5 min)

**RTK Fixed** daje dokładność **1-2 cm** w poziomie!

## 📊 Interpretacja danych

### Fix Type
- **No Fix** - brak sygnału GPS
- **2D Fix** - tylko szerokość/długość (słaby sygnał)
- **3D Fix** - pełna pozycja z wysokością
- **GPS Fix** - standardowy GPS (~5m dokładność)
- **DGPS Fix** - GPS różnicowy (~1m)
- **RTK Float** - RTK w trybie zmiennoprzecinkowym (~10-50cm)
- **RTK Fixed** - RTK w trybie całkowitym (~1-2cm) ✨

### DOP (Dilution of Precision)
Wskaźnik geometrycznego rozkładu satelitów:

- **HDOP** - dokładność pozioma (najważniejsza)
- **PDOP** - dokładność pozycji (3D)
- **VDOP** - dokładność wysokości

**Interpretacja:**
- < 2 - Idealnie 🟢
- 2-5 - Doskonale 🟢
- 5-10 - Dobrze 🟡
- 10-20 - Umiarkowanie 🟠
- \> 20 - Słabo 🔴

### Liczba satelitów
- **Satelity użyte** - wykorzystywane do obliczeń
- **Satelity widoczne** - wszystkie wykryte

**Minimum:** 4 satelity do 3D Fix  
**Idealnie:** 10+ satelitów

### Wiek korekcji RTK
Pokazuje jak stare są dane różnicowe z bazy RTK:
- < 5s - Doskonale ✅
- 5-15s - Dobrze
- \> 15s - Sprawdź połączenie NTRIP

## 🔧 Rozwiązywanie problemów

### Brak danych GPS
```bash
# Sprawdź czy UART jest włączony
grep "enable_uart" /boot/firmware/config.txt

# Sprawdź proces
ps aux | grep python

# Sprawdź logi
journalctl -u rtk_monitor -f
```

### ValueError: invalid async_mode specified

Jeśli widzisz ten błąd, reinstaluj zależności:

```bash
cd ~/rtk_monitor
source venv/bin/activate
pip uninstall -y Flask-SocketIO eventlet
pip install -r requirements.txt
python3 app.py
```

### Port szeregowy zajęty
```bash
# Wyłącz konsolę szeregową
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
```

### Brak RTK Fixed
- Sprawdź czy NTRIP Client działa
- Sprawdź login/hasło ASG-EUPOS
- Sprawdź czy wybrałeś najbliższą stację referencyjną
- Sprawdź widoczność nieba (min. 8 satelitów)
- Czekaj 5-10 minut na konwergencję

### Aplikacja nie działa na smartfonie
```bash
# Sprawdź IP Raspberry Pi
hostname -I

# Sprawdź czy port 5000 jest otwarty
sudo netstat -tlnp | grep 5000

# Sprawdź firewall (jeśli włączony)
sudo ufw allow 5000
```

**📖 Więcej rozwiązań problemów:** Zobacz [TROUBLESHOOTING.md](TROUBLESHOOTING.md) dla szczegółowych instrukcji.

## 🚀 Autostart przy boot

### Metoda 1: systemd service

Utwórz plik `/etc/systemd/system/rtk-monitor.service`:

```ini
[Unit]
Description=RTK Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rtk_monitor
ExecStart=/home/pi/rtk_monitor/venv/bin/python3 /home/pi/rtk_monitor/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Włącz:

```bash
sudo systemctl enable rtk-monitor
sudo systemctl start rtk-monitor
```

### Metoda 2: crontab

```bash
crontab -e
```

Dodaj linię:

```
@reboot sleep 30 && cd /home/pi/rtk_monitor && /home/pi/rtk_monitor/venv/bin/python3 app.py
```

## 📁 Struktura projektu

```
rtk_monitor/
├── app.py                 # Backend Flask + WebSocket
├── gps_reader.py          # Czytnik i parser NMEA
├── ntrip_client.py        # Klient NTRIP (opcjonalny)
├── requirements.txt       # Zależności Python
├── install.sh             # Skrypt instalacyjny
├── README.md              # Ta dokumentacja
├── templates/
│   └── index.html         # Frontend HTML
└── static/
    ├── style.css          # Style CSS
    └── script.js          # Logika JavaScript
```

## 📖 Technologie

- **Backend:** Python, Flask, Flask-SocketIO
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **Komunikacja:** WebSocket (Socket.IO)
- **GPS:** pyserial, pynmea2
- **RTK:** NTRIP protocol

## 🤝 Wsparcie

Jeśli masz problemy:
1. Sprawdź logi: `python3 app.py`
2. Sprawdź FAQ powyżej
3. Sprawdź dokumentację Waveshare: https://www.waveshare.com/wiki/LC29H(XX)_GPS/RTK_HAT

## 📝 Licencja

MIT License - używaj jak chcesz!

## 🎉 Enjoy your RTK adventures!

Masz pytania? Powodzenia z pomiarami centymetrowymi! 🎯
