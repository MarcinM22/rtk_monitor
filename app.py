#!/usr/bin/env python3
"""
RTK Monitor - Aplikacja webowa do monitorowania GPS/RTK
Backend Flask + WebSocket
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import os
from gps_reader import GPSReader
from ntrip_client import NTRIPClient

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rtk-monitor-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Globalne instancje
gps = None
ntrip = None


def find_uart_port():
    """Automatyczne wykrywanie portu UART"""
    # Lista portów do sprawdzenia (w kolejności preferencji)
    possible_ports = [
        '/dev/ttyAMA0',  # Raspberry Pi 3/4 (główny)
        '/dev/serial0',  # Symlink do głównego UART
        '/dev/ttyS0',    # Alternatywny UART
        '/dev/serial1',  # Alternatywny symlink
        '/dev/ttyUSB0'   # USB adapter (rzadko)
    ]
    
    for port in possible_ports:
        if os.path.exists(port):
            return port
    
    return None


@app.route('/')
def index():
    """Strona główna aplikacji"""
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    """Obsługa połączenia WebSocket"""
    print(f'✓ Klient podłączony')
    emit('status', {'message': 'Połączono z serwerem RTK Monitor'})


@socketio.on('disconnect')
def handle_disconnect():
    """Obsługa rozłączenia WebSocket"""
    print(f'✗ Klient rozłączony')


@socketio.on('request_data')
def handle_request_data():
    """Wysyła aktualne dane GPS do klienta"""
    if gps and gps.is_data_fresh():
        data = gps.get_data()
        emit('gps_data', data)
    else:
        emit('gps_data', {
            'fix_type': 'Brak danych',
            'satellites': 0,
            'error': 'Brak świeżych danych GPS'
        })


def background_task():
    """Zadanie w tle - wysyła dane GPS co 1 sekundę"""
    while True:
        if gps and gps.is_data_fresh():
            data = gps.get_data()
            socketio.emit('gps_data', data)
        else:
            socketio.emit('gps_data', {
                'fix_type': 'Brak danych',
                'satellites': 0,
                'error': 'Moduł GPS nie odpowiada'
            })
        
        socketio.sleep(1)


if __name__ == '__main__':
    print("=" * 60)
    print("RTK Monitor - Aplikacja GPS/RTK dla Raspberry Pi")
    print("=" * 60)
    
    # Konfiguracja NTRIP (opcjonalna - ustaw aby włączyć RTK)
    NTRIP_CONFIG = {
        'enabled': False,  # Zmień na True aby włączyć RTK
        'host': 'system.asgeupos.pl',
        'port': 8086,
        'mountpoint': 'RTK4G_MULTI_RTCM32',
        'username': 'TWOJ_LOGIN',  # Ustaw swój login z ASG-EUPOS
        'password': 'TWOJE_HASLO',  # Ustaw swoje hasło
        'lat': 49.8167,  # Twoja pozycja (przybliżona)
        'lon': 18.7236,
        'debug': False  # True = pokaż szczegóły połączenia NTRIP
    }
    
    # Wykryj dostępny port UART
    uart_port = find_uart_port()
    
    if not uart_port:
        print("\n❌ BŁĄD: Nie znaleziono portu UART!")
        print("\n🔧 Rozwiązanie:")
        print("1. Sprawdź konfigurację UART:")
        print("   grep 'enable_uart' /boot/firmware/config.txt")
        print("   (powinno być: enable_uart=1)")
        print()
        print("2. Jeśli brak 'enable_uart=1', dodaj i zrestartuj:")
        print("   sudo nano /boot/firmware/config.txt")
        print("   # Dodaj na końcu: enable_uart=1")
        print("   sudo reboot")
        print()
        print("3. Sprawdź dostępne porty:")
        print("   python3 find_uart.py")
        print()
        print("4. Sprawdź czy moduł LC29H jest poprawnie zamontowany")
        print()
        exit(1)
    
    print(f"\n✓ Wykryto port UART: {uart_port}")
    
    # Inicjalizacja GPS Reader
    gps = GPSReader(port=uart_port, baudrate=115200)
    
    if gps.start():
        print("\n✓ GPS Reader uruchomiony pomyślnie")
        print("\n📡 Czekam na dane GPS...")
        
        # Inicjalizacja NTRIP Client (jeśli włączony)
        if NTRIP_CONFIG.get('enabled') and NTRIP_CONFIG['username'] != 'TWOJ_LOGIN':
            print("\n" + "=" * 60)
            print("🛰️  Uruchamianie NTRIP Client (RTK)...")
            print("=" * 60)
            
            # Utwórz NTRIP Client z callback do GPS Reader
            ntrip = NTRIPClient(
                host=NTRIP_CONFIG['host'],
                port=NTRIP_CONFIG['port'],
                mountpoint=NTRIP_CONFIG['mountpoint'],
                username=NTRIP_CONFIG['username'],
                password=NTRIP_CONFIG['password'],
                lat=NTRIP_CONFIG['lat'],
                lon=NTRIP_CONFIG['lon'],
                debug=NTRIP_CONFIG['debug'],
                write_callback=gps.write_rtcm  # Współdzielone połączenie szeregowe!
            )
            
            if ntrip.start():
                print("✓ NTRIP Client uruchomiony")
                print("💡 GPS będzie odbierał korekcje RTK")
                print("💡 Oczekuj RTK Fixed w ciągu 2-5 minut")
            else:
                print("✗ Nie można uruchomić NTRIP Client")
                print("⚠️  Aplikacja działa bez RTK (tylko GPS)")
        elif NTRIP_CONFIG.get('enabled'):
            print("\n⚠️  NTRIP: Nie skonfigurowano loginu/hasła")
            print("   Edytuj app.py, sekcję NTRIP_CONFIG i ustaw:")
            print("   'enabled': True,")
            print("   'username': 'twoj_email@example.com',")
            print("   'password': 'twoje_haslo',")
        
        # Uruchom zadanie w tle
        socketio.start_background_task(background_task)
        
        print("\n🌐 Aplikacja dostępna pod adresem:")
        print("   http://localhost:5000")
        print("   http://<IP_RASPBERRY_PI>:5000")
        print("\n💡 Użyj CTRL+C aby zatrzymać\n")
        
        try:
            # Uruchom serwer Flask
            socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        except KeyboardInterrupt:
            print("\n\n⏹  Zatrzymywanie aplikacji...")
        finally:
            if ntrip:
                ntrip.stop()
            gps.stop()
            print("✓ Aplikacja zatrzymana")
    else:
        print("\n✗ Nie można uruchomić GPS Reader")
        print(f"Sprawdź połączenie z modułem LC29H na porcie {uart_port}")
