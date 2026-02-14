# 🚨 BŁĄD: SOURCETABLE 200 OK

## Co się stało?

Serwer NTRIP zwrócił **SOURCETABLE** (listę dostępnych mountpointów) zamiast strumienia korekt RTK.

```
✗ Błąd serwera NTRIP: SOURCETABLE 200 OK
STR;BART_RTCM_3_2;BART_RTCM_3_2;...
STR;BIAL_RTCM_3_2;BIAL_RTCM_3_2;...
...
```

### Przyczyna:

**Brak loginu i hasła** lub są one nieprawidłowe!

Gdy połączysz się z serwerem NTRIP bez autoryzacji (lub z błędnymi danymi), serwer zwraca listę dostępnych stacji zamiast danych RTK.

---

## ✅ ROZWIĄZANIE (3 minuty)

### Krok 1: Sprawdź czy masz konto ASG-EUPOS

**Nie masz konta?**
- Wejdź na: http://www.asgeupos.pl
- Kliknij "Rejestracja"
- Wypełnij formularz
- Czekaj na aktywację (1-3 dni)

**Masz konto?**
- Sprawdź login (adres email)
- Sprawdź hasło

### Krok 2: Edytuj ntrip_client.py

```bash
cd ~/rtk_monitor
nano ntrip_client.py
```

### Krok 3: Znajdź sekcję CONFIG i uzupełnij:

**Stare (niepoprawne):**
```python
CONFIG = {
    'username': 'TWOJ_LOGIN',    # ← TO NIE ZADZIAŁA!
    'password': 'TWOJE_HASLO',   # ← TO NIE ZADZIAŁA!
}
```

**Nowe (poprawne):**
```python
CONFIG = {
    'username': 'jan.kowalski@gmail.com',  # ← Twój email z ASG-EUPOS
    'password': 'MojeHaslo123',            # ← Twoje prawdziwe hasło
    'mountpoint': 'ZYWI',                  # ← Najbliższa stacja
    'lat': 49.82,                          # ← Twoja lokalizacja
    'lon': 18.72,
}
```

**WAŻNE:** 
- Login = adres email użyty przy rejestracji
- Hasło = hasło które ustawiłeś podczas rejestracji
- NIE zostawiaj `'TWOJ_LOGIN'` ani `'TWOJE_HASLO'` - to przykładowe wartości!

### Krok 4: Zapisz i uruchom ponownie

```bash
# Zapisz plik
CTRL+O → Enter → CTRL+X

# Uruchom NTRIP Client
python3 ntrip_client.py
```

### ✅ Teraz powinno działać:

```
🔌 Łączenie z www.asgeupos.pl:2101...
✓ Połączono z serwerem NTRIP
✓ Połączono z GPS na /dev/ttyS0
✓ NTRIP Client uruchomiony
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
```

---

## 🔍 Inne możliwe błędy

### 401 Unauthorized

```
✗ Błąd serwera NTRIP: 401 Unauthorized
```

**Przyczyna:** Nieprawidłowy login lub hasło

**Rozwiązanie:**
- Sprawdź czy login i hasło są poprawne
- Sprawdź czy konto jest aktywne
- Zaloguj się na www.asgeupos.pl aby sprawdzić

### 404 Not Found

```
✗ Błąd serwera NTRIP: 404 Not Found
```

**Przyczyna:** Nieprawidłowy mountpoint

**Rozwiązanie:**
- Sprawdź nazwę mountpoint
- Lista dostępnych: http://www.asgeupos.pl/index.php?wpg_type=stacje
- Przykłady: `WARZ`, `KRAK`, `ZYWI`, `POZN`

### Connection refused

```
✗ Błąd połączenia: Connection refused
```

**Przyczyna:** Brak internetu lub zablokowany port

**Rozwiązanie:**
```bash
# Sprawdź internet
ping www.asgeupos.pl

# Sprawdź port 2101
telnet www.asgeupos.pl 2101
```

---

## 📖 Pełna instrukcja

Szczegółowy przewodnik konfiguracji ASG-EUPOS:
**[CONFIGURE_ASGEUPOS.md](CONFIGURE_ASGEUPOS.md)**

Zawiera:
- Jak się zarejestrować
- Lista wszystkich mountpointów w Polsce
- Jak wybrać najbliższą stację
- Rozwiązywanie problemów

---

## 🎯 Szybka weryfikacja konfiguracji

```bash
cd ~/rtk_monitor
nano ntrip_client.py
```

Sprawdź czy masz:
```python
'username': 'twoj_prawdziwy_email@example.com',  # nie 'TWOJ_LOGIN'
'password': 'twoje_prawdziwe_haslo',             # nie 'TWOJE_HASLO'
'mountpoint': 'ZYWI',                            # poprawna nazwa stacji
```

Jeśli wszystko OK - zapisz i uruchom!

---

**Gotowe? Teraz uruchom NTRIP Client i ciesz się RTK Fixed! 🎉**
