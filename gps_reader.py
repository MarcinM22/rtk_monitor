#!/usr/bin/env python3
"""
GPS Reader - czyta i parsuje dane NMEA z modułu LC29H RTK HAT
"""

import serial
import pynmea2
import threading
import time
from typing import Dict, Optional


class GPSReader:
    def __init__(self, port: str = '/dev/ttyAMA0', baudrate: int = 115200):
        """
        Inicjalizacja czytnika GPS
        
        Args:
            port: Port szeregowy (domyślnie /dev/ttyAMA0 dla RPi)
            baudrate: Prędkość transmisji (115200 dla LC29H)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Dane GPS
        self.data = {
            'latitude': 0.0,
            'longitude': 0.0,
            'altitude': 0.0,
            'fix_type': 'No Fix',
            'fix_quality': 0,
            'satellites': 0,
            'satellites_visible': 0,
            'hdop': 99.9,
            'pdop': 99.9,
            'vdop': 99.9,
            'speed': 0.0,
            'course': 0.0,
            'rtk_age': None,  # None = brak korekt RTK
            'rtk_status': 'N/A',
            'timestamp': '',
            'last_update': time.time()
        }
        
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """Nawiązuje połączenie z portem szeregowym"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            print(f"✓ Połączono z {self.port} @ {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"✗ Błąd połączenia z {self.port}: {e}")
            return False
    
    def start(self):
        """Rozpoczyna wątek czytania danych GPS"""
        if not self.connect():
            return False
            
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        print("✓ Wątek GPS uruchomiony")
        return True
    
    def stop(self):
        """Zatrzymuje czytanie danych"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print("✓ GPS zatrzymany")
    
    def _read_loop(self):
        """Główna pętla czytania danych z portu szeregowego"""
        while self.running:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('ascii', errors='ignore').strip()
                    
                    if line.startswith('$'):
                        self._parse_nmea(line)
                        
            except Exception as e:
                print(f"Błąd czytania: {e}")
                time.sleep(0.1)
    
    def _parse_nmea(self, sentence: str):
        """Parsuje zdanie NMEA"""
        try:
            msg = pynmea2.parse(sentence)
            
            with self.lock:
                # GGA - Fix data
                if isinstance(msg, pynmea2.GGA):
                    self.data['latitude'] = msg.latitude if msg.latitude else 0.0
                    self.data['longitude'] = msg.longitude if msg.longitude else 0.0
                    self.data['altitude'] = float(msg.altitude) if msg.altitude else 0.0
                    self.data['satellites'] = int(msg.num_sats) if msg.num_sats else 0
                    self.data['hdop'] = float(msg.horizontal_dil) if msg.horizontal_dil else 99.9
                    self.data['timestamp'] = str(msg.timestamp) if msg.timestamp else ''
                    
                    # Fix quality: 0=invalid, 1=GPS, 2=DGPS, 4=RTK fixed, 5=RTK float
                    fix_quality = int(msg.gps_qual) if msg.gps_qual else 0
                    self.data['fix_quality'] = fix_quality
                    
                    fix_types = {
                        0: 'No Fix',
                        1: 'GPS Fix',
                        2: 'DGPS Fix',
                        4: 'RTK Fixed',
                        5: 'RTK Float',
                        6: 'Estimated'
                    }
                    self.data['fix_type'] = fix_types.get(fix_quality, f'Unknown ({fix_quality})')
                    
                    # Debug: Pokaż raw GGA co 5 sekund
                    import random
                    if random.random() < 0.2:  # ~20% szans = co ~5 sekund przy 1Hz
                        age_str = f"'{msg.age_gps_data}'" if msg.age_gps_data else "PUSTE"
                        print(f"🔍 GGA: qual={fix_quality}, sats={msg.num_sats}, age={age_str}")
                    
                    # Wiek danych różnicowych
                    if msg.age_gps_data:
                        self.data['rtk_age'] = float(msg.age_gps_data)
                    else:
                        self.data['rtk_age'] = None  # None zamiast 0 = brak korekt
                    
                # GSA - DOP and active satellites
                elif isinstance(msg, pynmea2.GSA):
                    # Mode: 1=no fix, 2=2D, 3=3D
                    if msg.mode_fix_type:
                        mode = int(msg.mode_fix_type)
                        if self.data['fix_quality'] == 0 or self.data['fix_quality'] == 1:
                            if mode == 1:
                                self.data['fix_type'] = 'No Fix'
                            elif mode == 2:
                                self.data['fix_type'] = '2D Fix'
                            elif mode == 3:
                                self.data['fix_type'] = '3D Fix'
                    
                    self.data['pdop'] = float(msg.pdop) if msg.pdop else 99.9
                    self.data['hdop'] = float(msg.hdop) if msg.hdop else 99.9
                    self.data['vdop'] = float(msg.vdop) if msg.vdop else 99.9
                
                # GSV - Satellites in view
                elif isinstance(msg, pynmea2.GSV):
                    if msg.num_sv_in_view:
                        self.data['satellites_visible'] = int(msg.num_sv_in_view)
                
                # RMC - Recommended minimum
                elif isinstance(msg, pynmea2.RMC):
                    if msg.spd_over_grnd:
                        self.data['speed'] = float(msg.spd_over_grnd) * 1.852  # knots to km/h
                    if msg.true_course:
                        self.data['course'] = float(msg.true_course)
                
                self.data['last_update'] = time.time()
                
        except pynmea2.ParseError:
            pass  # Ignoruj nieprawidłowe zdania
        except Exception as e:
            print(f"Błąd parsowania: {e}")
    
    def get_data(self) -> Dict:
        """Zwraca aktualne dane GPS (thread-safe)"""
        with self.lock:
            return self.data.copy()
    
    def is_data_fresh(self, max_age: float = 5.0) -> bool:
        """Sprawdza czy dane są aktualne (odebrane w ciągu max_age sekund)"""
        return (time.time() - self.data['last_update']) < max_age
    
    def write_rtcm(self, data: bytes) -> bool:
        """
        Zapisuje dane RTCM do GPS (dla korekt RTK)
        Thread-safe - może być wywoływane z innego wątku
        """
        try:
            if self.serial_conn and self.serial_conn.is_open:
                # Debug: pokaż pierwsze 4 bajty i sprawdź sygnaturę RTCM
                if len(data) >= 4:
                    hex_preview = ' '.join(f'{b:02X}' for b in data[:4])
                    
                    # Sprawdź czy to prawidłowe RTCM (D3 00 XX XX)
                    if data[0] == 0xD3 and data[1] == 0x00:
                        status = "✅ RTCM"
                    else:
                        status = "❌ NIE-RTCM"
                    
                    print(f"📤 {status} → GPS: {len(data)} bajtów [{hex_preview}...]")
                else:
                    print(f"📤 RTCM → GPS: {len(data)} bajtów (za krótkie)")
                
                self.serial_conn.write(data)
                return True
            return False
        except Exception as e:
            print(f"✗ Błąd zapisu RTCM: {e}")
            return False
