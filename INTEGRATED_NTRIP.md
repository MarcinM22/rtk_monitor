# 🎉 ZINTEGROWANY NTRIP - Jedna aplikacja, jedno połączenie!

## ✅ Co zostało naprawione?

### Poprzedni problem:
```
app.py           ← czyta /dev/ttyS0
ntrip_client.py  ← pisze /dev/ttyS0
      ↓
  KONFLIKT! ❌
```

### Nowe rozwiązanie:
```
app.py {
  ├─ GPS Reader     ← czyta NMEA
  └─ NTRIP Client   ← pisze RTCM
         ↓
  JEDNO POŁĄCZENIE! ✅
}
```

**Oba używają tego samego obiektu `serial` - BEZ KONFLIKTU!**

---

## 🚀 Jak używać - DWA SPOSOBY:

### **Sposób 1: Wszystko w jednym (ZALECANE)**

Edytuj `app.py` i skonfiguruj NTRIP wewnątrz:

```bash
nano app.py
```

Znajdź sekcję `NTRIP_CONFIG` (około linia 96) i ustaw:

```python
NTRIP_CONFIG = {
    'enabled': True,  # ← ZMIEŃ na True
    'host': 'system.asgeupos.pl',
    'port': 8086,
    'mountpoint': 'RTK4G_MULTI_RTCM32',
    'username': 'twoj_email@example.com',  # ← TWÓJ LOGIN
    'password': 'twoje_haslo',              # ← TWOJE HASŁO
    'lat': 49.8167,  # ← Twoja pozycja
    'lon': 18.7236,
    'debug': False  # True = pokaż szczegóły NTRIP
}
```

**Zapisz (CTRL+O, Enter, CTRL+X) i uruchom:**

```bash
python3 app.py
```

**To wszystko! Jedna komenda!** 🎉

Zobaczysz:
```
✓ GPS Reader uruchomiony pomyślnie
============================================================
🛰️  Uruchamianie NTRIP Client (RTK)...
============================================================
✓ Połączono z serwerem NTRIP
✓ Autoryzacja udana
✓ Używam współdzielonego połączenia GPS (integrated mode)
✓ NTRIP Client uruchomiony
💡 GPS będzie odbierał korekcje RTK
💡 Oczekuj RTK Fixed w ciągu 2-5 minut
```

---

### **Sposób 2: Osobny NTRIP Client (starszy sposób)**

Nadal możesz używać `ntrip_client.py` osobno:

**Terminal 1:**
```bash
python3 app.py
```

**Terminal 2:**
```bash
python3 ntrip_client.py
```

**UWAGA:** Ten sposób może mieć konflikty portu! Używaj tylko jeśli Sposób 1 nie działa.

---

## 🎯 Zalety zintegrowanego rozwiązania:

### ✅ **Brak konfliktu portu**
- Jedno połączenie szeregowe
- GPS Reader i NTRIP współdzielą ten sam `serial` object
- Żadnych błędów "Device busy"

### ✅ **Prostsze uruchamianie**
- Jedna komenda: `python3 app.py`
- Nie trzeba pamiętać o dwóch terminalach
- Autostart łatwiejszy do skonfigurowania

### ✅ **Synchronizacja**
- NTRIP startuje **po** GPS Reader
- Automatycznie używa tego samego portu
- Nie ma wyścigu (race condition)

---

## 📊 Co zobaczysz w aplikacji:

### Gdy NTRIP działa poprawnie:

1. **"Wiek korekcji RTK"** zacznie się **zmieniać**:
   ```
   Wiek korekcji: 1.2 s
   Wiek korekcji: 2.3 s
   Wiek korekcji: 1.5 s
   ```

2. **Fix Type** przejdzie przez etapy:
   ```
   3D Fix
     ↓ (~1-2 minuty)
   RTK Float
     ↓ (~2-5 minut)
   RTK Fixed  🎉
   ```

3. **HDOP** spadnie poniżej **1.0**

---

## 🔧 Konfiguracja szczegółowa

### Parametry NTRIP_CONFIG:

| Parametr | Opis | Wartość |
|----------|------|---------|
| `enabled` | Włącz/wyłącz RTK | `True` lub `False` |
| `host` | Serwer ASG-EUPOS | `system.asgeupos.pl` |
| `port` | Port NTRIP | `8086` (GPS+GLO+GAL+BDS) |
| `mountpoint` | Wybór stacji | `RTK4G_MULTI_RTCM32` (auto) |
| `username` | Login ASG-EUPOS | Twój email |
| `password` | Hasło ASG-EUPOS | Twoje hasło |
| `lat` | Szerokość geograficzna | Twoja pozycja |
| `lon` | Długość geograficzna | Twoja pozycja |
| `debug` | Debug output | `True` lub `False` |

### Mountpoint - wybór formatu:

**Automatyczny (zalecany):**
```python
'port': 8086,
'mountpoint': 'RTK4G_MULTI_RTCM32',
```
- Auto-wybór najbliższej stacji
- RTCM 3.4 (GPS+GLO+GAL+BDS)

**Ręczny (jeśli problemy):**
```python
'port': 8082,
'mountpoint': 'NAWGEO_POJ_3_1',
```
- Auto-wybór najbliższej stacji
- RTCM 3.1 (GPS+GLO) - starszy format

---

## 🆘 Rozwiązywanie problemów

### Problem: "Wiek korekcji" = "-"

**Przyczyna:** NTRIP nie działa lub GPS nie odbiera

**Sprawdź:**
1. Czy `enabled: True` w CONFIG?
2. Czy login/hasło są poprawne?
3. Uruchom z `debug: True` aby zobaczyć szczegóły

### Problem: NTRIP nie startuje

**Logi pokażą przyczynę:**
```
✗ Nie można uruchomić NTRIP Client
⚠️  Aplikacja działa bez RTK (tylko GPS)
```

**Rozwiązanie:**
- Sprawdź login/hasło
- Sprawdź połączenie internetowe: `ping system.asgeupos.pl`
- Włącz `debug: True` aby zobaczyć więcej

### Problem: Konflikt portu (nadal!)

**Jeśli używasz Sposób 2 (dwa terminale):**
- Zatrzymaj `ntrip_client.py`
- Użyj **tylko** `app.py` ze zintegrowanym NTRIP

---

## 🎯 Test czy działa

### 1. Sprawdź logi app.py:
```
✓ NTRIP Client uruchomiony
💡 GPS będzie odbierał korekcje RTK
```

### 2. Sprawdź w przeglądarce:
- **Wiek korekcji** powinien się **zmieniać** (nie być "-")
- **Fix Type** powinien przejść do **RTK Float** w 1-2 min

### 3. Sprawdź logi NTRIP (jeśli debug: True):
```
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
📥 Odebrano korekt: 20.5 KB
```

---

## 🚀 Autostart (systemd)

Teraz łatwiejszy - **tylko jeden service**:

```bash
sudo nano /etc/systemd/system/rtk-monitor.service
```

```ini
[Unit]
Description=RTK Monitor with NTRIP
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

```bash
sudo systemctl enable rtk-monitor
sudo systemctl start rtk-monitor
```

**Gotowe!** Wszystko w jednym.

---

## 📖 Podsumowanie

**Stary sposób:**
```
Terminal 1: python3 app.py
Terminal 2: python3 ntrip_client.py
```
❌ Konflikt portu  
❌ Dwa procesy do zarządzania

**Nowy sposób:**
```
python3 app.py
```
✅ Jedno połączenie  
✅ Jeden proces  
✅ Brak konfliktu  
✅ Wszystko działa!

---

**Skonfiguruj NTRIP_CONFIG w app.py i uruchom. Powodzenia z RTK Fixed!** 🎯
