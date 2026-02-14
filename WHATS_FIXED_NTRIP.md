# 🔧 Naprawiony plik ntrip_client.py

## ✅ Co zostało zmienione?

### 1. Poprawny serwer i port
**Stare (NIE DZIAŁAŁO):**
```python
'host': 'www.asgeupos.pl',
'port': 2101,
```

**Nowe (DZIAŁA):**
```python
'host': 'system.asgeupos.pl',
'port': 8086,
```

### 2. Automatyczny wybór najbliższej stacji
**Stare (ręczny wybór):**
```python
'mountpoint': 'ZYWI',  # trzeba było ręcznie wybierać
```

**Nowe (automatyczny):**
```python
'mountpoint': 'RTK4G_MULTI_RTCM32',  # auto-wybór!
```

### 3. Wysyłanie pozycji GGA
Dodano generowanie i wysyłanie zdania GGA w żądaniu NTRIP - **WYMAGANE** dla `RTK4G_MULTI_RTCM32`.

### 4. Debug - wyświetlanie danych logowania
Teraz przy próbie połączenia zobaczysz:
```
============================================================
🔌 Łączenie z system.asgeupos.pl:8086...
============================================================
📍 Mountpoint: RTK4G_MULTI_RTCM32
👤 Username: twoj@email.pl
🔑 Password: ********* (9 znaków)
📍 Pozycja: 49.8167°N, 18.7236°E
============================================================

📤 Wysyłane żądanie HTTP:
------------------------------------------------------------
GET /RTK4G_MULTI_RTCM32 HTTP/1.1
Host: system.asgeupos.pl
Ntrip-Version: Ntrip/2.0
User-Agent: NTRIP RTKMonitor/1.0
Authorization: Basic dHdvakBl...Q0OQ==
Ntrip-GGA: $GPGGA,000000.00,4949.0020,N,01843.4160,E,1,08,1.0,100.0,M,0.0,M,,*67
Connection: close
------------------------------------------------------------

📥 Odpowiedź serwera:
------------------------------------------------------------
HTTP/1.0 200 OK
Server: NTRIP Trimble Ntrip Caster 5.2
...
------------------------------------------------------------
```

### 5. Lepsze komunikaty błędów
- `SOURCETABLE 200 OK` → jasne wyjaśnienie co jest źle
- `401 Unauthorized` → błędny login/hasło
- `404 Not Found` → błędny mountpoint

---

## 🚀 Jak używać?

### 1. Edytuj ntrip_client.py:
```bash
nano ntrip_client.py
```

### 2. W sekcji CONFIG uzupełnij TYLKO:
```python
'username': 'twoj_prawdziwy_email@gmail.com',  # ← twój login
'password': 'twoje_prawdziwe_haslo',           # ← twoje hasło
'lat': 49.82,  # ← twoja szerokość (przybliżona)
'lon': 18.72,  # ← twoja długość (przybliżona)
```

**Pozostałe wartości NIE ZMIENIAJ** - są już poprawne!

### 3. Zapisz i uruchom:
```bash
python3 ntrip_client.py
```

---

## 🎯 Co zobaczysz jeśli wszystko OK?

```
============================================================
🔌 Łączenie z system.asgeupos.pl:8086...
============================================================
📍 Mountpoint: RTK4G_MULTI_RTCM32
👤 Username: jan.kowalski@gmail.com
🔑 Password: *********** (11 znaków)
📍 Pozycja: 49.8167°N, 18.7236°E
============================================================

[... debug HTTP ...]

✓ Połączono z serwerem NTRIP
✓ Autoryzacja udana
✓ Wybrano mountpoint: RTK4G_MULTI_RTCM32
✓ Połączono z GPS na /dev/ttyS0
✓ NTRIP Client uruchomiony
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
📥 Odebrano korekt: 20.5 KB
```

---

## ❌ Najczęstsze błędy

### "SOURCETABLE 200 OK"
**Przyczyna:** Nieprawidłowy login lub hasło  
**Rozwiązanie:** Sprawdź username i password (zobacz debug output powyżej)

### "401 Unauthorized"
**Przyczyna:** Błędny login lub hasło  
**Rozwiązanie:** Sprawdź czy konto jest aktywne na www.asgeupos.pl

### "404 Not Found"
**Przyczyna:** Błędny mountpoint (NIE POWINNO SIĘ ZDARZYĆ jeśli używasz RTK4G_MULTI_RTCM32)  
**Rozwiązanie:** Sprawdź czy nie zmieniłeś mountpoint

---

## 🔍 Weryfikacja przed uruchomieniem

Sprawdź w pliku czy masz:
```python
CONFIG = {
    'host': 'system.asgeupos.pl',       # ✓ poprawne
    'port': 8086,                        # ✓ poprawne
    'mountpoint': 'RTK4G_MULTI_RTCM32',  # ✓ poprawne
    'username': 'twoj@email.pl',         # ← ZMIEŃ!
    'password': 'twoje_haslo',           # ← ZMIEŃ!
    'lat': 49.8167,                      # ← ZMIEŃ na swoją
    'lon': 18.7236,                      # ← ZMIEŃ na swoją
    'debug': True                        # ✓ zostaw True
}
```

---

**Gotowe! Uruchom i sprawdź debug output - tam będzie widać dokładnie co jest wysyłane do serwera.** 🚀
