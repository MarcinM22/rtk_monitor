"""
surveyor.py - Modul pomiarowy RTK Monitor
Zbiera probki RTK Fixed, usrednia, konwertuje na PL-2000/EVRF2007,
zapisuje do CSV i raportu.

Projekty przechowywane w ~/rtk_projekty (poza aplikacja).
Obsluga wysokosci anteny nad punktem.
Odczyt DXF do podgladu mapy.
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
    """Pojedynszy pomiar punktu (kolekcja probek)."""

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

        if fq < self.min_fix_quality:
            self.rejected += 1
            return False

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

        alts_ell = [s['alt_ell'] for s in self.samples if s.get('alt_ell') is not None]
        avg_alt_ell = sum(alts_ell) / len(alts_ell) if alts_ell else None

        if n > 1:
            std_lat = math.sqrt(sum((s['lat'] - avg_lat) ** 2 for s in self.samples) / (n - 1))
            std_lon = math.sqrt(sum((s['lon'] - avg_lon) ** 2 for s in self.samples) / (n - 1))
            if alts and len(alts) > 1:
                std_alt = math.sqrt(sum((a - avg_alt) ** 2 for a in alts) / (len(alts) - 1))
            else:
                std_alt = None
        else:
            std_lat = std_lon = std_alt = 0.0

        std_lat_m = std_lat * 111000.0
        std_lon_m = std_lon * 111000.0 * math.cos(math.radians(avg_lat))

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
        # Domyslnie ~/rtk_projekty (poza aplikacja, przetrwa reinstalacje)
        self.base_dir = base_dir or os.path.expanduser('~/rtk_projekty')
        self.converter = CoordinateConverter()
        self._current_measurement = None
        self._current_project = None
        self._point_counter = 0
        self._lock = threading.Lock()
        self._collect_thread = None
        self.antenna_height = 0.0  # wys. anteny nad punktem [m]

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

        if not os.path.exists(csv_path):
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([
                    'ID', 'Nazwa',
                    'X_PL2000', 'Y_PL2000', 'H_EVRF2007',
                    'Lat_WGS84', 'Lon_WGS84', 'H_elips',
                    'Wys_anteny', 'Dokl_poziom', 'Dokl_pion'
                ])

        if not os.path.exists(report_path):
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("  RAPORT POMIAROWY\n")
                f.write("  Projekt: %s\n" % name)
                f.write("  Utworzony: %s\n" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                f.write("  Uklad poziomy: PL-2000 strefa 6 (EPSG:2177)\n")
                f.write("  Uklad wysokosciowy: PL-EVRF2007-NH (%s)\n" % self.converter.height_method)
                f.write("  Katalog: %s\n" % project_dir)
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
                min_fix_quality=4,
            )
            self._current_measurement.start()

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

            time.sleep(1)

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
        h_for_conv = avg.get('alt_ellipsoidal') or avg['alt']
        conv = self.converter.convert_point(avg['lat'], avg['lon'], h_for_conv)

        # Odejmij wysokosc anteny od wysokosci normalnej
        h_normal = conv['h_normal']
        if h_normal is not None and self.antenna_height > 0:
            h_normal = h_normal - self.antenna_height

        self._point_counter += 1
        point_id = self._point_counter

        result = {
            'point_id': point_id,
            'point_name': m.point_name,
            'x_pl2000': conv['x_pl2000'],
            'y_pl2000': conv['y_pl2000'],
            'h_normal': h_normal,
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
            'antenna_height': self.antenna_height,
        }

        self._save_to_csv(result)
        self._save_to_report(result, avg)

        logger.info("Pomiar zapisany: #%d '%s' X=%.3f Y=%.3f H=%.3f (ant=%.3f)",
                     point_id, m.point_name,
                     conv['x_pl2000'] or 0, conv['y_pl2000'] or 0,
                     h_normal or 0, self.antenna_height)

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
                    "%.3f" % result['h_normal'] if result['h_normal'] is not None else '',
                    "%.8f" % result['lat_wgs84'] if result['lat_wgs84'] else '',
                    "%.8f" % result['lon_wgs84'] if result['lon_wgs84'] else '',
                    "%.3f" % result['h_ellipsoidal'] if result['h_ellipsoidal'] else '',
                    "%.3f" % result['antenna_height'],
                    "%.4f" % result['std_horizontal_m'] if result['std_horizontal_m'] else '',
                    "%.4f" % result['std_alt'] if result['std_alt'] is not None else '',
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
                if result['antenna_height'] > 0:
                    f.write("  Wys. anteny:   %.3f m\n" % result['antenna_height'])
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
                    if result['antenna_height'] > 0:
                        f.write("  (po odjęciu wys. anteny %.3f m)\n" % result['antenna_height'])
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

    # === Pomierzone punkty ===

    def get_project_points(self):
        """Zwroc liste pomierzonych punktow z biezacego projektu."""
        if not self._current_project:
            return []
        csv_path = self._current_project['csv_path']
        if not os.path.exists(csv_path):
            return []
        points = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                header = next(reader, None)
                if not header:
                    return []
                for row in reader:
                    if len(row) < 5:
                        continue
                    try:
                        pt = {
                            'id': row[0],
                            'name': row[1],
                            'x': float(row[2]) if row[2] else None,
                            'y': float(row[3]) if row[3] else None,
                            'h': float(row[4]) if row[4] else None,
                            'lat': float(row[5]) if len(row) > 5 and row[5] else None,
                            'lon': float(row[6]) if len(row) > 6 and row[6] else None,
                            'h_elips': float(row[7]) if len(row) > 7 and row[7] else None,
                        }
                        # Nowe pola (kompatybilnosc wsteczna)
                        if len(row) > 8 and row[8]:
                            pt['antenna_h'] = float(row[8])
                        if len(row) > 9 and row[9]:
                            pt['acc_h'] = float(row[9])
                        if len(row) > 10 and row[10]:
                            pt['acc_v'] = float(row[10])
                        points.append(pt)
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            logger.error("Blad odczytu CSV: %s", e)
        return points

    # === Wytyczanie ===

    def get_stakeout_dir(self):
        """Zwroc sciezke do katalogu wytyczanie."""
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wytyczenie')
        os.makedirs(d, exist_ok=True)
        return d

    def list_stakeout_files(self):
        """Lista plikow TXT w katalogu wytyczenie/."""
        d = self.get_stakeout_dir()
        files = []
        for f in sorted(os.listdir(d)):
            if f.lower().endswith('.txt'):
                fpath = os.path.join(d, f)
                count = 0
                try:
                    with open(fpath, 'r', encoding='utf-8') as fh:
                        for line in fh:
                            parts = line.strip().split(',')
                            if len(parts) >= 3:
                                count += 1
                except Exception:
                    pass
                files.append({'name': f, 'points': count})
        return files

    def load_stakeout_file(self, filename):
        """Wczytaj punkty z pliku TXT. Format: nazwa,x,y,h"""
        safe = os.path.basename(filename)
        fpath = os.path.join(self.get_stakeout_dir(), safe)
        if not os.path.exists(fpath):
            return []
        points = []
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(',')
                    if len(parts) < 3:
                        continue
                    try:
                        name = parts[0].strip()
                        x = float(parts[1].strip())
                        y = float(parts[2].strip())
                        h = float(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else None
                        points.append({'name': name, 'x': x, 'y': y, 'h': h})
                    except ValueError:
                        continue
        except Exception as e:
            logger.error("Blad odczytu pliku wytyczenia %s: %s", safe, e)
        return points

    def compute_stakeout(self, target_x, target_y, target_h, gps_data):
        """Oblicz roznice do punktu docelowego."""
        lat = gps_data.get('latitude')
        lon = gps_data.get('longitude')
        if lat is None or lon is None:
            return None

        cur_x, cur_y = self.converter.wgs84_to_pl2000(lat, lon)
        if cur_x is None or cur_y is None:
            return None

        h_ell = gps_data.get('altitude_ellipsoidal') or gps_data.get('altitude')
        cur_h = self.converter.ellipsoidal_to_normal(lat, lon, h_ell) if h_ell else None
        # Odejmij wysokosc anteny od aktualnej H
        if cur_h is not None and self.antenna_height > 0:
            cur_h = cur_h - self.antenna_height

        dN = target_x - cur_x
        dE = target_y - cur_y
        dist2d = math.sqrt(dN * dN + dE * dE)

        result = {
            'dN': round(dN, 3),
            'dE': round(dE, 3),
            'dH': None,
            'dist2d': round(dist2d, 3),
            'dist3d': None,
            'cur_x': round(cur_x, 3),
            'cur_y': round(cur_y, 3),
            'cur_h': round(cur_h, 3) if cur_h else None,
        }

        if target_h is not None and cur_h is not None:
            dH = target_h - cur_h
            result['dH'] = round(dH, 3)
            result['dist3d'] = round(math.sqrt(dN * dN + dE * dE + dH * dH), 3)

        return result

    # === DXF ===

    def list_dxf_files(self):
        """Lista plikow DXF w biezacym projekcie."""
        if not self._current_project:
            return []
        project_dir = self._current_project['dir']
        files = []
        try:
            for f in sorted(os.listdir(project_dir)):
                if f.lower().endswith('.dxf'):
                    files.append(f)
        except Exception:
            pass
        return files

    def load_dxf_file(self, filename):
        """Parsuj plik DXF i zwroc elementy geometryczne (linie, polyline).
        Prosty parser ASCII DXF bez zewnetrznych zaleznosci.
        """
        if not self._current_project:
            return {'error': 'Brak projektu', 'entities': []}
        safe = os.path.basename(filename)
        fpath = os.path.join(self._current_project['dir'], safe)
        if not os.path.exists(fpath):
            return {'error': 'Plik nie istnieje', 'entities': []}

        entities = []
        try:
            entities = self._parse_dxf(fpath)
        except Exception as e:
            logger.error("Blad parsowania DXF %s: %s", safe, e)
            return {'error': str(e), 'entities': []}

        return {'filename': safe, 'entities': entities, 'count': len(entities)}

    def _parse_dxf(self, filepath):
        """Parser ASCII DXF - obsluguje formaty R12 (AC1009) i nowsze.

        R12 uzywa POLYLINE + VERTEX + SEQEND (oddzielne encje code-0).
        Nowsze formaty uzywaja LWPOLYLINE (wspolrzedne wewnatrz jednej encji).
        """
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Parsuj grupy kod-wartosc
        groups = []
        i = 0
        while i < len(lines) - 1:
            try:
                code = int(lines[i].strip())
                value = lines[i + 1].strip()
                groups.append((code, value))
            except (ValueError, IndexError):
                pass
            i += 2

        entities = []
        in_entities = False
        idx = 0

        # Stan dla POLYLINE R12 (POLYLINE -> VERTEX* -> SEQEND)
        in_polyline = False
        poly_layer = '0'
        poly_closed = False
        poly_vertices = []

        while idx < len(groups):
            code, value = groups[idx]

            # Szukaj sekcji ENTITIES
            if code == 2 and value == 'ENTITIES':
                in_entities = True
                idx += 1
                continue
            if code == 0 and value == 'ENDSEC':
                # Zamknij otwarta polyline
                if in_polyline and poly_vertices:
                    entities.append({
                        'type': 'polyline',
                        'layer': poly_layer,
                        'points': list(poly_vertices),
                        'closed': poly_closed,
                    })
                    in_polyline = False
                in_entities = False
                idx += 1
                continue
            if code == 0 and value == 'EOF':
                if in_polyline and poly_vertices:
                    entities.append({
                        'type': 'polyline',
                        'layer': poly_layer,
                        'points': list(poly_vertices),
                        'closed': poly_closed,
                    })
                break

            if not in_entities:
                idx += 1
                continue

            # === Entity start (code 0) ===
            if code == 0:
                etype = value
                idx += 1

                # --- SEQEND: koniec POLYLINE R12 ---
                if etype == 'SEQEND':
                    if in_polyline and poly_vertices:
                        entities.append({
                            'type': 'polyline',
                            'layer': poly_layer,
                            'points': list(poly_vertices),
                            'closed': poly_closed,
                        })
                    in_polyline = False
                    poly_vertices = []
                    # Pomin atrybuty SEQEND
                    while idx < len(groups) and groups[idx][0] != 0:
                        idx += 1
                    continue

                # --- VERTEX: wierzcholek POLYLINE R12 ---
                if etype == 'VERTEX':
                    vx = None
                    vy = None
                    while idx < len(groups) and groups[idx][0] != 0:
                        c, v = groups[idx]
                        if c == 10:
                            try: vx = float(v)
                            except ValueError: pass
                        elif c == 20:
                            try: vy = float(v)
                            except ValueError: pass
                        idx += 1
                    if in_polyline and vx is not None and vy is not None:
                        poly_vertices.append((vx, vy))
                    continue

                # --- POLYLINE R12: poczatek sekwencji ---
                if etype == 'POLYLINE':
                    # Zamknij poprzednia jesli otwarta
                    if in_polyline and poly_vertices:
                        entities.append({
                            'type': 'polyline',
                            'layer': poly_layer,
                            'points': list(poly_vertices),
                            'closed': poly_closed,
                        })
                    in_polyline = True
                    poly_layer = '0'
                    poly_closed = False
                    poly_vertices = []
                    while idx < len(groups) and groups[idx][0] != 0:
                        c, v = groups[idx]
                        if c == 8:
                            poly_layer = v
                        elif c == 70:
                            try: poly_closed = bool(int(v) & 1)
                            except ValueError: pass
                        idx += 1
                    continue

                # --- Standardowe encje (nie w trakcie POLYLINE R12) ---
                edata = {}
                layer = '0'
                while idx < len(groups) and groups[idx][0] != 0:
                    c, v = groups[idx]
                    if c == 8:
                        layer = v
                    edata.setdefault(c, []).append(v)
                    idx += 1

                if etype == 'LINE':
                    try:
                        entities.append({
                            'type': 'line',
                            'layer': layer,
                            'x1': float(edata.get(10, ['0'])[0]),
                            'y1': float(edata.get(20, ['0'])[0]),
                            'x2': float(edata.get(11, ['0'])[0]),
                            'y2': float(edata.get(21, ['0'])[0]),
                        })
                    except (ValueError, IndexError):
                        pass

                elif etype == 'LWPOLYLINE':
                    try:
                        xs = [float(v) for v in edata.get(10, [])]
                        ys = [float(v) for v in edata.get(20, [])]
                        closed = int(edata.get(70, ['0'])[0]) & 1
                        if xs and ys and len(xs) == len(ys):
                            entities.append({
                                'type': 'polyline',
                                'layer': layer,
                                'points': list(zip(xs, ys)),
                                'closed': bool(closed),
                            })
                    except (ValueError, IndexError):
                        pass

                elif etype == 'POINT':
                    try:
                        entities.append({
                            'type': 'point',
                            'layer': layer,
                            'x': float(edata.get(10, ['0'])[0]),
                            'y': float(edata.get(20, ['0'])[0]),
                        })
                    except (ValueError, IndexError):
                        pass

                elif etype == 'CIRCLE':
                    try:
                        entities.append({
                            'type': 'circle',
                            'layer': layer,
                            'cx': float(edata.get(10, ['0'])[0]),
                            'cy': float(edata.get(20, ['0'])[0]),
                            'r': float(edata.get(40, ['0'])[0]),
                        })
                    except (ValueError, IndexError):
                        pass

                elif etype == 'ARC':
                    try:
                        entities.append({
                            'type': 'arc',
                            'layer': layer,
                            'cx': float(edata.get(10, ['0'])[0]),
                            'cy': float(edata.get(20, ['0'])[0]),
                            'r': float(edata.get(40, ['0'])[0]),
                            'start_angle': float(edata.get(50, ['0'])[0]),
                            'end_angle': float(edata.get(51, ['360'])[0]),
                        })
                    except (ValueError, IndexError):
                        pass

                elif etype in ('TEXT', 'MTEXT'):
                    try:
                        text_val = edata.get(1, [''])[0]
                        if text_val:
                            entities.append({
                                'type': 'text',
                                'layer': layer,
                                'x': float(edata.get(10, ['0'])[0]),
                                'y': float(edata.get(20, ['0'])[0]),
                                'text': text_val,
                                'height': float(edata.get(40, ['1'])[0]),
                            })
                    except (ValueError, IndexError):
                        pass
            else:
                idx += 1

        return entities

    # === Pomocnicze ===

    def _count_existing_points(self, csv_path):
        """Policz istniejace punkty w CSV."""
        if not os.path.exists(csv_path):
            return 0
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                return max(0, sum(1 for _ in f) - 1)
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
