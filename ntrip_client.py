#!/usr/bin/env python3
"""
NTRIP Client - do połączenia z ASG-EUPOS
Pobiera korekcje RTK i przekazuje do modułu GPS
"""

import socket
import base64
import threading
import time
import serial
import os
from typing import Optional


def find_uart_port():
    """Automatyczne wykrywanie portu UART"""
    possible_ports = [
        '/dev/ttyAMA0',
        '/dev/serial0',
        '/dev/ttyS0',
        '/dev/serial1',
        '/dev/ttyUSB0'
    ]
    
    for port in possible_ports:
        if os.path.exists(port):
            return port
    
    return None


class NTRIPClient:
    def __init__(self, 
                 host: str,
                 port: int,
                 mountpoint: str,
                 username: str,
                 password: str,
                 lat: float = 52.0,
                 lon: float = 21.0,
                 debug: bool = True,
                 write_callback = None):
        """
        Inicjalizacja klienta NTRIP
        
        Args:
            host: Adres serwera NTRIP (np. 'system.asgeupos.pl')
            port: Port serwera (8086 dla GPS+GLO+GAL+BDS)
            mountpoint: Punkt montowania (np. 'RTK4G_MULTI_RTCM32')
            username: Login ASG-EUPOS
            password: Hasło ASG-EUPOS
            lat: Przybliżona szerokość geograficzna (dla NTRIP)
            lon: Przybliżona długość geograficzna (dla NTRIP)
            debug: Wyświetlaj informacje debugowania
            write_callback: Funkcja do zapisu RTCM (zamiast serial_conn)
        """
        self.host = host
        self.port = port
        self.mountpoint = mountpoint
        self.username = username
        self.password = password
        self.lat = lat
        self.lon = lon
        self.debug = debug
        self.write_callback = write_callback
        
        self.socket: Optional[socket.socket] = None
        self.serial_conn: Optional[serial.Serial] = None  # Używane tylko w standalone mode
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.chunked_mode = False  # Czy serwer używa chunked transfer encoding
        
    def _generate_gga(self) -> str:
        """Generuje zdanie NMEA GGA z podanych współrzędnych"""
        # Konwersja decimal degrees na degrees/minutes
        lat_deg = int(abs(self.lat))
        lat_min = (abs(self.lat) - lat_deg) * 60
        lat_dir = 'N' if self.lat >= 0 else 'S'
        
        lon_deg = int(abs(self.lon))
        lon_min = (abs(self.lon) - lon_deg) * 60
        lon_dir = 'E' if self.lon >= 0 else 'W'
        
        # Format GGA (uproszczony)
        gga = f"$GPGGA,000000.00,{lat_deg:02d}{lat_min:07.4f},{lat_dir},{lon_deg:03d}{lon_min:07.4f},{lon_dir},1,08,1.0,100.0,M,0.0,M,,"
        
        # Oblicz checksum
        checksum = 0
        for char in gga[1:]:  # pomijamy $
            checksum ^= ord(char)
        
        gga_with_checksum = f"{gga}*{checksum:02X}\r\n"
        return gga_with_checksum
    
    def connect(self) -> bool:
        """Nawiązuje połączenie z serwerem NTRIP i GPS"""
        try:
            # Połączenie z serwerem NTRIP
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            
            if self.debug:
                print(f"\n{'='*60}")
                print(f"🔌 Łączenie z {self.host}:{self.port}...")
                print(f"{'='*60}")
                print(f"📍 Mountpoint: {self.mountpoint}")
                print(f"👤 Username: {self.username}")
                print(f"🔑 Password: {'*' * len(self.password)} ({len(self.password)} znaków)")
                print(f"📍 Pozycja: {self.lat:.4f}°N, {self.lon:.4f}°E")
                print(f"{'='*60}\n")
            
            self.socket.connect((self.host, self.port))
            
            # Przygotuj żądanie NTRIP z GGA
            auth = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            
            # Generuj GGA dla RTK4G_MULTI_RTCM32 (wymaga pozycji)
            gga_sentence = self._generate_gga()
            
            # NTRIP 2.0 request z pozycją GGA
            request = (
                f"GET /{self.mountpoint} HTTP/1.1\r\n"
                f"Host: {self.host}\r\n"
                f"Ntrip-Version: Ntrip/2.0\r\n"
                f"User-Agent: NTRIP RTKMonitor/1.0\r\n"
                f"Authorization: Basic {auth}\r\n"
                f"Ntrip-GGA: {gga_sentence.strip()}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            
            if self.debug:
                print("📤 Wysyłane żądanie HTTP:")
                print("-" * 60)
                # Pokazuj request ale zamaskuj hasło w Authorization
                debug_request = request.replace(auth, f"{auth[:8]}...{auth[-4:]}")
                print(debug_request)
                print("-" * 60)
                print()
            
            self.socket.send(request.encode())
            
            # Czytaj odpowiedź
            response = self.socket.recv(4096).decode('utf-8', errors='ignore')
            
            if self.debug:
                print("📥 Odpowiedź serwera:")
                print("-" * 60)
                # Pokaż tylko pierwsze linie (nagłówki)
                response_lines = response.split('\r\n')[:15]
                for line in response_lines:
                    print(line)
                if len(response.split('\r\n')) > 15:
                    print("... (więcej linii)")
                print("-" * 60)
                print()
            
            # Sprawdź odpowiedź
            if 'ICY 200 OK' in response or 'HTTP/1.1 200 OK' in response or 'HTTP/1.0 200 OK' in response:
                print("✓ Połączono z serwerem NTRIP")
                print("✓ Autoryzacja udana")
                print(f"✓ Wybrano mountpoint: {self.mountpoint}")
                
                # Sprawdź czy używa chunked encoding
                if 'Transfer-Encoding: chunked' in response or 'transfer-encoding: chunked' in response:
                    self.chunked_mode = True
                    print("⚠️  Uwaga: Serwer używa chunked transfer encoding")
                    print("   → Włączam dekoder chunked - dane RTCM będą czyszczone")
                else:
                    self.chunked_mode = False
                    print("✓ Serwer wysyła czyste RTCM (bez chunked)")
            elif 'SOURCETABLE 200 OK' in response:
                print("✗ Błąd: Serwer zwrócił SOURCETABLE (listę stacji)")
                print("  Możliwe przyczyny:")
                print("  1. Nieprawidłowy login lub hasło")
                print("  2. Nieprawidłowy mountpoint")
                print("  3. Konto nieaktywne lub wygasłe")
                print()
                print("Sprawdź dane logowania powyżej!")
                return False
            elif '401' in response or 'Unauthorized' in response:
                print("✗ Błąd 401: Nieprawidłowy login lub hasło")
                print("  Sprawdź credentials w konfiguracji!")
                return False
            elif '404' in response:
                print(f"✗ Błąd 404: Mountpoint '{self.mountpoint}' nie istnieje")
                print("  Sprawdź nazwę mountpoint!")
                return False
            else:
                print(f"⚠ Nieoczekiwana odpowiedź serwera:")
                print(response[:500])
                print("\nPróbuję kontynuować...")
            
            # Połączenie z GPS - tylko jeśli nie ma callback (standalone mode)
            if self.write_callback is None:
                # Standalone mode - musimy sami otworzyć port
                uart_port = find_uart_port()
                if not uart_port:
                    print("✗ Błąd: Nie znaleziono portu UART!")
                    return False
                
                self.serial_conn = serial.Serial(
                    port=uart_port,
                    baudrate=115200,
                    timeout=1
                )
                print(f"✓ Połączono z GPS na {uart_port}")
            else:
                # Integrated mode - używamy callback
                print(f"✓ Używam współdzielonego połączenia GPS (integrated mode)")
            
            return True
            
        except Exception as e:
            print(f"✗ Błąd połączenia: {e}")
            return False
    
    def start(self):
        """Rozpoczyna pobieranie i przekazywanie korekt RTK"""
        if not self.connect():
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._rtcm_loop, daemon=True)
        self.thread.start()
        print("✓ NTRIP Client uruchomiony")
        
        return True
    
    def stop(self):
        """Zatrzymuje klienta NTRIP"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2)
        
        if self.socket:
            self.socket.close()
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        
        print("✓ NTRIP Client zatrzymany")
    
    def _read_chunk(self) -> bytes:
        """
        Czyta jeden chunk z HTTP chunked transfer encoding.
        Format: <hex_size>\r\n<data>\r\n
        Zwraca czyste dane (bez headerów).
        """
        try:
            # Czytaj linię z rozmiarem chunku (hex)
            size_line = b''
            while not size_line.endswith(b'\r\n'):
                byte = self.socket.recv(1)
                if not byte:
                    return b''
                size_line += byte
            
            # Parsuj rozmiar z hex (usuń \r\n)
            size_hex = size_line[:-2].decode('ascii').strip()
            
            # Jeśli rozmiar = 0, to koniec chunków
            if size_hex == '0':
                return b''
            
            try:
                chunk_size = int(size_hex, 16)
            except ValueError:
                print(f"✗ Błąd parsowania chunk size: '{size_hex}'")
                return b''
            
            # Czytaj chunk_size bajtów (czyste dane)
            chunk_data = b''
            while len(chunk_data) < chunk_size:
                remaining = chunk_size - len(chunk_data)
                data = self.socket.recv(remaining)
                if not data:
                    break
                chunk_data += data
            
            # Czytaj trailing \r\n po chunku
            trailing = self.socket.recv(2)  # powinno być \r\n
            
            return chunk_data
            
        except Exception as e:
            print(f"✗ Błąd czytania chunku: {e}")
            return b''
    
    def _rtcm_loop(self):
        """Główna pętla odbierania RTCM i wysyłania do GPS"""
        print("📡 Rozpoczęto odbieranie korekt RTK...")
        
        if self.chunked_mode:
            print("🔧 Używam dekodera chunked transfer encoding")
        
        bytes_received = 0
        rtcm_signature_count = 0
        
        while self.running:
            try:
                # Odbierz dane RTCM z serwera
                if self.chunked_mode:
                    # Tryb chunked - czytaj chunk po chunku
                    data = self._read_chunk()
                    if not data:
                        # Chunk size = 0 lub błąd
                        continue
                else:
                    # Tryb normalny - czytaj bezpośrednio
                    data = self.socket.recv(1024)
                
                if not data:
                    print("⚠ Brak danych z serwera NTRIP")
                    break
                
                # Debug: sprawdź czy to jest prawidłowy RTCM (sygnatura D3 00)
                if len(data) >= 2 and data[0] == 0xD3 and data[1] == 0x00:
                    rtcm_signature_count += 1
                    if rtcm_signature_count == 1:
                        print("✅ Wykryto prawidłową sygnaturę RTCM (D3 00)!")
                
                # Wyślij do GPS - przez callback lub serial_conn
                if self.write_callback:
                    # Integrated mode - użyj callback
                    if self.write_callback(data):
                        bytes_received += len(data)
                elif self.serial_conn and self.serial_conn.is_open:
                    # Standalone mode - bezpośredni zapis
                    self.serial_conn.write(data)
                    bytes_received += len(data)
                
                # Log co 10KB
                if bytes_received % 10240 < 1024:
                    print(f"📥 Odebrano korekt: {bytes_received / 1024:.1f} KB")
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Błąd w pętli RTCM: {e}")
                break
        
        print(f"📊 Suma odebranych korekt: {bytes_received / 1024:.1f} KB")
        if rtcm_signature_count > 0:
            print(f"✅ Zweryfikowano {rtcm_signature_count} pakietów RTCM z prawidłową sygnaturą")


def get_nearest_mountpoint(lat: float, lon: float) -> str:
    """
    Zwraca najbliższy mountpoint ASG-EUPOS dla podanych współrzędnych
    
    Przykładowe mountpointy:
    - KATO (Katowice): ~50.2°N, 19.0°E
    - WROC (Wrocław): ~51.1°N, 17.0°E
    - POZN (Poznań): ~52.4°N, 16.9°E
    - LODZ (Łódź): ~51.8°N, 19.5°E
    - WARZ (Warszawa): ~52.2°N, 21.0°E
    - KRAK (Kraków): ~50.1°N, 19.9°E
    - GDNS (Gdańsk): ~54.4°N, 18.6°E
    """
    
    # Prosta heurystyka - użyj Warszawy dla centralnej Polski
    if 51.5 <= lat <= 52.5 and 20.0 <= lon <= 22.0:
        return 'WARZ'
    elif 50.0 <= lat <= 51.0 and 18.5 <= lon <= 20.5:
        return 'KRAK'
    elif 54.0 <= lat <= 55.0 and 18.0 <= lon <= 19.0:
        return 'GDNS'
    else:
        return 'WARZ'  # domyślnie Warszawa


if __name__ == '__main__':
    """
    Przykładowe użycie - uruchom osobno od app.py
    """
    print("=" * 60)
    print("NTRIP Client - ASG-EUPOS")
    print("=" * 60)
    
    # Konfiguracja - WYPEŁNIJ SWOIMI DANYMI
    CONFIG = {
        'host': 'system.asgeupos.pl',      # Adres serwera ASG-EUPOS
        'port': 8086,                       # Port dla GPS+GLO+GAL+BDS
        'mountpoint': 'RTK4G_MULTI_RTCM32', # Automatyczny wybór najbliższej stacji
        'username': 'TWOJ_LOGIN',           # WYMAGANE - login z asgeupos.pl
        'password': 'TWOJE_HASLO',          # WYMAGANE - hasło z asgeupos.pl
        'lat': 49.8167,                     # Twoja szerokość geograficzna
        'lon': 18.7236,                     # Twoja długość geograficzna
        'debug': True                       # Wyświetlaj szczegóły połączenia
    }
    
    print(f"\n📍 Konfiguracja:")
    print(f"   Serwer: {CONFIG['host']}:{CONFIG['port']}")
    print(f"   Mountpoint: {CONFIG['mountpoint']}")
    print(f"   (Auto-wybór najbliższej stacji na podstawie pozycji)")
    
    # Sprawdź czy login i hasło są ustawione
    if CONFIG['username'] == 'TWOJ_LOGIN' or CONFIG['password'] == 'TWOJE_HASLO':
        print("\n" + "=" * 60)
        print("❌ BŁĄD: Nie skonfigurowano loginu i hasła!")
        print("=" * 60)
        print("\n📝 Jak uzyskać dostęp do ASG-EUPOS:")
        print()
        print("1. Wejdź na: http://www.asgeupos.pl")
        print("2. Zarejestruj się (bezpłatne konto)")
        print("3. Po rejestracji otrzymasz:")
        print("   - Login (adres email lub nazwa użytkownika)")
        print("   - Hasło")
        print()
        print("4. Edytuj ten plik:")
        print("   nano ntrip_client.py")
        print()
        print("5. W sekcji CONFIG ustaw:")
        print("   'username': 'twoj_email@example.com',")
        print("   'password': 'twoje_haslo',")
        print()
        print("6. Zapisz (CTRL+O, Enter, CTRL+X) i uruchom ponownie")
        print()
        print("💡 Mountpoint RTK4G_MULTI_RTCM32 automatycznie wybierze")
        print("   najbliższą stację referencyjną na podstawie Twojej pozycji.")
        print()
        print("=" * 60)
        exit(1)
    
    # Automatyczne wykrywanie portu GPS
    print("\n🔍 Wykrywanie portu GPS...")
    uart_port = find_uart_port()
    
    if not uart_port:
        print("\n❌ BŁĄD: Nie znaleziono portu UART!")
        print("\n🔧 Rozwiązanie:")
        print("1. Sprawdź konfigurację UART:")
        print("   grep 'enable_uart' /boot/firmware/config.txt")
        print("   (powinno być: enable_uart=1)")
        print()
        print("2. Jeśli brak, dodaj i zrestartuj:")
        print("   sudo nano /boot/firmware/config.txt")
        print("   # Dodaj: enable_uart=1")
        print("   sudo reboot")
        print()
        print("3. Sprawdź dostępne porty:")
        print("   ls -la /dev/tty* | grep -E '(AMA|S0|serial)'")
        print()
        exit(1)
    
    print(f"✓ Wykryto port GPS: {uart_port}")
    
    # Dodaj port do CONFIG
    CONFIG['gps_port'] = uart_port
    
    client = NTRIPClient(**CONFIG)
    
    if client.start():
        print("\n" + "=" * 60)
        print("✅ NTRIP Client działa poprawnie!")
        print("=" * 60)
        print("\n💡 Co się dzieje:")
        print("   - Pobieranie korekt RTK z ASG-EUPOS")
        print("   - Wysyłanie do GPS przez UART")
        print("   - GPS będzie używał korekt do RTK Fixed")
        print()
        print("📊 Sprawdź aplikację RTK Monitor:")
        print("   http://IP_RASPBERRY:5000")
        print()
        print("   Postęp RTK:")
        print("   GPS Fix → RTK Float (~1-2 min) → RTK Fixed (~2-5 min)")
        print()
        print("🛑 Naciśnij CTRL+C aby zatrzymać")
        print("=" * 60)
        print()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⏹  Zatrzymywanie...")
        finally:
            client.stop()
    else:
        print("\n" + "=" * 60)
        print("✗ Nie można uruchomić klienta NTRIP")
        print("=" * 60)
        print("\n⚠️  Połączenie z ASG-EUPOS działa, ale problem z GPS!")
        print()
        print("🔍 Sprawdź:")
        print("   1. Czy app.py działa (w osobnym terminalu)")
        print("   2. Czy port GPS nie jest zajęty")
        print("   3. Czy moduł LC29H jest podłączony")
        print()
        print("💡 Sekwencja uruchamiania:")
        print("   Terminal 1: python3 app.py")
        print("   Terminal 2: python3 ntrip_client.py")
        print()
        print("📖 Zobacz: FIX_NO_UART.md")
        print("=" * 60)
