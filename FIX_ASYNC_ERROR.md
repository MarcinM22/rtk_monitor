# 🔧 Szybkie poprawki - RTK Monitor

## Problem 1: "invalid async_mode specified"
Po uruchomieniu `python3 app.py` widzisz:
```
ValueError: invalid async_mode specified
```

## Szybka poprawka (2 minuty)

### Metoda 1: Reinstalacja zależności (najłatwiejsza)

```bash
cd ~/rtk_monitor
source venv/bin/activate

# Usuń problematyczne pakiety
pip uninstall -y Flask-SocketIO eventlet python-socketio

# Zainstaluj ponownie
pip install Flask-SocketIO==5.3.5
pip install python-socketio==5.10.0
pip install simple-websocket==1.0.0

# Uruchom aplikację
python3 app.py
```

### Metoda 2: Edycja kodu (jeśli Metoda 1 nie działa)

**Otwórz plik `app.py`:**
```bash
nano app.py
```

**Znajdź linię (około linia 11):**
```python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
```

**Zmień na:**
```python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
```

**Zapisz (CTRL+O, Enter, CTRL+X)**

**Zrób to samo dla `app_demo.py`:**
```bash
nano app_demo.py
```

### Metoda 3: Użyj eventlet (alternatywa)

```bash
pip install eventlet==0.33.3
python3 app.py
```

Jeśli to nie pomoże, użyj Metody 2.

## Sprawdzenie czy działa

```bash
python3 app.py
```

Powinieneś zobaczyć:
```
====================================================================
RTK Monitor - Aplikacja GPS/RTK dla Raspberry Pi
====================================================================

✓ Połączono z /dev/ttyAMA0 @ 115200 baud
✓ GPS Reader uruchomiony pomyślnie
...
```

Bez błędów! ✅

## Jeśli nadal nie działa

Usuń całe środowisko wirtualne i zainstaluj od nowa:

```bash
cd ~/rtk_monitor
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

## Nowa wersja requirements.txt

Jeśli używasz starej wersji, zastąp zawartość `requirements.txt`:

```
Flask==3.0.0
Flask-SocketIO==5.3.5
pyserial==3.5
pynmea2==1.19.0
python-socketio==5.10.0
simple-websocket==1.0.0
```

Następnie:
```bash
pip install -r requirements.txt
```

---

**Problem rozwiązany? Świetnie! Wróć do [README.md](README.md) 🚀**

---

## Problem 2: "[Errno 2] No such file or directory: '/dev/ttyAMA0'"

Po uruchomieniu widzisz:
```
✗ Błąd połączenia z /dev/ttyAMA0: [Errno 2] could not open port /dev/ttyAMA0
✗ Nie można uruchomić GPS Reader
```

### Krok 1: Sprawdź jakie porty są dostępne

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 find_uart.py
```

Ten skrypt pokaże wszystkie dostępne porty UART.

### Krok 2a: Jeśli znaleziono porty (np. /dev/ttyS0)

Zaktualizowana wersja `app.py` automatycznie wykrywa porty, więc po prostu uruchom ponownie:

```bash
python3 app.py
```

### Krok 2b: Jeśli NIE znaleziono żadnych portów

**Włącz UART w konfiguracji Raspberry Pi:**

```bash
# Sprawdź czy UART jest włączony
grep "enable_uart" /boot/firmware/config.txt
```

Jeśli nic nie zwraca lub jest `enable_uart=0`:

```bash
# Edytuj config
sudo nano /boot/firmware/config.txt
```

**Na Raspberry Pi OS Bookworm (nowsze):**
Plik: `/boot/firmware/config.txt`

**Na Raspberry Pi OS Bullseye (starsze):**
Plik: `/boot/config.txt`

**Dodaj na końcu pliku:**
```
enable_uart=1
dtoverlay=disable-bt
```

**Zapisz i wyjdź:**
- CTRL+O (zapisz)
- Enter
- CTRL+X (wyjdź)

**Restart:**
```bash
sudo reboot
```

### Krok 3: Po restarcie sprawdź ponownie

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 find_uart.py
```

Teraz powinny pojawić się porty (np. `/dev/ttyAMA0` lub `/dev/ttyS0`).

### Krok 4: Wyłącz konsolę szeregową

```bash
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
```

Lub dla `/dev/ttyS0`:
```bash
sudo systemctl stop serial-getty@ttyS0.service
sudo systemctl disable serial-getty@ttyS0.service
```

### Krok 5: Dodaj użytkownika do grupy dialout

```bash
sudo usermod -a -G dialout $USER
```

Wyloguj się i zaloguj ponownie (lub `sudo reboot`).

### Krok 6: Uruchom aplikację

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 app.py
```

Powinno działać! ✅

### Ręczna zmiana portu (jeśli auto-detect nie działa)

Jeśli `find_uart.py` pokazuje np. `/dev/ttyS0`, ale app.py go nie wykrywa:

**Edytuj `app.py`:**
```bash
nano app.py
```

**Znajdź funkcję `find_uart_port()` i dodaj swój port na początku listy:**
```python
def find_uart_port():
    possible_ports = [
        '/dev/ttyS0',      # ← dodaj tutaj swój port
        '/dev/ttyAMA0',
        '/dev/serial0',
        ...
    ]
```

Lub zmień bezpośrednio w sekcji `if __name__ == '__main__':`:
```python
# Zamiast: uart_port = find_uart_port()
# Użyj:
uart_port = '/dev/ttyS0'  # twój port z find_uart.py
```

### Test portu

Sprawdź czy moduł GPS wysyła dane:
```bash
sudo cat /dev/ttyS0
# lub
sudo cat /dev/ttyAMA0
```

Powinieneś zobaczyć strumień tekstu zaczynający się od `$GNGGA`, `$GNRMC`, itp.

Jeśli tak - port działa! ✅  
Jeśli nie - sprawdź fizyczne połączenie HAT z GPIO.

---

**Więcej problemów?** Zobacz [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
