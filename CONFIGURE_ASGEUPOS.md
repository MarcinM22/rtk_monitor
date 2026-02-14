# 🛰️ Konfiguracja ASG-EUPOS dla RTK

## Co to jest ASG-EUPOS?

ASG-EUPOS to sieć stacji referencyjnych GNSS w Polsce, która zapewnia **bezpłatne** korekcje RTK. Dzięki nim możesz uzyskać dokładność pozycjonowania **1-2 cm**!

## 📝 Krok 1: Rejestracja

### Bezpłatne konto

1. Wejdź na: **http://www.asgeupos.pl**
2. Kliknij **"Rejestracja"** lub **"Uzyskaj dostęp"**
3. Wypełnij formularz:
   - Imię i nazwisko
   - Email (będzie to Twój login)
   - Hasło
   - Dane kontaktowe
4. Potwierdź email
5. Czekaj na aktywację konta (zwykle 1-3 dni robocze)

### Po aktywacji otrzymasz:

- **Login**: Twój adres email
- **Hasło**: To co ustawiłeś podczas rejestracji
- Dostęp do wszystkich mountpointów (stacji referencyjnych)

---

## 📍 Krok 2: Wybierz najbliższy mountpoint

Mountpoint = stacja referencyjna RTK. Im bliżej, tym lepsza dokładność.

### 🗺️ Popularne mountpointy w Polsce

**Śląsk:**
- `ZYWI` - Żywiec (49.82°N, 18.72°E)
- `KATO` - Katowice (50.22°N, 18.99°E)
- `BIEL` - Bielsko-Biała (49.82°N, 19.04°E)

**Małopolska:**
- `KRAK` - Kraków (50.06°N, 19.96°E)
- `TARN` - Tarnów (50.01°N, 20.99°E)

**Mazowsze:**
- `WARZ` - Warszawa (52.23°N, 21.04°E)
- `BOGI` - Boguty-Pianki (52.47°N, 21.03°E)

**Pomorze:**
- `GDNS` - Gdańsk (54.35°N, 18.65°E)
- `SLUP` - Słupsk (54.46°N, 17.03°E)

**Wielkopolska:**
- `POZN` - Poznań (52.38°N, 16.90°E)

**Dolny Śląsk:**
- `WROC` - Wrocław (51.11°N, 17.06°E)

**Zachodniopomorskie:**
- `SZCZ` - Szczecin (53.43°N, 14.53°E)

**Pełna lista:** http://www.asgeupos.pl/index.php?wpg_type=stacje

### 💡 Wskazówki:

- Wybierz stację w promieniu **50 km** od Twojej lokalizacji
- Im bliżej, tym szybsza konwergencja do RTK Fixed
- Sprawdź mapę stacji na stronie ASG-EUPOS

---

## ⚙️ Krok 3: Konfiguracja w RTK Monitor

### Edytuj plik `ntrip_client.py`:

```bash
cd ~/rtk_monitor
nano ntrip_client.py
```

### Znajdź sekcję CONFIG i uzupełnij:

```python
CONFIG = {
    'host': 'system.asgeupos.pl',       # Serwer ASG-EUPOS
    'port': 8086,                        # Port dla GPS+GLO+GAL+BDS
    'mountpoint': 'RTK4G_MULTI_RTCM32',  # Auto-wybór najbliższej stacji
    'username': 'twoj@email.pl',         # ← Login z ASG-EUPOS
    'password': 'twoje_haslo',           # ← Hasło z ASG-EUPOS
    'lat': 49.8167,                      # ← Twoja szerokość geograficzna
    'lon': 18.7236,                      # ← Twoja długość geograficzna
}
```

**UWAGA:** Mountpoint `RTK4G_MULTI_RTCM32` automatycznie wybiera najbliższą stację na podstawie Twojej pozycji (lat/lon)! Nie musisz ręcznie wybierać ZYWI, KRAK, WARZ, itp.

### Zapisz zmiany:

- Naciśnij `CTRL+O` (zapisz)
- Naciśnij `Enter` (potwierdź)
- Naciśnij `CTRL+X` (wyjdź)

---

## 🚀 Krok 4: Uruchom NTRIP Client

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 ntrip_client.py
```

### ✅ Poprawne połączenie wygląda tak:

```
🔌 Łączenie z www.asgeupos.pl:2101...
✓ Połączono z serwerem NTRIP
✓ Połączono z GPS na /dev/ttyS0
✓ NTRIP Client uruchomiony
📡 Rozpoczęto odbieranie korekt RTK...
📥 Odebrano korekt: 10.2 KB
📥 Odebrano korekt: 20.5 KB
...
```

### ❌ Błędy i rozwiązania:

**Błąd: "SOURCETABLE 200 OK"**
- **Przyczyna:** Brak loginu/hasła lub są nieprawidłowe
- **Rozwiązanie:** Sprawdź czy `username` i `password` są poprawne

**Błąd: "401 Unauthorized"**
- **Przyczyna:** Nieprawidłowy login lub hasło
- **Rozwiązanie:** Sprawdź dane logowania na www.asgeupos.pl

**Błąd: "404 Not Found"**
- **Przyczyna:** Nieprawidłowy mountpoint
- **Rozwiązanie:** Sprawdź nazwę mountpoint na liście ASG-EUPOS

**Błąd: "Connection refused"**
- **Przyczyna:** Brak internetu lub zablokowany port
- **Rozwiązanie:** Sprawdź połączenie: `ping www.asgeupos.pl`

---

## 📊 Krok 5: Monitoruj RTK w aplikacji

Otwórz aplikację RTK Monitor w przeglądarce:
```
http://IP_RASPBERRY:5000
```

### Postęp RTK:

```
No Fix (start)
    ↓ ~30 sekund
GPS Fix (5-10m dokładność)
    ↓ ~1-2 minuty
RTK Float (10-50cm dokładność)
    ↓ ~2-5 minut
RTK Fixed (1-2cm dokładność) ✨
```

### Co obserwować:

1. **Fix Type** powinien przejść do **RTK Fixed** (zielony)
2. **Wiek korekcji** powinien być **< 5 sekund**
3. **HDOP** powinien być **< 1.0**
4. **Satelity** minimum **10-12**

---

## 🔧 Rozwiązywanie problemów

### RTK Float nie przechodzi do RTK Fixed

**Sprawdź:**
1. Czy NTRIP Client działa (powinien pokazywać "📥 Odebrano korekt")
2. Czy wiek korekcji < 5s (w aplikacji RTK Monitor)
3. Czy masz min. 10 satelitów
4. Czy antena ma czysty widok na niebo

**Spróbuj:**
- Czekaj dłużej (czasem 5-10 minut)
- Przenieś antenę na dach/okno
- Zmień mountpoint na inny (może bliższy)
- Restart GPS: wyłącz NTRIP, wyłącz app.py, włącz ponownie

### Wiek korekcji > 15 sekund

**Przyczyna:** Słabe połączenie internetowe lub problem z serwerem

**Rozwiązanie:**
```bash
# Sprawdź internet
ping www.asgeupos.pl

# Restart NTRIP Client
pkill -f ntrip_client
python3 ntrip_client.py
```

### Brak satelitów

**Przyczyna:** Antena w złym miejscu lub nie działa

**Rozwiązanie:**
- Umieść antenę na zewnątrz z widokiem na niebo
- Sprawdź połączenie anteny z HAT
- Czekaj 2-5 minut na cold start GPS

---

## 📖 Dodatkowe informacje

### Serwery alternatywne ASG-EUPOS:

Jeśli `www.asgeupos.pl` nie działa, spróbuj:
- `rtk.asgeupos.pl:2101`
- `193.59.228.253:2101` (IP backup)

### Format mountpointu:

ASG-EUPOS używa różnych formatów dla różnych odbiorników:
- `STACJA` - RTCM 3.0 (standardowy, dla LC29H)
- `STACJA_RTCM_3_2` - RTCM 3.2 (nowszy)

Dla LC29H HAT używaj standardowej nazwy (np. `ZYWI`, nie `ZYWI_RTCM_3_2`).

### Koszty:

ASG-EUPOS jest **całkowicie darmowy** dla użytkowników w Polsce! 🎉

---

## ✅ Checklist końcowy

Przed uruchomieniem sprawdź:

- [ ] Konto ASG-EUPOS aktywowane
- [ ] Login i hasło sprawdzone
- [ ] Mountpoint wybrany (najbliższy)
- [ ] Współrzędne ustawione (przybliżone)
- [ ] `ntrip_client.py` skonfigurowany
- [ ] Internet działa (`ping www.asgeupos.pl`)
- [ ] NTRIP Client uruchomiony (osobny terminal)
- [ ] App.py działa
- [ ] Antena GPS na zewnątrz z widokiem na niebo

**Jeśli wszystko OK - czekaj na RTK Fixed! Powodzenia! 🎯**

---

**Pytania?** Zobacz [README.md](README.md) lub [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
