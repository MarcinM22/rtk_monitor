# 🚨 ROZWIĄZANIE: Brak portu /dev/ttyAMA0

## Co się stało?
Twój Raspberry Pi nie ma portu `/dev/ttyAMA0` lub nie jest on skonfigurowany.

## ✅ SZYBKIE ROZWIĄZANIE (3 kroki)

### Krok 1: Sprawdź jakie porty są dostępne

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 find_uart.py
```

To pokaże wszystkie dostępne porty UART.

**Możliwe wyniki:**

**A) Jeśli widzisz porty (np. /dev/ttyS0, /dev/serial0):**
```
✓ /dev/ttyS0 - ISTNIEJE
✓ /dev/serial0 - ISTNIEJE
```
→ Przejdź do **Kroku 2A**

**B) Jeśli nie widzisz żadnych portów:**
```
❌ Nie znaleziono żadnych portów UART!
```
→ Przejdź do **Kroku 2B**

---

### Krok 2A: Uruchom aplikację (porty są dostępne)

Zaktualizowana wersja automatycznie wykrywa porty:

```bash
python3 app.py
```

Powinno zadziałać! ✅

---

### Krok 2B: Włącz UART (brak portów)

**1. Sprawdź plik konfiguracyjny:**

Na **Raspberry Pi OS Bookworm** (2023+):
```bash
sudo nano /boot/firmware/config.txt
```

Na **Raspberry Pi OS Bullseye** (2021-2023):
```bash
sudo nano /boot/config.txt
```

**2. Dodaj na końcu pliku:**
```
enable_uart=1
dtoverlay=disable-bt
```

**3. Zapisz i wyjdź:**
- Naciśnij `CTRL+O` (zapisz)
- Naciśnij `Enter` (potwierdź)
- Naciśnij `CTRL+X` (wyjdź)

**4. Restart:**
```bash
sudo reboot
```

**5. Po restarcie sprawdź ponownie:**
```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 find_uart.py
```

Teraz powinny pojawić się porty!

**6. Wyłącz konsolę szeregową:**
```bash
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
```

**7. Dodaj użytkownika do grupy dialout:**
```bash
sudo usermod -a -G dialout marcin
```

**8. Wyloguj się i zaloguj ponownie** lub zrestartuj:
```bash
sudo reboot
```

**9. Uruchom aplikację:**
```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 app.py
```

---

### Krok 3: Test połączenia GPS

Sprawdź czy moduł GPS wysyła dane:

```bash
sudo cat /dev/ttyS0
```
(lub `/dev/ttyAMA0` jeśli taki masz)

**Powinieneś zobaczyć coś takiego:**
```
$GNGGA,123519,5223.1234,N,02101.2345,E,1,08,0.9,545.4,M,46.9,M,,*47
$GNRMC,123519,A,5223.1234,N,02101.2345,E,022.4,084.4,230318,003.1,W*6A
$GNGSA,A,3,01,02,03,04,05,06,07,08,,,,,1.2,0.9,0.8*3C
...
```

**Jeśli widzisz te dane:**
✅ Hardware działa! Problem był tylko z konfiguracją portu.

**Jeśli nie widzisz żadnych danych:**
- Sprawdź fizyczne połączenie HAT z pinami GPIO
- Sprawdź czy antena GPS jest podłączona
- Umieść antenę z widokiem na niebo
- Czekaj 2-5 minut (cold start GPS)

Naciśnij `CTRL+C` aby zatrzymać wyświetlanie.

---

## 🎯 Podsumowanie

Po wykonaniu powyższych kroków:

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 app.py
```

Powinieneś zobaczyć:
```
============================================================
RTK Monitor - Aplikacja GPS/RTK dla Raspberry Pi
============================================================

✓ Wykryto port UART: /dev/ttyS0
✓ Połączono z /dev/ttyS0 @ 115200 baud
✓ GPS Reader uruchomiony pomyślnie

📡 Czekam na dane GPS...

🌐 Aplikacja dostępna pod adresem:
   http://localhost:5000
   http://192.168.X.X:5000
```

**Gotowe!** 🚀

---

## 📞 Nadal nie działa?

1. Sprawdź czy HAT jest poprawnie zamontowany na 40-pin GPIO
2. Sprawdź czy używasz odpowiedniego pliku config.txt:
   - `/boot/firmware/config.txt` (nowsze OS)
   - `/boot/config.txt` (starsze OS)
3. Pełna dokumentacja: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
