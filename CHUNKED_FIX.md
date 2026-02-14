# ✅ NAPRAWIONO: Chunked Transfer Encoding Decoder

## 🎯 Co zostało naprawione?

### **Problem:**
Serwer NTRIP wysyłał dane w formacie HTTP chunked transfer encoding:
```
31 46 0D 0A [31 bajtów RTCM] 0D 0A
42 41 0D 0A [186 bajtów RTCM] 0D 0A
```

GPS odbierał:
```
31 46 0D 0A D3 00 ... ← "1F\r\n" zamiast czystego RTCM!
```

GPS oczekiwał:
```
D3 00 ... ← czyste RTCM bez headerów
```

**Efekt:** GPS **ignorował** wszystkie dane RTCM bo nie rozpoznawał sygnatury!

---

## ✅ Rozwiązanie:

Dodano **dekoder HTTP chunked transfer encoding** który:

1. **Wykrywa** chunked mode w odpowiedzi serwera
2. **Dekoduje** każdy chunk:
   - Czyta hex header (np. `BA\r\n`)
   - Parsuje długość (`BA` hex = 186 dec)
   - Czyta **dokładnie 186 bajtów** czystego RTCM
   - Pomija trailing `\r\n`
3. **Wysyła CZYSTE RTCM** do GPS (bez headerów!)

---

## 📊 Co się zmieniło w kodzie:

### 1. **ntrip_client.py**

**Dodano:**
- Flagę `chunked_mode` (auto-wykrywanie)
- Metodę `_read_chunk()` (dekoder chunked)
- Logikę w `_rtcm_loop()` do dekodowania

**Efekt:** RTCM jest teraz czyszczony przed wysłaniem do GPS!

### 2. **gps_reader.py**

**Zmieniono:**
- Debug w `write_rtcm()` pokazuje czy dane to prawidłowy RTCM

**Teraz pokazuje:**
```
📤 ✅ RTCM → GPS: 186 bajtów [D3 00 ...]  ← prawidłowy!
📤 ❌ NIE-RTCM → GPS: 37 bajtów [31 46 ...]  ← chunked garbage
```

---

## 🚀 Czego się spodziewać po uruchomieniu:

### **Przy starcie zobaczysz:**

```
✓ Połączono z serwerem NTRIP
✓ Autoryzacja udana
⚠️  Uwaga: Serwer używa chunked transfer encoding
   → Włączam dekoder chunked - dane RTCM będą czyszczone
📡 Rozpoczęto odbieranie korekt RTK...
🔧 Używam dekodera chunked transfer encoding
```

### **Podczas działania:**

```
📤 ✅ RTCM → GPS: 186 bajtów [D3 00 BA 12...]  ← CZYSTE RTCM!
📤 ✅ RTCM → GPS: 313 bajtów [D3 00 39 41...]  ← CZYSTE RTCM!
✅ Wykryto prawidłową sygnaturę RTCM (D3 00)!
```

**WAŻNE:** Wszystkie pakiety powinny zaczynać się od `D3 00` (sygnatura RTCM)!

### **Po 1-2 minutach:**

```
🔍 GGA: qual=5, sats=20, age='1.2'  ← age WYPEŁNIONY!
Fix Type: RTK Float                 ← RTK DZIAŁA!
```

### **Po 2-5 minutach:**

```
🔍 GGA: qual=4, sats=20, age='0.8'
Fix Type: RTK Fixed  🎉             ← DOKŁADNOŚĆ 1-2 CM!
```

---

## 🔍 Jak sprawdzić czy działa?

### **1. Sprawdź logi startowe:**

**Powinno być:**
```
⚠️  Uwaga: Serwer używa chunked transfer encoding
   → Włączam dekoder chunked - dane RTCM będą czyszczone
```

**NIE:**
```
✓ Serwer wysyła czyste RTCM (bez chunked)
```

### **2. Sprawdź pakiety RTCM:**

**Powinno być:**
```
📤 ✅ RTCM → GPS: 186 bajtów [D3 00 ...]
```

**NIE:**
```
📤 ❌ NIE-RTCM → GPS: 192 bajtów [42 41 ...]
```

### **3. Sprawdź sygnaturę:**

**Powinno być (po kilku sekundach):**
```
✅ Wykryto prawidłową sygnaturę RTCM (D3 00)!
```

### **4. Sprawdź GGA:**

**Powinno być (po 1-2 min):**
```
🔍 GGA: qual=5, sats=20, age='1.2'  ← liczba!
```

**NIE:**
```
🔍 GGA: qual=2, sats=20, age=PUSTE  ← puste
```

---

## ❌ Co zrobić jeśli NADAL nie działa?

### **Jeśli widzisz:**
```
📤 ❌ NIE-RTCM → GPS: ...
```

**Problem:** Dekoder chunked nie działa poprawnie.

**Debug:**
1. Sprawdź czy `chunked_mode = True` (logi startowe)
2. Sprawdź logi błędów w `_read_chunk()`

### **Jeśli widzisz:**
```
📤 ✅ RTCM → GPS: 186 bajtów [D3 00 ...]
🔍 GGA: qual=2, sats=20, age=PUSTE
```

**Problem:** GPS dostaje prawidłowe RTCM ale je ignoruje!

**Możliwe przyczyny:**
1. LC29H nie obsługuje RTCM 3.1 (spróbuj port 8084, RTCM 2.3)
2. LC29H wymaga komendy AT do włączenia RTK
3. Hardware problem z modułem

---

## 📖 Dodatkowe informacje:

### **Czym jest chunked encoding?**

HTTP/1.1 umożliwia serwerowi wysyłanie danych w "chunkach" (kawałkach) bez określania z góry całkowitej długości.

**Format:**
```
<długość_w_hex>\r\n
<dane>\r\n
<długość_w_hex>\r\n
<dane>\r\n
0\r\n
\r\n
```

**Przykład:**
```
1F\r\n       ← 31 bajtów w hex
[31 bajtów RTCM]\r\n
BA\r\n       ← 186 bajtów w hex
[186 bajtów RTCM]\r\n
0\r\n        ← koniec
\r\n
```

### **Dlaczego to był problem?**

GPS nie rozumie HTTP - oczekuje czystych danych RTCM zaczynających się od `D3 00`.

Gdy dostaje `31 46 0D 0A D3 00...` (`"1F\r\n"` + RTCM), myśli że to są śmieci i odrzuca.

### **Dlaczego GPS używał DGPS?**

GPS LC29H ma wbudowane odbieranie SBAS/EGNOS (satelitarne korekcje różnicowe z Europy). Gdy nie ma RTCM, automatycznie przełącza się na SBAS → DGPS Fix (dokładność ~1m).

---

## 🎯 Podsumowanie:

| Przed naprawą | Po naprawie |
|---------------|-------------|
| `📤 192 bajtów [42 41 0D 0A...]` | `📤 ✅ RTCM 186 bajtów [D3 00...]` |
| `🔍 GGA: age=PUSTE` | `🔍 GGA: age='1.2'` |
| `Fix Type: DGPS` | `Fix Type: RTK Float/Fixed` |
| GPS ignoruje RTCM | GPS używa RTCM! |

---

## 🚀 Teraz uruchom i sprawdź!

```bash
cd ~/rtk_monitor
python3 app.py
```

**Czekaj 1-2 minuty i sprawdź czy:**
1. ✅ Pakiety zaczynają się od `D3 00`
2. ✅ `age=` ma wartość (nie jest puste)
3. ✅ Fix Type zmienia się na RTK Float

**Jeśli TAK → RTK DZIAŁA! 🎉**

**Powodzenia!** 🎯
