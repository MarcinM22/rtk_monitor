# ⚡ Szybka Instalacja - RTK Monitor

## 1. Skopiuj archiwum na Raspberry Pi

```bash
# Jeśli masz archiwum na komputerze:
scp rtk_monitor.tar.gz pi@IP_RASPBERRY:~

# Lub skopiuj przez pendrive/kartę SD
```

## 2. Rozpakuj archiwum

```bash
cd ~
tar -xzf rtk_monitor.tar.gz
cd rtk_monitor
```

**WAŻNE:** Użyj `tar -xzf` - to zachowa strukturę katalogów!

## 3. Sprawdź strukturę

```bash
ls -la
```

Powinieneś zobaczyć:
```
drwxr-xr-x templates/     ← musi być
drwxr-xr-x static/        ← musi być
-rw-r--r-- app.py
-rw-r--r-- gps_reader.py
...
```

Sprawdź zawartość:
```bash
ls templates/   # index.html
ls static/      # script.js, style.css
```

## 4. Uruchom instalator

```bash
chmod +x install.sh
./install.sh
```

Po restarcie (jeśli wymagany):

```bash
cd ~/rtk_monitor
source venv/bin/activate
```

## 5. Sprawdź porty UART (jeśli masz problemy)

```bash
python3 find_uart.py
```

## 6. Uruchom aplikację

```bash
python3 app.py
```

Powinieneś zobaczyć:
```
✓ Wykryto port UART: /dev/ttyXXX
✓ GPS Reader uruchomiony pomyślnie
🌐 Aplikacja dostępna pod adresem:
   http://192.168.X.X:5000
```

## 7. Otwórz w przeglądarce na smartfonie

```
http://IP_RASPBERRY:5000
```

---

## 🆘 Problemy?

**Brak portu UART:** Zobacz [FIX_NO_UART.md](FIX_NO_UART.md)

**Inne problemy:** Zobacz [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## ✅ To wszystko!

Aplikacja powinna działać. Jeśli widzisz dane GPS - super! 

Jeśli chcesz RTK Fixed (dokładność centymetrowa), skonfiguruj ASG-EUPOS według instrukcji w [README.md](README.md).

**Miłego pomiarowania! 📡**
