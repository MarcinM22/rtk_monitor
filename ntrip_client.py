"""
ntrip_client.py - Klient NTRIP dla ASG-EUPOS
Uzywa NTRIP 1.0 (HTTP/1.0) zeby uniknac chunked encoding.
Jesli serwer wymusza chunked - automatycznie de-chunkuje.

Parametry ASG-EUPOS (zrodlo: asgeupos.pl/serwisy-rtk):
  Host: system.asgeupos.pl (lub 91.198.76.2)
  Port 8086: RTCM 3.4 - GPS+GLO+GAL+BDS (ZALECANY)
  Port 8082/8083: RTCM 3.1 - GPS+GLO
"""

import socket
import base64
import threading
import time
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    'host': 'system.asgeupos.pl',
    'port': 8086,
    'mountpoint': 'RTK4G_MULTI_RTCM32',
    'username': '',
    'password': '',
    'send_gga': True,
    'gga_interval': 10,
}

STATION_SUFFIXES = {
    8086: '_RTCM_3_2',
    8082: '_RTCM_3_1',
    8083: '_RTCM_3_1',
    8084: '_RTCM_2_3',
    8085: '_RTCM_2_3',
}

AUTO_MOUNTPOINTS = {
    8086: 'RTK4G_MULTI_RTCM32',
    8082: 'NAWGEO_POJ_3_1',
    8083: 'NAWGEO_POJ_3_1',
}


def build_mountpoint(station_id, port=8086):
    """Buduje prawidlowy mountpoint ASG-EUPOS."""
    if not station_id or station_id.upper() == 'AUTO':
        return AUTO_MOUNTPOINTS.get(port, 'RTK4G_MULTI_RTCM32')
    if '_RTCM_' in station_id.upper():
        return station_id
    suffix = STATION_SUFFIXES.get(port, '_RTCM_3_2')
    return station_id.upper() + suffix


def find_rtcm3_preamble(data):
    """Szukaj preamble RTCM3 (0xD3) z walidacja naglowka."""
    for i in range(len(data) - 2):
        if data[i] == 0xD3 and (data[i + 1] & 0xFC) == 0:
            length = ((data[i + 1] & 0x03) << 8) | data[i + 2]
            if 0 < length < 1024:
                return i, length
    return -1, 0


class NTRIPClient:
    """Klient NTRIP do odbioru korekcji RTK z ASG-EUPOS."""

    def __init__(self, gps_reader, config=None):
        self.gps = gps_reader
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)

        self._socket = None
        self._running = False
        self._connected = False
        self._chunked = False
        self._thread = None
        self._lock = threading.Lock()
        self._first_data_logged = False
        self._chunk_buf = b""

        self._stats = {
            'connected': False,
            'bytes_received': 0,
            'rtcm_bytes_sent': 0,
            'last_data_time': None,
            'error': None,
            'mountpoint': None,
            'reconnect_count': 0,
            'chunked': False,
        }

    def configure(self, config):
        """Zmien konfiguracje i restartuj jesli dzialal."""
        was_running = self._running
        if was_running:
            self.stop()
        self.config.update(config)
        if 'station' in config or 'port' in config:
            station = config.get('station', self.config.get('station', 'AUTO'))
            port = self.config.get('port', 8086)
            self.config['mountpoint'] = build_mountpoint(station, port)
        if was_running:
            self.start()

    def start(self):
        """Uruchom klient NTRIP."""
        if not self.config.get('username') or not self.config.get('password'):
            with self._lock:
                self._stats['error'] = 'Brak loginu/hasla ASG-EUPOS'
            return False
        self._running = True
        self._first_data_logged = False
        with self._lock:
            self._stats['bytes_received'] = 0
            self._stats['rtcm_bytes_sent'] = 0
            self._stats['reconnect_count'] = 0
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("NTRIP start -> %s:%d/%s",
                     self.config['host'], self.config['port'], self.config['mountpoint'])
        return True

    def stop(self):
        """Zatrzymaj klient NTRIP."""
        self._running = False
        self._connected = False
        # Zamknij socket pod lockiem zeby uniknac race condition z _receive_data
        sock = None
        with self._lock:
            sock = self._socket
            self._socket = None
            self._stats['connected'] = False
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("NTRIP zatrzymany")

    def get_stats(self):
        with self._lock:
            return dict(self._stats)

    # === Glowna petla ===

    def _run_loop(self):
        while self._running:
            try:
                if self._connect():
                    self._receive_data()
            except Exception as e:
                logger.error("NTRIP blad: %s", e)
                with self._lock:
                    self._stats['error'] = str(e)
            self._disconnect()
            if self._running:
                with self._lock:
                    self._stats['reconnect_count'] += 1
                logger.info("NTRIP: reconnect za 5s...")
                for _ in range(50):
                    if not self._running:
                        return
                    time.sleep(0.1)

    # === Polaczenie ===

    def _connect(self):
        host = self.config['host']
        port = self.config['port']
        mp = self.config['mountpoint']
        user = self.config['username']
        pwd = self.config['password']

        logger.info("NTRIP: laczenie z %s:%d/%s...", host, port, mp)
        with self._lock:
            self._stats['error'] = None
            self._stats['mountpoint'] = mp

        # TCP
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(15)
            self._socket.connect((host, port))
        except socket.error as e:
            logger.error("NTRIP: blad TCP: %s", e)
            with self._lock:
                self._stats['error'] = "Blad TCP: %s" % e
            return False

        # === NTRIP 1.0 request (HTTP/1.0 = ZERO chunked encoding) ===
        auth = base64.b64encode(("%s:%s" % (user, pwd)).encode()).decode()
        gga = self.gps.get_gga() if self.config.get('send_gga') else None

        request = "GET /%s HTTP/1.0\r\n" % mp
        request += "User-Agent: NTRIP RTKMonitor/1.0\r\n"
        request += "Authorization: Basic %s\r\n" % auth
        if gga:
            request += "Ntrip-GGA: %s\r\n" % gga
        request += "\r\n"

        logger.debug("NTRIP request:\n%s", request.strip())

        try:
            self._socket.sendall(request.encode('ascii'))
        except socket.error as e:
            logger.error("NTRIP: blad wysylania: %s", e)
            with self._lock:
                self._stats['error'] = "Blad wysylania: %s" % e
            return False

        # Odczytaj naglowki odpowiedzi
        try:
            response = b""
            self._socket.settimeout(10)
            while b"\r\n\r\n" not in response:
                chunk = self._socket.recv(4096)
                if not chunk:
                    break
                response += chunk
                if len(response) > 16384:
                    break
        except socket.timeout:
            logger.error("NTRIP: timeout")
            with self._lock:
                self._stats['error'] = "Timeout odpowiedzi serwera"
            return False

        header_end = response.find(b"\r\n\r\n")
        if header_end < 0:
            with self._lock:
                self._stats['error'] = "Niekompletna odpowiedz"
            return False

        headers_text = response[:header_end].decode('ascii', errors='ignore')
        body = response[header_end + 4:]
        first_line = headers_text.split('\r\n')[0]

        logger.info("NTRIP odpowiedz: %s", first_line)
        logger.debug("NTRIP headers: %s", headers_text.replace('\r\n', ' | '))

        # Sprawdz status
        ok = False
        if 'ICY 200 OK' in first_line:
            ok = True
        else:
            parts = first_line.split()
            if len(parts) >= 2 and parts[1] == '200':
                ok = True

        if not ok:
            if 'SOURCETABLE' in headers_text or 'SOURCETABLE' in body.decode('ascii', errors='ignore')[:200]:
                err = "Mountpoint '%s' nie istnieje" % mp
            elif '401' in first_line:
                err = "Bledny login lub haslo"
                self._running = False  # nie probuj ponownie
            else:
                err = first_line
            logger.error("NTRIP: %s", err)
            with self._lock:
                self._stats['error'] = err
            return False

        # === Wykryj chunked encoding ===
        headers_lower = headers_text.lower()
        self._chunked = 'transfer-encoding: chunked' in headers_lower
        self._chunk_buf = b""

        if self._chunked:
            logger.warning("NTRIP: CHUNKED ENCODING wykryte! De-chunking wlaczony.")
        else:
            logger.info("NTRIP: strumien surowy (bez chunked) - OK")

        self._connected = True
        with self._lock:
            self._stats['connected'] = True
            self._stats['error'] = None
            self._stats['chunked'] = self._chunked

        logger.info("NTRIP: polaczono z %s (chunked=%s)", mp, self._chunked)

        # Przetworz dane po headerach
        if body:
            self._process_received(body, is_first=True)

        self._socket.settimeout(30)
        return True

    # === Odbior danych ===

    def _receive_data(self):
        last_gga_time = 0
        gga_interval = self.config.get('gga_interval', 10)

        while self._running and self._connected:
            sock = self._socket
            if sock is None:
                break
            try:
                data = sock.recv(4096)
                if not data:
                    logger.warning("NTRIP: serwer zamknal polaczenie")
                    self._connected = False
                    break

                with self._lock:
                    self._stats['bytes_received'] += len(data)
                    self._stats['last_data_time'] = time.time()

                self._process_received(data)

                # GGA keep-alive
                now = time.time()
                if self.config.get('send_gga') and now - last_gga_time > gga_interval:
                    gga = self.gps.get_gga()
                    if gga:
                        try:
                            sock.sendall((gga + "\r\n").encode('ascii'))
                            last_gga_time = now
                        except (socket.error, OSError):
                            pass

            except socket.timeout:
                gga = self.gps.get_gga()
                if gga:
                    try:
                        sock.sendall((gga + "\r\n").encode('ascii'))
                    except (socket.error, OSError):
                        self._connected = False
                        break
            except (socket.error, OSError) as e:
                if self._running:
                    logger.error("NTRIP: blad odbioru: %s", e)
                self._connected = False
                break

    def _process_received(self, data, is_first=False):
        """Przetworz odebrane dane - de-chunk jesli trzeba, wyslij do GPS."""
        if self._chunked:
            rtcm = self._extract_chunks(data)
        else:
            rtcm = data

        if not rtcm:
            return

        # Loguj pierwsze dane dla diagnostyki
        if not self._first_data_logged or is_first:
            hex_preview = ' '.join('%02X' % b for b in rtcm[:24])
            logger.info("RTCM -> GPS: %d bajtow [%s]", len(rtcm), hex_preview)

            offset, length = find_rtcm3_preamble(rtcm)
            if offset >= 0:
                if offset + 4 < len(rtcm):
                    msg_type = (rtcm[offset + 3] << 4) | ((rtcm[offset + 4] >> 4) & 0x0F)
                    logger.info("RTCM3 OK: typ=%d dlugosc=%d offset=%d", msg_type, length, offset)
                else:
                    logger.info("RTCM3 preamble na offset=%d dlugosc=%d", offset, length)
                if offset > 0:
                    logger.warning("RTCM3: %d bajtow smieci przed preamble!", offset)
            else:
                logger.error("BRAK RTCM3 preamble (0xD3)! Dane moga byc uszkodzone.")
                # Pokaz jako tekst jesli to moze byc chunked
                try:
                    txt = rtcm[:60].decode('ascii', errors='replace')
                    logger.error("Dane jako tekst: '%s'", txt.strip())
                except Exception:
                    pass

            self._first_data_logged = True

        # Wyslij do modulu GPS
        if self.gps.write(rtcm):
            with self._lock:
                self._stats['rtcm_bytes_sent'] += len(rtcm)
        else:
            logger.warning("Blad zapisu %d bajtow RTCM do GPS", len(rtcm))

    def _extract_chunks(self, data):
        """Wyciagnij surowe dane z chunked encoding."""
        self._chunk_buf += data
        result = b""

        while self._chunk_buf:
            # Szukaj rozmiaru chunka (hex + \r\n)
            nl_pos = self._chunk_buf.find(b"\r\n")
            if nl_pos < 0:
                # Niepelna linia - czekaj na wiecej danych
                # Ale jesli bufor jest duzy i zaczyna sie od 0xD3, to nie jest chunked
                if len(self._chunk_buf) > 10 and self._chunk_buf[0] == 0xD3:
                    result += self._chunk_buf
                    self._chunk_buf = b""
                break

            size_str = self._chunk_buf[:nl_pos].decode('ascii', errors='ignore').strip()

            # Puste linie - pomin
            if not size_str:
                self._chunk_buf = self._chunk_buf[nl_pos + 2:]
                continue

            # Sprobuj parsowac jako hex
            try:
                chunk_size = int(size_str, 16)
            except ValueError:
                # To nie jest chunk header - prawdopodobnie surowe dane
                # Wyslij calosc i wyczysc bufor
                result += self._chunk_buf
                self._chunk_buf = b""
                break

            if chunk_size == 0:
                # Koniec chunked stream
                self._chunk_buf = b""
                break

            data_start = nl_pos + 2
            data_end = data_start + chunk_size

            if data_end > len(self._chunk_buf):
                # Niepelny chunk - czekaj na wiecej danych
                break

            # Wyciagnij dane chunka
            result += self._chunk_buf[data_start:data_end]

            # Pomin chunk data + trailing \r\n
            remaining_start = data_end
            if remaining_start + 2 <= len(self._chunk_buf) and self._chunk_buf[remaining_start:remaining_start + 2] == b"\r\n":
                remaining_start += 2

            self._chunk_buf = self._chunk_buf[remaining_start:]

        return result

    def _disconnect(self):
        self._connected = False
        self._chunked = False
        self._chunk_buf = b""
        with self._lock:
            self._stats['connected'] = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
