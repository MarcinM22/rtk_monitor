# 🚀 RTK Monitor - Szybki Start

## 1️⃣ Podłącz hardware
- Nałóż LC29H HAT na GPIO Raspberry Pi
- Podłącz antenę GPS
- Umieść antenę z widokiem na niebo

## 2️⃣ Skopiuj folder na RPi
```bash
# Przykład przez SCP
scp -r rtk_monitor/ pi@192.168.1.XXX:~
```

Lub wgraj przez pendrive / kartę SD.

## 3️⃣ Uruchom instalator
```bash
cd ~/rtk_monitor
chmod +x install.sh
./install.sh
```

Restart jeśli wymagany: `sudo reboot`

## 4️⃣ Uruchom aplikację
```bash
cd ~/rtk_monitor
source venv/bin/activate

# Sprawdź dostępne porty (opcjonalnie)
python3 find_uart.py

# Uruchom aplikację
python3 app.py
```

**Jeśli błąd "No such file /dev/ttyAMA0":**
Zobacz [FIX_ASYNC_ERROR.md](FIX_ASYNC_ERROR.md) - Problem 2

## 5️⃣ Otwórz na smartfonie
1. Sprawdź IP: `hostname -I`
2. Wpisz w przeglądarce: `http://IP_RASPBERRY:5000`

**Gotowe!** 🎉

---

## 🌐 RTK Fix (opcjonalnie)

Chcesz dokładność centymetrową? Skonfiguruj ASG-EUPOS:

1. **Zarejestruj się:** http://www.asgeupos.pl
2. **Edytuj** `ntrip_client.py`:
   ```python
   CONFIG = {
       'username': 'TWOJ_LOGIN',
       'password': 'TWOJE_HASLO',
       'mountpoint': 'WARZ',  # najbliższa stacja
   }
   ```
3. **Uruchom** w nowym terminalu:
   ```bash
   python3 ntrip_client.py
   ```
4. **Czekaj** 2-5 minut na RTK Fixed

---

## 🆘 Nie działa?

### GPS nie odpowiada
```bash
# Test portu
sudo cat /dev/ttyAMA0
# powinny pojawić się zdania $GNGGA, $GNRMC, etc.
```

### Brak połączenia ze smartfona
```bash
# Sprawdź IP
hostname -I

# Sprawdź czy serwer działa
ps aux | grep python
```

### Port zajęty
```bash
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
```

---

📖 **Pełna dokumentacja:** README.md
