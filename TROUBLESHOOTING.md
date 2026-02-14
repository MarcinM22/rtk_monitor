# 🔧 Rozwiązywanie problemów - RTK Monitor

## ❌ ValueError: invalid async_mode specified

### Problem
```
ValueError: Invalid async_mode specified
```

### Rozwiązanie
Ten błąd występuje gdy Flask-SocketIO nie może znaleźć odpowiedniego backendu async.

**Opcja 1: Reinstalacja zależności (zalecane)**
```bash
cd ~/rtk_monitor
source venv/bin/activate
pip uninstall -y Flask-SocketIO eventlet
pip install -r requirements.txt
```

**Opcja 2: Ręczna instalacja**
```bash
pip install Flask==3.0.0
pip install Flask-SocketIO==5.3.5
pip install simple-websocket==1.0.0
pip install python-socketio==5.10.0
```

**Opcja 3: Użyj eventlet (jeśli preferujesz)**
```bash
pip install eventlet==0.33.3
```

Następnie w `app.py` zmień:
```python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
```

### Sprawdzenie
```bash
python3 -c "import flask_socketio; print(flask_socketio.__version__)"
```

---

## 📡 Brak danych GPS

### Problem
Aplikacja działa, ale nie ma danych GPS (wszystkie wartości = 0).

### Diagnostyka

**1. Sprawdź czy moduł wysyła dane:**
```bash
sudo cat /dev/ttyAMA0
```

Powinieneś zobaczyć strumień zdań NMEA:
```
$GNGGA,123519,5223.123,N,02101.234,E,1,08,0.9,545.4,M,46.9,M,,*47
$GNRMC,123519,A,5223.123,N,02101.234,E,022.4,084.4,230318,003.1,W*6A
...
```

Jeśli nie ma danych:
- ✅ Sprawdź fizyczne połączenie HAT z GPIO
- ✅ Sprawdź czy antena jest podłączona
- ✅ Umieść antenę z widokiem na niebo (okno, dach)
- ✅ Czekaj 2-5 minut na cold start GPS

**2. Sprawdź konfigurację UART:**
```bash
grep "enable_uart" /boot/firmware/config.txt
# lub
grep "enable_uart" /boot/config.txt
```

Powinno być:
```
enable_uart=1
```

**3. Sprawdź czy konsola szeregowa jest wyłączona:**
```bash
sudo systemctl status serial-getty@ttyAMA0.service
```

Powinno być: `disabled` i `inactive`

Jeśli aktywna:
```bash
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
sudo reboot
```

**4. Sprawdź uprawnienia do portu:**
```bash
ls -l /dev/ttyAMA0
```

Dodaj użytkownika do grupy `dialout`:
```bash
sudo usermod -a -G dialout $USER
```

Wyloguj się i zaloguj ponownie (lub `reboot`).

---

## 🔌 Port szeregowy zajęty / Permission denied

### Problem
```
PermissionError: [Errno 13] Permission denied: '/dev/ttyAMA0'
```
lub
```
serial.serialutil.SerialException: [Errno 16] Device or resource busy
```

### Rozwiązanie

**1. Wyłącz konsolę szeregową:**
```bash
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
```

**2. Sprawdź czy inny proces używa portu:**
```bash
sudo lsof /dev/ttyAMA0
```

Zabij proces jeśli potrzeba:
```bash
sudo kill -9 <PID>
```

**3. Dodaj użytkownika do grupy dialout:**
```bash
sudo usermod -a -G dialout pi
```

Wyloguj się i zaloguj ponownie.

**4. Sprawdź który port jest dostępny:**
```bash
ls -l /dev/tty* | grep -E "(AMA|S0|serial)"
```

Możliwe porty:
- `/dev/ttyAMA0` (najczęściej)
- `/dev/ttyS0`
- `/dev/serial0`

Zmień w `app.py`:
```python
gps = GPSReader(port='/dev/ttyS0', baudrate=115200)
```

---

## 🌐 Brak połączenia ze smartfona

### Problem
Nie można otworzyć aplikacji z przeglądarki na smartfonie.

### Rozwiązanie

**1. Sprawdź IP Raspberry Pi:**
```bash
hostname -I
```

Przykład: `192.168.1.100`

**2. Sprawdź czy serwer działa:**
```bash
ps aux | grep python
sudo netstat -tlnp | grep 5000
```

Powinno być:
```
tcp  0  0  0.0.0.0:5000  0.0.0.0:*  LISTEN  1234/python3
```

**3. Sprawdź czy smartfon jest w tej samej sieci WiFi**

**4. Testuj z Raspberry Pi:**
```bash
curl http://localhost:5000
```

Powinno zwrócić HTML.

**5. Sprawdź firewall (jeśli włączony):**
```bash
sudo ufw status
```

Jeśli aktywny:
```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

**6. Sprawdź czy router blokuje komunikację (AP isolation)**

Niektóre routery mają włączoną izolację klientów WiFi. Wyłącz ją w ustawieniach routera lub podłącz RPi kablem ethernet.

---

## 🛰️ Brak RTK Fixed

### Problem
Aplikacja działa, GPS ma fix, ale nie przechodzi do RTK Fixed.

### Diagnostyka

**1. Sprawdź czy NTRIP Client działa:**
```bash
ps aux | grep ntrip
```

Jeśli nie:
```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 ntrip_client.py
```

**2. Sprawdź logi NTRIP Client:**

Powinieneś zobaczyć:
```
✓ Połączono z serwerem NTRIP
✓ Połączono z GPS na /dev/ttyAMA0
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
```

Jeśli błąd autoryzacji:
- Sprawdź login/hasło ASG-EUPOS
- Sprawdź czy konto jest aktywne
- Sprawdź czy mountpoint jest prawidłowy

**3. Sprawdź mountpoint (stacja referencyjna):**

Wybierz najbliższą stację (50km max):
- WARZ - Warszawa
- KRAK - Kraków
- POZN - Poznań
- WROC - Wrocław
- GDNS - Gdańsk

Zmień w `ntrip_client.py`:
```python
'mountpoint': 'WARZ',  # twoja najbliższa
```

**4. Sprawdź warunki:**
- ✅ Min. 8-10 satelitów widocznych
- ✅ HDOP < 2.0
- ✅ Czysty widok na niebo (bez drzew, budynków)
- ✅ Antena na zewnątrz lub przy oknie

**5. Czekaj na konwergencję:**

Postęp RTK:
```
No Fix (0s) → GPS Fix (30s) → RTK Float (1-2 min) → RTK Fixed (2-5 min)
```

Jeśli po 10 minutach nadal RTK Float:
- Przenieś antenę w lepsze miejsce
- Sprawdź czy korekcje napływają (`wiek korekcji < 5s`)
- Zrestartuj moduł GPS (wyłącz/włącz zasilanie)

**6. Sprawdź wiek korekcji RTK:**

W aplikacji sprawdź "Wiek korekcji":
- < 5s - Doskonale ✅
- 5-15s - Dobrze
- \> 15s - Problem z NTRIP

Jeśli wiek > 15s:
```bash
# Sprawdź połączenie internetowe
ping www.asgeupos.pl

# Restart NTRIP Client
pkill -f ntrip_client
python3 ntrip_client.py
```

---

## 💾 Problemy z instalacją

### Problem: pip install fails

```bash
# Aktualizuj pip
python3 -m pip install --upgrade pip

# Zainstaluj build tools
sudo apt install -y python3-dev build-essential

# Reinstaluj
pip install -r requirements.txt
```

### Problem: brak venv

```bash
sudo apt install -y python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Problem: brak git

```bash
sudo apt install -y git
```

---

## 🖥️ Aplikacja się crashuje

### Problem
Aplikacja kończy się błędem po uruchomieniu.

### Diagnostyka

**1. Sprawdź logi:**
```bash
python3 app.py 2>&1 | tee app.log
```

**2. Sprawdź import errors:**
```bash
python3 -c "import flask; import flask_socketio; import serial; import pynmea2"
```

Jeśli błąd:
```bash
pip install flask flask-socketio pyserial pynmea2
```

**3. Test GPS Reader osobno:**
```bash
python3 -c "from gps_reader import GPSReader; gps = GPSReader(); gps.start()"
```

**4. Sprawdź pamięć:**
```bash
free -h
```

Jeśli mało RAM (< 100MB):
```bash
sudo systemctl stop niektóre-usługi
```

---

## 🔄 Restart po zmianach

Po każdej zmianie w konfiguracji:

**UART / config.txt:**
```bash
sudo reboot
```

**Python code:**
```bash
# Zatrzymaj (CTRL+C)
# Uruchom ponownie
python3 app.py
```

**NTRIP config:**
```bash
pkill -f ntrip_client
python3 ntrip_client.py
```

---

## 📊 Monitoring wydajności

### Sprawdź zasoby:
```bash
# CPU i RAM
htop

# Temperatura
vcgencmd measure_temp

# Procesy Python
ps aux | grep python
```

### Logi systemowe:
```bash
# Jeśli używasz systemd
journalctl -u rtk-monitor -f

# Ogólne logi
dmesg | grep -i uart
dmesg | grep -i serial
```

---

## 🆘 Nadal nie działa?

1. **Spróbuj trybu demo:**
   ```bash
   python3 app_demo.py
   ```
   
   Jeśli demo działa = problem z GPS hardware  
   Jeśli demo nie działa = problem z konfiguracją Python/Flask

2. **Sprawdź wersje:**
   ```bash
   python3 --version  # min 3.7
   pip list | grep -E "(Flask|serial|pynmea2)"
   ```

3. **Reinstaluj od zera:**
   ```bash
   cd ~
   rm -rf rtk_monitor
   # Skopiuj folder ponownie
   cd rtk_monitor
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 app.py
   ```

4. **Kontakt:**
   - Sprawdź dokumentację Waveshare
   - Forum Raspberry Pi
   - GitHub Issues (jeśli projekt jest na GitHub)

---

## ✅ Checklist weryfikacji

Przed zgłoszeniem problemu, sprawdź:

- [ ] UART włączony w config.txt (`enable_uart=1`)
- [ ] Konsola szeregowa wyłączona
- [ ] Moduł HAT poprawnie zamontowany na GPIO
- [ ] Antena podłączona i z widokiem na niebo
- [ ] Dane NMEA widoczne (`sudo cat /dev/ttyAMA0`)
- [ ] Użytkownik w grupie `dialout`
- [ ] Wszystkie zależności zainstalowane (`pip list`)
- [ ] Serwer działa (`ps aux | grep python`)
- [ ] Port 5000 otwarty (`netstat -tlnp | grep 5000`)
- [ ] Smartfon w tej samej sieci WiFi
- [ ] Brak błędów w logach aplikacji

---

**Powodzenia! 🚀**
