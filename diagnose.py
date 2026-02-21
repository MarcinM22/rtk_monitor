#!/usr/bin/env python3
"""
Diagnostyka polaczenia z modulem LC29H.
Sprawdza: port, odczyt NMEA, zapis (TX), i czy diff_age sie zmienia.
Uruchom: python3 diagnose.py
"""
import serial
import time
import sys
import os
import glob

def find_port():
    candidates = ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/ttyUSB0', '/dev/serial0']
    candidates += sorted(glob.glob('/dev/ttyUSB*'))
    seen = set()
    for c in candidates:
        r = os.path.realpath(c)
        if r in seen:
            continue
        seen.add(r)
        if not os.path.exists(c):
            continue
        try:
            s = serial.Serial(c, 115200, timeout=2)
            t0 = time.time()
            while time.time() - t0 < 3:
                line = s.readline().decode('ascii', errors='ignore').strip()
                if line.startswith('$G'):
                    s.close()
                    return c
            s.close()
        except Exception:
            pass
    return None

def main():
    print("=" * 60)
    print("  LC29H Diagnostyka")
    print("=" * 60)
    print()

    # 1. Znajdz port
    print("[1] Szukam portu GPS...")
    port = find_port()
    if not port:
        print("  BLAD: Nie znaleziono modulu GPS!")
        print("  Sprawdz: jumper B, UART wlaczony, antena podlaczona")
        sys.exit(1)
    print("  OK: %s" % port)
    real = os.path.realpath(port)
    if real != port:
        print("  (realpath: %s)" % real)
    print()

    # 2. Otworz port
    print("[2] Otwieram port...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        print("  BLAD: %s" % e)
        sys.exit(1)
    print("  OK: otwarty")
    print("  readable: %s" % ser.readable())
    print("  writable: %s" % ser.writable())
    print()

    # 3. Odczyt NMEA
    print("[3] Odczyt NMEA (5s)...")
    gga_count = 0
    last_gga = None
    fix_quality = 0
    t0 = time.time()
    while time.time() - t0 < 5:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode('ascii', errors='ignore').strip()
        if '$' in line and 'GGA' in line:
            gga_count += 1
            last_gga = line
            parts = line.split(',')
            if len(parts) > 6:
                try:
                    fix_quality = int(parts[6])
                except ValueError:
                    pass
            if gga_count <= 3:
                print("  GGA: %s" % line[:80])
    print("  Odebrano %d zdaN GGA w 5s" % gga_count)
    print("  Fix quality: %d" % fix_quality)
    fix_names = {0:'No Fix', 1:'GPS', 2:'DGPS', 4:'RTK Fixed', 5:'RTK Float'}
    print("  Typ: %s" % fix_names.get(fix_quality, 'nieznany'))
    print()

    # 4. Test zapisu
    print("[4] Test zapisu do portu (TX)...")
    # Wyslij komende PAIR - zapytanie o wersje firmware
    # LC29H odpowiada na komendy $PAIR
    test_cmd = b"$PAIR020*38\r\n"
    try:
        written = ser.write(test_cmd)
        ser.flush()
        print("  Wyslano %d bajtow: %s" % (written, test_cmd.strip().decode()))
    except Exception as e:
        print("  BLAD ZAPISU: %s" % e)
        print("  >>> To jest prawdopodobnie przyczyna braku RTK! <<<")
        ser.close()
        sys.exit(1)

    # Czekaj na odpowiedz
    time.sleep(0.5)
    response_found = False
    t0 = time.time()
    while time.time() - t0 < 3:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode('ascii', errors='ignore').strip()
        if 'PAIR' in line or 'pair' in line.lower():
            print("  Odpowiedz: %s" % line[:80])
            response_found = True
            break
        elif line.startswith('$'):
            pass  # normalne NMEA, ignoruj

    if response_found:
        print("  OK: Modul odpowiada na komendy - TX dziala!")
    else:
        print("  UWAGA: Brak odpowiedzi na komende PAIR")
        print("  To moze oznaczac:")
        print("    - TX (zapis) nie dziala -> brak RTK")
        print("    - Modul nie obsluguje tej komendy (mniej prawdopodobne)")
    print()

    # 5. Test symulowanego RTCM
    print("[5] Test zapisu danych binarnych (symulacja RTCM)...")
    # Wyslij 100 bajtow losowych (nie prawdziwe RTCM, ale testuje TX)
    test_data = bytes(range(256))[:100]
    try:
        written = ser.write(test_data)
        ser.flush()
        print("  Wyslano %d bajtow binarnych" % written)
        print("  OK: Zapis binarny dziala")
    except Exception as e:
        print("  BLAD: %s" % e)
    print()

    # 6. Sprawdz diff_age w GGA
    print("[6] Sprawdzam pola roznicowe w GGA...")
    if last_gga:
        parts = last_gga.split(',')
        if len(parts) >= 14:
            print("  Fix quality (pole 6): %s" % parts[6])
            print("  Diff age (pole 13): '%s'" % parts[13])
            print("  Diff station (pole 14): '%s'" % parts[14].split('*')[0] if len(parts) > 14 else "brak")
            if parts[13] and float(parts[13]) > 0:
                print("  -> Modul OTRZYMUJE korekcje roznicowe!")
            else:
                print("  -> Modul NIE otrzymuje korekcji (puste pole diff_age)")
        else:
            print("  GGA ma za malo pol: %d" % len(parts))
    else:
        print("  Brak zdania GGA do analizy")
    print()

    # 7. Podsumowanie
    print("=" * 60)
    print("  PODSUMOWANIE")
    print("=" * 60)
    print("  Port: %s (%s)" % (port, "writable" if ser.writable() else "READ-ONLY!"))
    print("  NMEA: %s" % ("OK" if gga_count > 0 else "BRAK"))
    print("  Fix: %s (quality=%d)" % (fix_names.get(fix_quality, '?'), fix_quality))
    print()

    if fix_quality <= 1:
        print("  SUGESTIE:")
        print("  1. Uruchom app.py z NTRIP, poczekaj 2-5 minut")
        print("  2. Sprawdz czy antena GNSS ma otwarty widok nieba")
        print("  3. Sprawdz login/haslo ASG-EUPOS")
        print("  4. Jesli diff_age jest puste - problem z TX (zapis do modulu)")
        print("     Sprawdz polaczenie fizyczne HAT z RPi")
    print()

    ser.close()

if __name__ == '__main__':
    main()
