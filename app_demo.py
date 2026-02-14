#!/usr/bin/env python3
"""
RTK Monitor - DEMO MODE
Testowanie aplikacji bez modułu GPS
Generuje symulowane dane GPS/RTK
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import random
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rtk-monitor-demo-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Symulowane dane GPS
class GPSSimulator:
    def __init__(self):
        # Warszawa, centrum
        self.base_lat = 52.2297
        self.base_lon = 21.0122
        self.altitude = 100.0
        
        self.fix_states = [
            'No Fix',
            'GPS Fix',
            '3D Fix',
            'DGPS Fix',
            'RTK Float',
            'RTK Fixed'
        ]
        self.current_fix_index = 0
        self.time_in_state = 0
        
    def get_data(self):
        # Symulacja postępu fix
        self.time_in_state += 1
        
        # Przejście przez stany co 10 sekund
        if self.time_in_state > 10:
            self.current_fix_index = min(
                self.current_fix_index + 1,
                len(self.fix_states) - 1
            )
            self.time_in_state = 0
        
        fix_type = self.fix_states[self.current_fix_index]
        
        # Parametry zależne od typu fix
        if fix_type == 'No Fix':
            satellites = 0
            hdop = 99.9
            speed = 0
        elif fix_type == 'GPS Fix':
            satellites = random.randint(4, 6)
            hdop = random.uniform(3.0, 8.0)
            speed = random.uniform(0, 5)
        elif fix_type == '3D Fix':
            satellites = random.randint(6, 8)
            hdop = random.uniform(2.0, 4.0)
            speed = random.uniform(0, 10)
        elif fix_type == 'DGPS Fix':
            satellites = random.randint(8, 10)
            hdop = random.uniform(1.5, 3.0)
            speed = random.uniform(0, 15)
        elif fix_type == 'RTK Float':
            satellites = random.randint(10, 12)
            hdop = random.uniform(0.8, 1.5)
            speed = random.uniform(0, 20)
        else:  # RTK Fixed
            satellites = random.randint(12, 15)
            hdop = random.uniform(0.5, 0.9)
            speed = random.uniform(0, 25)
        
        # Małe odchylenie pozycji (symulacja ruchu)
        offset = 0.0001
        lat = self.base_lat + random.uniform(-offset, offset)
        lon = self.base_lon + random.uniform(-offset, offset)
        
        # DOP values
        pdop = hdop * 1.2
        vdop = hdop * 0.8
        
        return {
            'latitude': lat,
            'longitude': lon,
            'altitude': self.altitude + random.uniform(-1, 1),
            'fix_type': fix_type,
            'fix_quality': self.current_fix_index,
            'satellites': satellites,
            'satellites_visible': satellites + random.randint(2, 5),
            'hdop': hdop,
            'pdop': pdop,
            'vdop': vdop,
            'speed': speed,
            'course': random.uniform(0, 360),
            'rtk_age': random.uniform(0, 5) if self.current_fix_index >= 4 else 0,
            'timestamp': time.strftime('%H:%M:%S'),
            'last_update': time.time()
        }


simulator = GPSSimulator()


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    print('🎮 Klient podłączony (DEMO MODE)')
    emit('status', {'message': 'Połączono - DEMO MODE (symulowane dane)'})


@socketio.on('disconnect')
def handle_disconnect():
    print('✗ Klient rozłączony')


@socketio.on('request_data')
def handle_request_data():
    data = simulator.get_data()
    emit('gps_data', data)


def background_task():
    """Wysyła symulowane dane GPS co 1 sekundę"""
    while True:
        data = simulator.get_data()
        socketio.emit('gps_data', data, broadcast=True)
        socketio.sleep(1)


if __name__ == '__main__':
    print("=" * 60)
    print("RTK Monitor - DEMO MODE")
    print("Symulacja danych GPS/RTK (bez hardware)")
    print("=" * 60)
    print()
    print("🎮 Tryb demonstracyjny aktywny!")
    print("📡 Generowanie symulowanych danych GPS...")
    print()
    print("Aplikacja symuluje postęp od 'No Fix' do 'RTK Fixed'")
    print("Przejście przez stany trwa ~60 sekund")
    print()
    print("🌐 Aplikacja dostępna pod adresem:")
    print("   http://localhost:5000")
    print()
    print("💡 Użyj CTRL+C aby zatrzymać")
    print()
    
    socketio.start_background_task(background_task)
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n\n⏹  Zatrzymywanie demo...")
    finally:
        print("✓ Demo zatrzymane")
