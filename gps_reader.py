"""
gps_reader.py - Czytnik NMEA dla Waveshare LC29H(DA) RTK HAT
Auto-detekcja portu: RPi 4B -> /dev/ttyS0, RPi 5 -> /dev/ttyAMA0, USB -> /dev/ttyUSB0
"""

import serial
import threading
import time
import logging
import os
import glob
import pynmea2

logger = logging.getLogger(__name__)


def detect_serial_port():
    """
    Automatyczne wykrywanie portu szeregowego modulu LC29H.
    Wg dokumentacji Waveshare:
      RPi 4B z jumperem B: /dev/ttyS0
      RPi 5 z jumperem B:  /dev/ttyAMA0
      Jumper A (USB):       /dev/ttyUSB0
    """
    candidates = ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/ttyUSB0', '/dev/serial0']
    candidates += sorted(glob.glob('/dev/ttyUSB*'))
    candidates += sorted(glob.glob('/dev/ttyACM*'))

    seen = set()
    unique = []
    for c in candidates:
        r = os.path.realpath(c)
        if r not in seen:
            seen.add(r)
            unique.append(c)

    for port in unique:
        if not os.path.exists(port):
            continue
        try:
            s = serial.Serial(port, 115200, timeout=2)
            t0 = time.time()
            while time.time() - t0 < 3:
                line = s.readline().decode('ascii', errors='ignore').strip()
                if line.startswith('$G') or line.startswith('$P'):
                    s.close()
                    logger.info("GPS wykryty na: %s", port)
                    return port
            s.close()
        except (serial.SerialException, OSError) as e:
            logger.debug("Port %s niedostepny: %s", port, e)
            continue

    logger.warning("Brak auto-detekcji portu GPS, domyslnie /dev/ttyS0")
    return '/dev/ttyS0'


class GPSReader:
    """Czytnik danych GPS/GNSS z portu szeregowego LC29H."""

    def __init__(self, port=None, baudrate=115200):
        self.port = port or detect_serial_port()
        self.baudrate = baudrate
        self.serial_conn = None
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._data = {
            'fix_type': 0,
            'fix_quality': 0,
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'altitude_ellipsoidal': None,
            'geo_sep': None,
            'satellites_used': 0,
            'satellites_visible': 0,
            'hdop': None,
            'pdop': None,
            'vdop': None,
            'speed_knots': None,
            'speed_kmh': None,
            'course': None,
            'timestamp': None,
            'date': None,
            'diff_age': None,
            'diff_station': None,
            'gga_sentence': None,
            'mode_indicator': None,
        }

    def connect(self):
        """Otworz port szeregowy."""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = serial.Serial(
                self.port, self.baudrate, timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE)
            logger.info("Polaczono z %s @ %d baud", self.port, self.baudrate)
            return True
        except serial.SerialException as e:
            logger.error("Nie mozna otworzyc portu %s: %s", self.port, e)
            return False

    def start(self):
        """Uruchom watek odczytu GPS."""
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.connect():
                return False
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("GPS Reader uruchomiony na %s", self.port)

        # Ustaw tryb Rover (wymagane dla RTK)
        time.sleep(0.5)
        self._configure_rover_mode()
        return True

    def _nmea_checksum(self, sentence):
        """Oblicz NMEA checksum (XOR bajtow miedzy $ i *)."""
        cs = 0
        for ch in sentence:
            cs ^= ord(ch)
        return "%02X" % cs

    def send_command(self, cmd):
        """Wyslij komende PAIR do modulu LC29H.
        cmd: np. 'PAIR432,0' (bez $ i *checksum)
        """
        cs = self._nmea_checksum(cmd)
        full = "$%s*%s\r\n" % (cmd, cs)
        logger.info("GPS CMD: %s", full.strip())
        return self.write(full.encode('ascii'))

    def _configure_rover_mode(self):
        """Skonfiguruj modul LC29H(DA) do trybu Rover (odbiorca RTK)."""
        # PAIR432,0 = Rover mode (0=Rover, 1=Base survey-in, 2=Base fixed)
        if self.send_command("PAIR432,0"):
            logger.info("GPS: wyslano komende Rover Mode (PAIR432,0)")
        else:
            logger.warning("GPS: nie udalo sie wyslac komendy Rover Mode")

        # Poczekaj na potwierdzenie
        time.sleep(0.3)

        # PAIR513,1,5 = Wlacz wejscie RTCM na UART1 (jesli modul to wspiera)
        self.send_command("PAIR513,1,5")

    def stop(self):
        """Zatrzymaj odczyt GPS."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        logger.info("GPS Reader zatrzymany")

    def write(self, data):
        """Wyslij dane do modulu GPS (korekcje RTCM z NTRIP)."""
        if not data:
            return False
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.warning("write(): port nie jest otwarty")
            return False
        try:
            written = self.serial_conn.write(data)
            self.serial_conn.flush()
            with self._lock:
                self._data['_rtcm_bytes_written'] = self._data.get('_rtcm_bytes_written', 0) + written
            return True
        except serial.SerialException as e:
            logger.error("Blad zapisu do portu: %s", e)
            return False

    def get_data(self):
        """Zwroc kopie aktualnych danych GPS."""
        with self._lock:
            return dict(self._data)

    def get_gga(self):
        """Zwroc ostatnie zdanie GGA (potrzebne dla NTRIP)."""
        with self._lock:
            return self._data.get('gga_sentence')

    def _read_loop(self):
        """Glowna petla odczytu - wyciaga NMEA z mieszanego strumienia binarnego.
        LC29H wysyla binarne dane (RTCM echo, proprietary) razem z NMEA
        na jednym UART. readline() nie dziala bo binarne dane zawieraja
        losowe \\n. Zamiast tego czytamy blokami i wyciagamy zdania NMEA
        po checksumie.
        """
        nmea_buf = ""
        while self._running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    time.sleep(2)
                    self.connect()
                    continue
                raw = self.serial_conn.read(512)
                if not raw:
                    continue
                text = raw.decode('ascii', errors='replace')
                nmea_buf += text
                while True:
                    start = nmea_buf.find('$')
                    if start < 0:
                        nmea_buf = ""
                        break
                    if start > 0:
                        nmea_buf = nmea_buf[start:]
                    star = nmea_buf.find('*', 1)
                    if star < 0:
                        if len(nmea_buf) > 256:
                            nmea_buf = nmea_buf[-128:]
                        break
                    end = star + 3
                    if end > len(nmea_buf):
                        break
                    sentence = nmea_buf[1:star]
                    cs_str = nmea_buf[star + 1:end]
                    nmea_buf = nmea_buf[end:]
                    # Sprawdz czy czyste ASCII drukowalne
                    clean = True
                    for ch in sentence:
                        c = ord(ch)
                        if c < 32 or c > 126:
                            clean = False
                            break
                    if not clean:
                        continue
                    # Weryfikuj NMEA checksum
                    try:
                        expected = int(cs_str[:2], 16)
                    except ValueError:
                        continue
                    actual = 0
                    for ch in sentence:
                        actual ^= ord(ch)
                    if actual != expected:
                        continue
                    full = "$" + sentence + "*" + cs_str[:2]
                    self._parse_nmea(full)
            except serial.SerialException as e:
                logger.warning("Blad odczytu portu: %s", e)
                time.sleep(3)
                try:
                    self.connect()
                except Exception:
                    pass
            except Exception as e:
                logger.debug("Blad parsowania: %s", e)

    def _parse_nmea(self, sentence):
        """Parsuj zdanie NMEA i zaktualizuj dane.
        Uzywa sentence_type zamiast isinstance bo modul wysyla $GN*
        (multi-constellation) a pynmea2.types.talker.GGA matchuje tylko $GP*.
        """
        try:
            msg = pynmea2.parse(sentence)
        except pynmea2.ParseError:
            return
        with self._lock:
            if msg.sentence_type == 'GGA':
                self._parse_gga(msg, sentence)
            elif msg.sentence_type == 'RMC':
                self._parse_rmc(msg)
            elif msg.sentence_type == 'GSA':
                self._parse_gsa(msg)
            elif msg.sentence_type == 'GSV':
                self._parse_gsv(msg)
            elif msg.sentence_type == 'VTG':
                self._parse_vtg(msg)

    def _parse_gga(self, msg, raw):
        """GGA: fix_quality 0=brak 1=GPS 2=DGPS 4=RTK_Fixed 5=RTK_Float
        UWAGA: pole altitude w GGA = wysokosc nad MSL (po odjęciu geoidy wg EGM96).
        Prawdziwa wysokosc elipsoidalna = altitude + geo_sep.
        """
        try:
            self._data['fix_quality'] = int(msg.gps_qual) if msg.gps_qual else 0
        except (ValueError, AttributeError):
            self._data['fix_quality'] = 0
        if msg.latitude and msg.longitude:
            self._data['latitude'] = msg.latitude
            self._data['longitude'] = msg.longitude
        try:
            if msg.altitude:
                alt_msl = float(msg.altitude)
                self._data['altitude'] = alt_msl
                # Odczytaj geoid separation (pole 11 GGA)
                geo_sep = None
                try:
                    if getattr(msg, 'geo_sep', None):
                        geo_sep = float(msg.geo_sep)
                except (ValueError, TypeError):
                    pass
                self._data['geo_sep'] = geo_sep
                # Prawdziwa wysokosc elipsoidalna = MSL + geoida
                if geo_sep is not None:
                    self._data['altitude_ellipsoidal'] = alt_msl + geo_sep
                else:
                    self._data['altitude_ellipsoidal'] = alt_msl
        except (ValueError, TypeError):
            pass
        try:
            self._data['satellites_used'] = int(msg.num_sats) if msg.num_sats else 0
        except (ValueError, AttributeError):
            pass
        try:
            self._data['hdop'] = float(msg.horizontal_dil) if msg.horizontal_dil else None
        except (ValueError, AttributeError):
            pass
        if msg.timestamp:
            self._data['timestamp'] = str(msg.timestamp)
        try:
            self._data['diff_age'] = float(msg.age_gps_data) if getattr(msg, 'age_gps_data', None) else None
        except (ValueError, AttributeError):
            self._data['diff_age'] = None
        try:
            if getattr(msg, 'ref_station_id', None):
                self._data['diff_station'] = str(msg.ref_station_id)
        except (ValueError, AttributeError):
            pass
        self._data['gga_sentence'] = raw

    def _parse_rmc(self, msg):
        """RMC: pozycja, predkosc, kurs, data."""
        if msg.latitude and msg.longitude:
            self._data['latitude'] = msg.latitude
            self._data['longitude'] = msg.longitude
        try:
            if msg.spd_over_grnd:
                self._data['speed_knots'] = float(msg.spd_over_grnd)
                self._data['speed_kmh'] = float(msg.spd_over_grnd) * 1.852
        except (ValueError, TypeError, AttributeError):
            pass
        try:
            if msg.true_course:
                self._data['course'] = float(msg.true_course)
        except (ValueError, TypeError, AttributeError):
            pass
        if msg.datestamp:
            self._data['date'] = str(msg.datestamp)
        if msg.timestamp:
            self._data['timestamp'] = str(msg.timestamp)

    def _parse_gsa(self, msg):
        """GSA: DOP i fix type."""
        try:
            if getattr(msg, 'mode_fix_type', None):
                self._data['fix_type'] = int(msg.mode_fix_type)
        except (ValueError, AttributeError):
            pass
        for attr in ('pdop', 'hdop', 'vdop'):
            try:
                v = getattr(msg, attr, None)
                if v:
                    self._data[attr] = float(v)
            except (ValueError, TypeError):
                pass

    def _parse_gsv(self, msg):
        """GSV: satelity w zasiegu."""
        try:
            if getattr(msg, 'num_sv_in_view', None):
                self._data['satellites_visible'] = int(msg.num_sv_in_view)
        except (ValueError, AttributeError):
            pass

    def _parse_vtg(self, msg):
        """VTG: predkosc nad ziemia."""
        try:
            if getattr(msg, 'spd_over_grnd_kmph', None):
                self._data['speed_kmh'] = float(msg.spd_over_grnd_kmph)
        except (ValueError, TypeError, AttributeError):
            pass
