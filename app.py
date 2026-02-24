"""
app.py - RTK Monitor Backend
Flask z zintegrowanym klientem NTRIP. Komunikacja: HTTP polling 1 Hz.
Jeden proces: GPS + NTRIP + Web UI.
"""

import os
import sys
import json
import signal
import logging

from flask import Flask, render_template, request, jsonify

from gps_reader import GPSReader
from ntrip_client import NTRIPClient, build_mountpoint
from surveyor import Surveyor

# --- Logowanie ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Konfiguracja ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

DEFAULT_NTRIP = {
    'host': 'system.asgeupos.pl',
    'port': 8086,
    'mountpoint': 'RTK4G_MULTI_RTCM32',
    'station': 'AUTO',
    'username': '',
    'password': '',
    'send_gga': True,
    'gga_interval': 10,
    'enabled': False,
}


def load_config():
    """Wczytaj konfiguracje z pliku."""
    cfg = {
        'gps_port': None,
        'gps_baudrate': 115200,
        'ntrip': dict(DEFAULT_NTRIP),
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            if 'ntrip' in saved:
                cfg['ntrip'].update(saved['ntrip'])
            if 'gps_port' in saved:
                cfg['gps_port'] = saved['gps_port']
            if 'gps_baudrate' in saved:
                cfg['gps_baudrate'] = saved['gps_baudrate']
        except Exception as e:
            logger.warning("Blad wczytywania config.json: %s", e)
    return cfg


def save_config(cfg):
    """Zapisz konfiguracje do pliku."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Blad zapisu config.json: %s", e)


# --- Inicjalizacja ---
config = load_config()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rtk-monitor-secret-key-change-me'

gps = GPSReader(
    port=config.get('gps_port'),
    baudrate=config.get('gps_baudrate', 115200)
)

ntrip = NTRIPClient(gps, config.get('ntrip', {}))

surveyor = Surveyor(gps)

# --- Stacje referencyjne ASG-EUPOS ---
STATIONS = {
    'AUTO': 'Automatycznie najblizszaja',
    'BIAL': 'Bialystok',
    'BYDG': 'Bydgoszcz',
    'CZEL': 'Czestochowa',
    'ELBL': 'Elblag',
    'GDNS': 'Gdansk',
    'GLOG': 'Glogow',
    'GNIE': 'Gniezno',
    'GORZ': 'Gorzow Wlkp.',
    'JEDR': 'Jedrzejow',
    'KALI': 'Kalisz',
    'KATO': 'Katowice',
    'KIEL': 'Kielce',
    'KLOB': 'Klobuck',
    'KOSZ': 'Koszalin',
    'KRAK': 'Krakow',
    'KROS': 'Krosno',
    'LEGN': 'Legnica',
    'LELO': 'Lezajsk',
    'LODZ': 'Lodz',
    'LUBL': 'Lublin',
    'OLSZ': 'Olsztyn',
    'OPOL': 'Opole',
    'OSTA': 'Ostroleka',
    'POZN': 'Poznan',
    'PRZM': 'Przemysl',
    'RADC': 'Radom',
    'REDZ': 'Redzikowa',
    'RZEP': 'Rzeszow',
    'SIED': 'Siedlce',
    'SKIE': 'Skierniewice',
    'SOCH': 'Sochaczew',
    'SWIE': 'Swinoujscie',
    'SZCZ': 'Szczecin',
    'TARN': 'Tarnow',
    'TORU': 'Torun',
    'WALA': 'Walbrzych',
    'WARZ': 'Warszawa',
    'WLOD': 'Wlodawa',
    'WROC': 'Wroclaw',
    'ZIEL': 'Zielona Gora',
}


# Stan wytyczania
stakeout_target = {
    'active': False,
    'name': None,
    'x': None,
    'y': None,
    'h': None,
}

# === HTTP Routes ===

def _get_stakeout_data(gps_data):
    """Oblicz dane wytyczania dla biezacej pozycji GPS."""
    if not stakeout_target['active']:
        return {'active': False}
    diff = surveyor.compute_stakeout(
        stakeout_target['x'], stakeout_target['y'], stakeout_target['h'],
        gps_data
    )
    result = {
        'active': True,
        'name': stakeout_target['name'],
        'target_x': stakeout_target['x'],
        'target_y': stakeout_target['y'],
        'target_h': stakeout_target['h'],
    }
    if diff:
        result.update(diff)
    return result

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Prosty endpoint statusu (polling fallback)."""
    gps_data = gps.get_data()
    ntrip_stats = ntrip.get_stats()
    fq = gps_data.get('fix_quality', 0)
    fix_labels = {
        0: 'No Fix', 1: 'GPS Fix', 2: 'DGPS Fix',
        3: 'PPS Fix', 4: 'RTK Fixed', 5: 'RTK Float', 6: 'Estymacja',
    }
    return jsonify({
        'fix_quality': fq,
        'fix_label': fix_labels.get(fq, 'Typ %d' % fq),
        'latitude': gps_data.get('latitude'),
        'longitude': gps_data.get('longitude'),
        'altitude': gps_data.get('altitude'),
        'altitude_ellipsoidal': gps_data.get('altitude_ellipsoidal'),
        'geo_sep': gps_data.get('geo_sep'),
        'satellites_used': gps_data.get('satellites_used', 0),
        'satellites_visible': gps_data.get('satellites_visible', 0),
        'hdop': gps_data.get('hdop'),
        'pdop': gps_data.get('pdop'),
        'vdop': gps_data.get('vdop'),
        'speed_kmh': gps_data.get('speed_kmh'),
        'course': gps_data.get('course'),
        'timestamp': gps_data.get('timestamp'),
        'date': gps_data.get('date'),
        'diff_age': gps_data.get('diff_age'),
        'ntrip_connected': ntrip_stats.get('connected', False),
        'ntrip_bytes': ntrip_stats.get('bytes_received', 0),
        'ntrip_bytes_written': ntrip_stats.get('rtcm_bytes_sent', 0),
        'ntrip_mountpoint': ntrip_stats.get('mountpoint'),
        'ntrip_error': ntrip_stats.get('error'),
        'measurement': surveyor.get_measurement_status(),
        'stakeout': _get_stakeout_data(gps_data),
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Pobierz aktualna konfiguracje NTRIP."""
    return jsonify({
        'ntrip': {
            'host': config['ntrip']['host'],
            'port': config['ntrip']['port'],
            'station': config['ntrip'].get('station', 'AUTO'),
            'username': config['ntrip']['username'],
            'password': '***' if config['ntrip']['password'] else '',
            'enabled': config['ntrip'].get('enabled', False),
            'mountpoint': config['ntrip']['mountpoint'],
        },
        'gps_port': gps.port,
        'stations': STATIONS,
    })


@app.route('/api/ntrip', methods=['POST'])
def update_ntrip():
    """Aktualizuj konfiguracje NTRIP i restartuj polaczenie."""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Brak danych'}), 400

    nc = config['ntrip']

    if 'host' in data:
        nc['host'] = data['host']
    if 'port' in data:
        nc['port'] = int(data['port'])
    if 'station' in data:
        nc['station'] = data['station']
        nc['mountpoint'] = build_mountpoint(data['station'], nc['port'])
    if 'username' in data:
        nc['username'] = data['username']
    if 'password' in data and data['password'] != '***':
        nc['password'] = data['password']
    if 'enabled' in data:
        nc['enabled'] = bool(data['enabled'])

    save_config(config)

    # Stop poprzedniego polaczenia (raz, nie podwojnie)
    ntrip.stop()

    if nc['enabled']:
        # Tylko aktualizuj config (nie wywoluj configure bo robi stop/start)
        ntrip.config.update(nc)
        ntrip.start()

    return jsonify({
        'status': 'ok',
        'mountpoint': nc['mountpoint'],
        'message': 'Zapisano' + (' i NTRIP uruchomiony' if nc['enabled'] else ''),
    })


@app.route('/api/ntrip/stop', methods=['POST'])
def stop_ntrip():
    """Zatrzymaj NTRIP."""
    config['ntrip']['enabled'] = False
    save_config(config)
    ntrip.stop()
    return jsonify({'status': 'ok', 'message': 'NTRIP zatrzymany'})


# === Pomiary / Projekty ===


@app.route('/api/projects', methods=['GET'])
def list_projects():
    """Lista projektow."""
    return jsonify({
        'projects': surveyor.list_projects(),
        'current': surveyor.get_current_project(),
    })


@app.route('/api/project/create', methods=['POST'])
def create_project():
    """Utworz lub otworz projekt."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'status': 'error', 'message': 'Podaj nazwe projektu'}), 400
    result = surveyor.create_project(data['name'])
    return jsonify(result)


@app.route('/api/points', methods=['GET'])
def list_points():
    """Lista pomierzonych punktow z biezacego projektu."""
    return jsonify({'points': surveyor.get_project_points()})


@app.route('/api/measure/start', methods=['POST'])
def start_measurement():
    """Rozpocznij pomiar punktu."""
    data = request.get_json()
    if not data or not data.get('point_name'):
        return jsonify({'status': 'error', 'message': 'Podaj nazwe punktu'}), 400
    result = surveyor.start_measurement(
        point_name=data['point_name'],
        required_samples=data.get('samples', 10),
    )
    return jsonify(result)


@app.route('/api/measure/cancel', methods=['POST'])
def cancel_measurement():
    """Anuluj biezacy pomiar."""
    result = surveyor.cancel_measurement()
    return jsonify(result)


@app.route('/api/measure/status', methods=['GET'])
def measurement_status():
    """Status biezacego pomiaru."""
    return jsonify(surveyor.get_measurement_status())


# === Wytyczanie ===

@app.route('/api/stakeout/files', methods=['GET'])
def stakeout_files():
    """Lista plikow do wytyczenia."""
    return jsonify({'files': surveyor.list_stakeout_files()})


@app.route('/api/stakeout/file/<filename>', methods=['GET'])
def stakeout_file_points(filename):
    """Punkty z pliku wytyczenia."""
    points = surveyor.load_stakeout_file(filename)
    return jsonify({'points': points, 'filename': filename})


@app.route('/api/stakeout/start', methods=['POST'])
def stakeout_start():
    """Ustaw punkt docelowy wytyczania."""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Brak danych'}), 400
    try:
        stakeout_target['active'] = True
        stakeout_target['name'] = data.get('name', '?')
        stakeout_target['x'] = float(data['x'])
        stakeout_target['y'] = float(data['y'])
        stakeout_target['h'] = float(data['h']) if data.get('h') not in (None, '', 'null') else None
        return jsonify({'status': 'ok', 'message': 'Wytyczanie: %s' % stakeout_target['name']})
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'status': 'error', 'message': 'Nieprawidlowe dane: %s' % e}), 400


@app.route('/api/stakeout/stop', methods=['POST'])
def stakeout_stop():
    """Zatrzymaj wytyczanie."""
    stakeout_target['active'] = False
    stakeout_target['name'] = None
    return jsonify({'status': 'ok'})


# === Main ===

def main():
    print("=" * 60)
    print("  RTK Monitor - Waveshare LC29H(DA) RTK HAT")
    print("=" * 60)
    print()

    # GPS
    if gps.start():
        print("  [OK] GPS: %s @ %d baud" % (gps.port, gps.baudrate))
    else:
        print("  [!!] GPS: nie mozna otworzyc %s" % gps.port)
        print("       RPi 4B -> /dev/ttyS0 | RPi 5 -> /dev/ttyAMA0 | USB -> /dev/ttyUSB0")
        print("       Sprawdz: jumper B na module, UART wlaczony, serial-getty wylaczony")

    # NTRIP
    if config['ntrip'].get('enabled') and config['ntrip'].get('username'):
        ntrip.configure(config['ntrip'])
        if ntrip.start():
            print("  [OK] NTRIP: %s:%d/%s" % (
                config['ntrip']['host'], config['ntrip']['port'], config['ntrip']['mountpoint']))
        else:
            print("  [!!] NTRIP: blad polaczenia")
    else:
        print("  [--] NTRIP: wylaczony (skonfiguruj w przegladarce)")

    # Surveyor
    print("  [OK] Pomiary: PL-2000/6 + %s" % surveyor.converter.height_method)

    # Wyswietl adresy
    local_ip = "???"
    try:
        import socket as sock
        s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print()
    print("  Otworz przegladarke:")
    print("    http://localhost:5000")
    print("    http://%s:5000" % local_ip)
    print()
    print("  CTRL+C = stop")
    print("=" * 60)

    def on_exit(sig, frame):
        print("\nZatrzymywanie...")
        ntrip.stop()
        gps.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


if __name__ == '__main__':
    main()
