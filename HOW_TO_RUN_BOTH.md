# 🚀 Uruchamianie RTK Monitor + NTRIP Client

## Jak uruchomić obie aplikacje jednocześnie?

Potrzebujesz **dwóch terminali** (lub użyj `screen`/`tmux`).

---

## Metoda 1: Dwa terminale (NAJŁATWIEJSZA)

### Terminal 1: RTK Monitor (aplikacja webowa)

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 app.py
```

**Zostaw to uruchomione!**

Powinieneś zobaczyć:
```
✓ Wykryto port UART: /dev/ttyS0
✓ GPS Reader uruchomiony pomyślnie
🌐 Aplikacja dostępna pod adresem:
   http://192.168.X.X:5000
```

### Terminal 2: NTRIP Client (korekcje RTK)

**Otwórz nowy terminal** (nowe SSH lub CTRL+ALT+T) i uruchom:

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 ntrip_client.py
```

Powinieneś zobaczyć:
```
🔍 Wykrywanie portu GPS...
✓ Wykryto port GPS: /dev/ttyS0
✓ Połączono z serwerem NTRIP
✓ Autoryzacja udana
✓ Połączono z GPS na /dev/ttyS0
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
```

**Zostaw oba terminale uruchomione!**

---

## Metoda 2: Screen (dla zaawansowanych)

### Instalacja screen:
```bash
sudo apt install screen
```

### Uruchom obie aplikacje:

```bash
cd ~/rtk_monitor
source venv/bin/activate

# Uruchom app.py w tle
screen -dmS rtk_app python3 app.py

# Poczekaj chwilę
sleep 3

# Uruchom ntrip_client.py w tle
screen -dmS rtk_ntrip python3 ntrip_client.py

# Sprawdź sesje
screen -ls
```

### Podłączanie do sesji:
```bash
# Podłącz do app.py
screen -r rtk_app

# Odłącz: CTRL+A, D

# Podłącz do ntrip_client.py
screen -r rtk_ntrip
```

### Zatrzymywanie:
```bash
# Zatrzymaj app.py
screen -S rtk_app -X quit

# Zatrzymaj ntrip_client.py
screen -S rtk_ntrip -X quit
```

---

## Metoda 3: Systemd (autostart przy boot)

Utwórz dwa service:

### rtk-app.service:
```bash
sudo nano /etc/systemd/system/rtk-app.service
```

```ini
[Unit]
Description=RTK Monitor App
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

### rtk-ntrip.service:
```bash
sudo nano /etc/systemd/system/rtk-ntrip.service
```

```ini
[Unit]
Description=RTK NTRIP Client
After=network.target rtk-app.service
Requires=rtk-app.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rtk_monitor
ExecStartPre=/bin/sleep 5
ExecStart=/home/pi/rtk_monitor/venv/bin/python3 /home/pi/rtk_monitor/ntrip_client.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Włącz autostart:
```bash
sudo systemctl enable rtk-app
sudo systemctl enable rtk-ntrip

sudo systemctl start rtk-app
sudo systemctl start rtk-ntrip

# Sprawdź status
sudo systemctl status rtk-app
sudo systemctl status rtk-ntrip
```

---

## ⚠️ Uwaga: Współdzielony port szeregowy

Obie aplikacje używają tego samego portu UART (np. `/dev/ttyS0`):
- `app.py` - **czyta** dane NMEA z GPS
- `ntrip_client.py` - **pisze** korekcje RTCM do GPS

To **może działać**, ale jeśli masz problemy:

### Rozwiązanie: Tylko NTRIP pisze, app.py czyta

W takiej konfiguracji:
1. `app.py` otwiera port w trybie read-only
2. `ntrip_client.py` otwiera port w trybie write-only
3. Teoretycznie nie powinno być konfliktu

Ale w praktyce, Linux **może blokować** drugi dostęp do tego samego portu.

### Jeśli widzisz błąd "Device or resource busy":

**Opcja A:** Uruchom najpierw app.py, potem ntrip_client.py  
**Opcja B:** Użyj tylko jednej aplikacji na raz  
**Opcja C:** Zmodyfikuj kod aby współdzielić port (zaawansowane)

---

## 🎯 Postęp RTK

Po uruchomieniu obu aplikacji obserwuj w przeglądarce:

```
http://IP_RASPBERRY:5000
```

**Postęp:**
```
No Fix (start)
    ↓ ~30 sekund
GPS Fix (5-10m dokładność)
    ↓ ~1-2 minuty (NTRIP wysyła korekcje)
RTK Float (10-50cm dokładność)
    ↓ ~2-5 minut (konwergencja)
RTK Fixed (1-2cm dokładność) ✨
```

**Wiek korekcji** powinien być **< 5 sekund**.

---

## 🔍 Sprawdzanie czy działa

### Sprawdź app.py:
```bash
ps aux | grep app.py
curl http://localhost:5000
```

### Sprawdź ntrip_client.py:
```bash
ps aux | grep ntrip_client.py
```

### Sprawdź port UART:
```bash
sudo lsof /dev/ttyS0
# Powinny być 2 procesy (python3)
```

---

## 📊 Monitorowanie

### Logi systemd:
```bash
journalctl -u rtk-app -f
journalctl -u rtk-ntrip -f
```

### Screen output:
```bash
screen -r rtk_app     # zobacz logi app.py
screen -r rtk_ntrip   # zobacz logi ntrip_client.py
```

---

## 🛑 Zatrzymywanie

### Ręczne (dwa terminale):
```
Terminal 1: CTRL+C (app.py)
Terminal 2: CTRL+C (ntrip_client.py)
```

### Screen:
```bash
screen -S rtk_app -X quit
screen -S rtk_ntrip -X quit
```

### Systemd:
```bash
sudo systemctl stop rtk-app
sudo systemctl stop rtk-ntrip
```

---

**Powodzenia z RTK Fixed! 🎯**
