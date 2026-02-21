"""
surveyor.py - Modul pomiarowy RTK Monitor
Zbiera probki RTK Fixed, usrednia, konwertuje na PL-2000/EVRF2007,
zapisuje do CSV i raportu.
"""

import os
import csv
import math
import time
import threading
import logging
from datetime import datetime

from coordinates import CoordinateConverter

logger = logging.getLogger(__name__)


class Measurement:
    """Pojedynczy pomiar punktu (kolekcja probek)."""

    def __init__(self, point_name, required_samples=10, min_fix_quality=4):
        self.point_name = point_name
        self.required_samples = required_samples
        self.min_fix_quality = min_fix_quality

        self.samples = []
        self.started_at = datetime.now()
        self.finished_at = None
        self.rejected = 0

        self._running = False
        self._done = False
        self._error = None

    @property
    def is_running(self):
        return self._running and not self._done

    @property
    def is_done(self):
        return self._done

    @property
    def progress(self):
        return len(self.samples)

    @property
    def error(self):
        return self._error

    def start(self):
        self._running = True
        self._done = False
        self._error = None
        self.samples = []
        self.rejected = 0
        self.started_at = datetime.now()

    def add_sample(self, gps_data):
        """Dodaj probke. Zwraca True jesli pomiar kompletny."""
        if not self._running or self._done:
            return False

        fq = gps_data.get('fix_quality', 0)
        lat = gps_data.get('latitude')
        lon = gps_data.get('longitude')
        alt = gps_data.get('altitude')

        # Odrzuc probki bez RTK Fixed
        if fq < self.min_fix_quality:
            self.rejected += 1
            return False

        # Odrzuc probki bez pozycji
        if lat is None or lon is None:
            self.rejected += 1
            return False

        self.samples.append({
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'alt_ell': gps_data.get('altitude_ellipsoidal'),
            'fix_quality': fq,
            'hdop': gps_data.get('hdop'),
            'pdop': gps_data.get('pdop'),
            'vdop': gps_data.get('vdop'),
            'satellites': gps_data.get('satellites_used', 0),
            'diff_age': gps_data.get('diff_age'),
            'timestamp': gps_data.get('timestamp'),
        })

        if len(self.samples) >= self.required_samples:
            self._done = True
            self._running = False
            self.finished_at = datetime.now()
            return True

        return False

    def cancel(self):
        self._running = False
        self._done = False
        self._error = "Anulowany"

    def compute_average(self):
        """Oblicz srednia i odchylenie standardowe z probek."""
        if not self.samples:
            return None

        n = len(self.samples)
        avg_lat = sum(s['lat'] for s in self.samples) / n
        avg_lon = sum(s['lon'] for s in self.samples) / n

        alts = [s['alt'] for s in self.samples if s['alt'] is not None]
        avg_alt = sum(alts) / len(alts) if alts else None

        # Wysokosc elipsoidalna (prawdziwa, do konwersji EVRF2007)
        alts_ell = [s['alt_ell'] for s in self.samples if s.get('alt_ell') is not None]
        avg_alt_ell = sum(alts_ell) / len(alts_ell) if alts_ell else None

        # Odchylenie standardowe
        if n > 1:
            std_lat = math.sqrt(sum((s['lat'] - avg_lat) ** 2 for s in self.samples) / (n - 1))
            std_lon = math.sqrt(sum((s['lon'] - avg_lon) ** 2 for s in self.samples) / (n - 1))
            if alts and len(alts) > 1:
                std_alt = math.sqrt(sum((a - avg_alt) ** 2 for a in alts) / (len(alts) - 1))
            else:
                std_alt = None
        else:
            std_lat = std_lon = std_alt = 0.0

        # Srednia std w metrach (przyblizone)
        # 1 stopien lat ~ 111 km, 1 stopien lon ~ 111 km * cos(lat)
        std_lat_m = std_lat * 111000.0
        std_lon_m = std_lon * 111000.0 * math.cos(math.radians(avg_lat))

        # Srednie DOP
        hdops = [s['hdop'] for s in self.samples if s['hdop'] is not None]
        pdops = [s['pdop'] for s in self.samples if s['pdop'] is not None]

        return {
            'lat': avg_lat,
            'lon': avg_lon,
            'alt': avg_alt,
            'alt_ellipsoidal': avg_alt_ell,
            'std_lat': std_lat,
            'std_lon': std_lon,
            'std_alt': std_alt,
            'std_lat_m': std_lat_m,
            'std_lon_m': std_lon_m,
            'std_horizontal_m': math.sqrt(std_lat_m ** 2 + std_lon_m ** 2),
            'samples_count': n,
            'rejected_count': self.rejected,
            'avg_hdop': sum(hdops) / len(hdops) if hdops else None,
            'avg_pdop': sum(pdops) / len(pdops) if pdops else None,
            'started_at': self.started_at.isoformat(),
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'duration_s': (self.finished_at - self.started_at).total_seconds() if self.finished_at else None,
        }


class Surveyor:
    """Menedzer pomiarow i projektow."""

    def __init__(self, gps_reader, base_dir=None):
        self.gps = gps_reader
        self.base_dir = base_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'projekty'
        )
        self.converter = CoordinateConverter()
        self._current_measurement = None
        self._current_project = None
        self._point_counter = 0
        self._lock = threading.Lock()
        self._collect_thread = None

        os.makedirs(self.base_dir, exist_ok=True)
        logger.info("Surveyor: katalog projektow: %s", self.base_dir)
        logger.info("Surveyor: PL-2000 %s, wysokosc: %s",
                     "OK" if self.converter.available else "NIEDOSTEPNA",
                     self.converter.height_method)

    # === Projekty ===

    def create_project(self, name):
        """Utworz nowy projekt (katalog + puste pliki CSV/raport)."""
        safe_name = self._safe_filename(name)
        project_dir = os.path.join(self.base_dir, safe_name)
        os.makedirs(project_dir, exist_ok=True)

        csv_path = os.path.join(project_dir, "wspolrzedne.csv")
        report_path = os.path.join(project_dir, "raport.txt")

        # Utworz CSV z naglowkiem jesli nie istnieje
        if not os.path.exists(csv_path):
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([
                    'ID', 'Nazwa',
                    'X_PL2000', 'Y_PL2000', 'H_EVRF2007',
                    'Lat_WGS84', 'Lon_WGS84', 'H_elips'
                ])

        # Utworz raport z naglowkiem
        if not os.path.exists(report_path):
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("  RAPORT POMIAROWY\n")
                f.write("  Projekt: %s\n" % name)
                f.write("  Utworzony: %s\n" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                f.write("  Uklad poziomy: PL-2000 strefa 6 (EPSG:2177)\n")
                f.write("  Uklad wysokosciowy: PL-EVRF2007-NH (%s)\n" % self.converter.height_method)
                f.write("=" * 70 + "\n\n")

        self._current_project = {
            'name': name,
            'safe_name': safe_name,
            'dir': project_dir,
            'csv_path': csv_path,
            'report_path': report_path,
        }
        self._point_counter = self._count_existing_points(csv_path)

        logger.info("Projekt: %s (%d istniejacych punktow)", name, self._point_counter)
        return {
            'status': 'ok',
            'name': name,
            'dir': safe_name,
            'existing_points': self._point_counter,
        }

    def list_projects(self):
        """Lista istniejacych projektow."""
        projects = []
        if os.path.exists(self.base_dir):
            for d in sorted(os.listdir(self.base_dir)):
                path = os.path.join(self.base_dir, d)
                if os.path.isdir(path):
                    csv_path = os.path.join(path, "wspolrzedne.csv")
                    count = self._count_existing_points(csv_path)
                    projects.append({
                        'name': d,
                        'points': count,
                    })
        return projects

    def get_current_project(self):
        if self._current_project:
            return {
                'name': self._current_project['name'],
                'points': self._point_counter,
            }
        return None

    # === Pomiar ===

    def start_measurement(self, point_name, required_samples=10):
        """Rozpocznij pomiar nowego punktu."""
        with self._lock:
            if self._current_measurement and self._current_measurement.is_running:
                return {'status': 'error', 'message': 'Pomiar juz trwa'}

            if not self._current_project:
                return {'status': 'error', 'message': 'Najpierw wybierz projekt'}

            if not point_name or not point_name.strip():
                return {'status': 'error', 'message': 'Podaj nazwe punktu'}

            self._current_measurement = Measurement(
                point_name=point_name.strip(),
                required_samples=required_samples,
                min_fix_quality=4,  # tylko RTK Fixed
            )
            self._current_measurement.start()

        # Uruchom watek zbierania probek
        self._collect_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._collect_thread.start()

        logger.info("Pomiar: start '%s' (%d probek)", point_name, required_samples)
        return {
            'status': 'ok',
            'message': 'Pomiar rozpoczety',
            'point_name': point_name,
            'required': required_samples,
        }

    def cancel_measurement(self):
        """Anuluj biezacy pomiar."""
        with self._lock:
            if self._current_measurement:
                self._current_measurement.cancel()
                self._current_measurement = None
        return {'status': 'ok', 'message': 'Pomiar anulowany'}

    def get_measurement_status(self):
        """Zwroc status biezacego pomiaru."""
        with self._lock:
            m = self._current_measurement
            if not m:
                return {'active': False}
            return {
                'active': m.is_running,
                'done': m.is_done,
                'point_name': m.point_name,
                'progress': m.progress,
                'required': m.required_samples,
                'rejected': m.rejected,
                'error': m.error,
            }

    def _collect_loop(self):
        """Watek zbierajacy probki GPS do pomiaru."""
        while True:
            with self._lock:
                m = self._current_measurement
                if not m or not m.is_running:
                    break

            gps_data = self.gps.get_data()
            with self._lock:
                done = m.add_sample(gps_data)

            if done:
                self._finalize_measurement()
                break

            time.sleep(1)  # 1 probka na sekunde

    def _finalize_measurement(self):
        """Oblicz wyniki, konwertuj, zapisz do pliku."""
        with self._lock:
            m = self._current_measurement

        if not m or not m.is_done:
            return

        avg = m.compute_average()
        if not avg:
            logger.error("Pomiar: brak danych do usrednienia")
            return

        # Konwersja PL-2000 + EVRF2007
        # Uzyj prawdziwej wysokosci elipsoidalnej (MSL + geo_sep) do konwersji
        h_for_conv = avg.get('alt_ellipsoidal') or avg['alt']
        conv = self.converter.convert_point(avg['lat'], avg['lon'], h_for_conv)

        self._point_counter += 1
        point_id = self._point_counter

        result = {
            'point_id': point_id,
            'point_name': m.point_name,
            'x_pl2000': conv['x_pl2000'],
            'y_pl2000': conv['y_pl2000'],
            'h_normal': conv['h_normal'],
            'lat_wgs84': avg['lat'],
            'lon_wgs84': avg['lon'],
            'h_ellipsoidal': h_for_conv,
            'std_horizontal_m': avg['std_horizontal_m'],
            'std_alt': avg['std_alt'],
            'samples': avg['samples_count'],
            'rejected': avg['rejected_count'],
            'avg_hdop': avg['avg_hdop'],
            'avg_pdop': avg['avg_pdop'],
            'duration_s': avg['duration_s'],
            'height_method': conv['height_method'],
        }

        # Zapisz do CSV
        self._save_to_csv(result)

        # Zapisz do raportu
        self._save_to_report(result, avg)

        logger.info("Pomiar zapisany: #%d '%s' X=%.3f Y=%.3f H=%.3f",
                     point_id, m.point_name,
                     conv['x_pl2000'] or 0, conv['y_pl2000'] or 0,
                     conv['h_normal'] or 0)

    def _save_to_csv(self, result):
        """Dopisz punkt do pliku CSV."""
        if not self._current_project:
            return
        csv_path = self._current_project['csv_path']
        try:
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([
                    result['point_id'],
                    result['point_name'],
                    "%.3f" % result['x_pl2000'] if result['x_pl2000'] else '',
                    "%.3f" % result['y_pl2000'] if result['y_pl2000'] else '',
                    "%.3f" % result['h_normal'] if result['h_normal'] else '',
                    "%.8f" % result['lat_wgs84'] if result['lat_wgs84'] else '',
                    "%.8f" % result['lon_wgs84'] if result['lon_wgs84'] else '',
                    "%.3f" % result['h_ellipsoidal'] if result['h_ellipsoidal'] else '',
                ])
            logger.info("CSV: punkt #%d zapisany do %s", result['point_id'], csv_path)
        except Exception as e:
            logger.error("Blad zapisu CSV: %s", e)

    def _save_to_report(self, result, avg):
        """Dopisz szczegoly pomiaru do raportu."""
        if not self._current_project:
            return
        report_path = self._current_project['report_path']
        try:
            with open(report_path, 'a', encoding='utf-8') as f:
                f.write("-" * 70 + "\n")
                f.write("  Punkt #%d: %s\n" % (result['point_id'], result['point_name']))
                f.write("-" * 70 + "\n")
                f.write("  Czas pomiaru:  %s -> %s\n" % (avg['started_at'], avg['finished_at']))
                f.write("  Czas trwania:  %.1f s\n" % (avg['duration_s'] or 0))
                f.write("  Probki:        %d uzytych / %d odrzuconych\n" % (
                    result['samples'], result['rejected']))
                f.write("\n")
                f.write("  --- Wspolrzedne PL-2000/6 ---\n")
                if result['x_pl2000']:
                    f.write("  X (northing):  %.3f m\n" % result['x_pl2000'])
                    f.write("  Y (easting):   %.3f m\n" % result['y_pl2000'])
                else:
                    f.write("  X, Y:          BLAD KONWERSJI\n")
                f.write("\n")
                f.write("  --- Wysokosc ---\n")
                if result['h_normal'] is not None:
                    f.write("  H normalna:    %.3f m (EVRF2007-NH, metoda: %s)\n" % (
                        result['h_normal'], result['height_method']))
                f.write("  h elipsoid.:   %.3f m (WGS84)\n" % (result['h_ellipsoidal'] or 0))
                f.write("\n")
                f.write("  --- WGS84 ---\n")
                f.write("  Szerokosc:     %.8f\n" % result['lat_wgs84'])
                f.write("  Dlugosc:       %.8f\n" % result['lon_wgs84'])
                f.write("\n")
                f.write("  --- Dokladnosc ---\n")
                f.write("  Std poziom:    %.4f m\n" % (result['std_horizontal_m'] or 0))
                if result['std_alt'] is not None:
                    f.write("  Std wysokosc:  %.4f m\n" % result['std_alt'])
                f.write("  Sr. HDOP:      %.2f\n" % (result['avg_hdop'] or 0))
                f.write("  Sr. PDOP:      %.2f\n" % (result['avg_pdop'] or 0))
                f.write("\n\n")
        except Exception as e:
            logger.error("Blad zapisu raportu: %s", e)

    # === Pomocnicze ===

    def _count_existing_points(self, csv_path):
        """Policz istniejace punkty w CSV."""
        if not os.path.exists(csv_path):
            return 0
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                return max(0, sum(1 for _ in f) - 1)  # minus naglowek
        except Exception:
            return 0

    def _safe_filename(self, name):
        """Zamien nazwe na bezpieczna nazwe katalogu."""
        safe = name.strip()
        for ch in r'<>:"/\|?*':
            safe = safe.replace(ch, '_')
        safe = safe.replace(' ', '_')
        if not safe:
            safe = "projekt_%s" % datetime.now().strftime('%Y%m%d_%H%M%S')
        return safe
