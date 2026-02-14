# 🔧 Co zostało naprawione - Debug RTK

## ✅ Naprawione problemy:

### 1. **Błąd Flask-SocketIO (KRYTYCZNY)**
```python
TypeError: Server.emit() got an unexpected keyword argument 'broadcast'
```

**Naprawa:** Usunięto parametr `broadcast` z `socketio.emit()`.

**Efekt:** Aplikacja teraz **normalnie wysyła dane** do przeglądarki bez błędów.

---

### 2. **Debug RTCM - widoczność przesyłanych danych**

Dodano komunikaty w `write_rtcm()`:
```
📤 RTCM → GPS: 87 bajtów [D3 00 55 2C...]
📤 RTCM → GPS: 124 bajtów [D3 00 7A 1F...]
```

**Co pokazuje:**
- Ile bajtów RTCM jest wysyłanych
- Pierwsze 4 bajty w HEX (sygnatura RTCM: `D3 00` + długość)

**Sprawdzenie:** Jeśli widzisz te komunikaty = RTCM dociera do GPS ✅

---

### 3. **Debug GGA - wykrywanie wieku korekcji**

Dodano komunikaty co ~5 sekund:
```
🔍 GGA: qual=2, sats=28, age=PUSTE
```

**Pola:**
- `qual` = fix quality (0=No Fix, 1=GPS, 2=DGPS, 4=RTK Fixed, 5=RTK Float)
- `sats` = liczba satelitów
- `age` = wiek korekcji różnicowych

**Kluczowe:**
- `age=PUSTE` → GPS **NIE MA** korekt RTK ❌
- `age='1.2'` → GPS **MA** korekcje (1.2 sekundy) ✅

---

### 4. **Wykrywanie chunked encoding**

Dodano ostrzeżenie:
```
⚠️  Uwaga: Serwer używa chunked transfer encoding
   Może to powodować problemy z odbiorem RTCM przez GPS
```

**Problem chunked:**
Serwer NTRIP wysyła dane w formacie:
```
3A\r\n
[58 bajtów RTCM]\r\n
42\r\n
[66 bajtów RTCM]\r\n
```

GPS oczekuje czystego RTCM: `D3 00 ...`

**Jeśli dostaje:** `3A\r\n\xD3\x00...` → **nie rozpozna jako RTCM!**

---

### 5. **Poprawna obsługa braku korekt**

Zmieniono `rtk_age` z `0.0` na `None` gdy brak korekt.

**Efekt:** Aplikacja pokazuje **"-"** zamiast **"0 s"** gdy GPS nie ma korekt.

---

## 🎯 Jak testować:

### **Krok 1: Uruchom nową wersję**

```bash
cd ~/rtk_monitor
python3 app.py
```

### **Krok 2: Obserwuj logi - szukaj:**

#### **A) Czy RTCM dociera do GPS?**
```
📤 RTCM → GPS: 87 bajtów [D3 00 55 2C...]
📤 RTCM → GPS: 124 bajtów [D3 00 7A 1F...]
```

**Jeśli WIDZISZ:** ✅ RTCM jest wysyłany do GPS  
**Jeśli NIE WIDZISZ:** ❌ Problem z NTRIP lub callback

#### **B) Czy GPS ma korekcje?**
```
🔍 GGA: qual=2, sats=28, age=PUSTE
```

**Jeśli `age=PUSTE`:** ❌ GPS nie widzi korekt (mimo że dostaje RTCM!)  
**Jeśli `age='1.2'`:** ✅ GPS ma korekcje!

#### **C) Czy jest problem z chunked?**
```
⚠️  Uwaga: Serwer używa chunked transfer encoding
```

**Jeśli WIDZISZ:** ⚠️ Może być problem - RTCM w złym formacie

---

## 📊 Scenariusze:

### **Scenariusz A: RTCM dociera, GPS ma korekcje**
```
📤 RTCM → GPS: 87 bajtów [D3 00...]
🔍 GGA: qual=5, sats=28, age='1.2'
Fix Type: RTK Float
```
✅ **DZIAŁA!** RTK jest aktywny!

---

### **Scenariusz B: RTCM dociera, ale GPS NIE MA korekt**
```
📤 RTCM → GPS: 87 bajtów [D3 00...]
🔍 GGA: qual=2, sats=28, age=PUSTE
Fix Type: DGPS Fix
```
❌ **Problem:** GPS dostaje RTCM ale go ignoruje!

**Możliwe przyczyny:**
1. ⚠️ Chunked encoding (GPS dostaje `3A\r\n\xD3` zamiast `\xD3`)
2. Format RTCM nie obsługiwany
3. GPS wymaga konfiguracji

---

### **Scenariusz C: RTCM NIE dociera do GPS**
```
📥 Odebrano korekt: 50.1 KB
(brak komunikatów 📤 RTCM → GPS)
```
❌ **Problem:** NTRIP pobiera, ale `write_rtcm()` nie jest wywoływany!

**Możliwa przyczyna:** Callback nie działa poprawnie

---

## 🔍 Dodatkowe testy:

### **Test 1: Raw NMEA GGA**
```bash
sudo cat /dev/serial0 | grep GGA
```

Szukaj pola "age" (11-te pole):
```
$GNGGA,123456.00,5230.1234,N,02100.5678,E,2,28,0.6,100.0,M,45.0,M,1.2,0001*XX
                                                                    ^^^
                                                               age = 1.2s
```

**Jeśli pole jest puste** → GPS nie ma korekt  
**Jeśli pole ma wartość** → GPS ma korekcje, ale parser może nie wyłapywać

---

### **Test 2: RTCM w hex dump**

Jeśli widzisz:
```
📤 RTCM → GPS: 87 bajtów [D3 00 55 2C...]
```

To znaczy RTCM dociera w DOBRYM formacie (zaczyna się od `D3 00`).

**Jeśli widzisz:**
```
📤 RTCM → GPS: 87 bajtów [33 41 0D 0A...]
```
(gdzie `33 41` = "3A" w ASCII)

To znaczy dostaje chunked headers zamiast czystego RTCM! ❌

---

## 🎯 Następne kroki (jeśli nadal nie działa):

### **Jeśli Scenariusz B (RTCM dociera, GPS ignoruje):**

1. **Sprawdź czy chunked jest problem**
   - Jeśli hex dump zaczyna się od `33 41` = chunked headers
   - Trzeba odkodować chunked przed wysłaniem do GPS

2. **Spróbuj inny format RTCM**
   - Zmień port 8082 → 8084 (RTCM 2.3)
   - RTCM 2.3 jest najstarszy i najbardziej kompatybilny

3. **Sprawdź dokumentację LC29H**
   - Może wymaga komendy AT do włączenia RTK?

---

## 📖 Podsumowanie zmian:

| Plik | Zmiana | Cel |
|------|--------|-----|
| `app.py` | Usunięto `broadcast=True` | Naprawiono błąd Flask |
| `gps_reader.py` | Dodano debug `write_rtcm()` | Zobacz czy RTCM dociera |
| `gps_reader.py` | Dodano debug GGA | Zobacz czy GPS ma korekcje |
| `gps_reader.py` | `rtk_age = None` gdy brak | Pokazuj "-" zamiast "0" |
| `ntrip_client.py` | Wykrywanie chunked | Ostrzeżenie o potencjalnym problemie |

---

**Uruchom nową wersję i daj znać co pokazują logi!** 🎯

Kluczowe pytania:
1. Czy widzisz `📤 RTCM → GPS`?
2. Jaki jest `age` w komunikacie `🔍 GGA`?
3. Czy widzisz ostrzeżenie o chunked encoding?
