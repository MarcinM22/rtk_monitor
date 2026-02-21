"""
coordinates.py - Konwersja wspolrzednych
WGS84 (EPSG:4326) -> PL-2000 strefa 6 (EPSG:2177) + PL-EVRF2007-NH

PL-2000 strefa 6: poludnik osiowy 18°E, skala 0.999923
Konwencja polska: X = northing, Y = easting (z prefiksem strefy 6XXXXXX)

Wysokosc: h_elipsoidalna (z GPS) -> H_normalna (EVRF2007-NH)
  H = h - N   (N = odstep geoidy)
"""

import logging

logger = logging.getLogger(__name__)

# Proba importu pyproj
try:
    from pyproj import Transformer, CRS
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    logger.error("pyproj nie jest zainstalowany! pip install pyproj")


class CoordinateConverter:
    """Konwerter WGS84 -> PL-2000/6 + EVRF2007-NH."""

    def __init__(self):
        self._t_pl2000 = None
        self._t_vertical = None
        self._vert_method = "none"
        self._vert_lonlat = False  # True jesli pipeline (lon,lat), False jesli CRS (lat,lon)

        if not HAS_PYPROJ:
            logger.error("Brak pyproj - konwersja niedostepna")
            return

        # === PL-2000 strefa 6 (EPSG:2177) ===
        try:
            self._t_pl2000 = Transformer.from_crs(
                "EPSG:4326", "EPSG:2177", always_xy=False
            )
            logger.info("PL-2000/6: OK (EPSG:2177)")
        except Exception as e:
            logger.error("Blad inicjalizacji PL-2000: %s", e)

        # === Wysokosc EVRF2007-NH ===
        # Proba 1: pipeline vgridshift z polska siatka geoidy GUGiK
        for grid in ['pl_gugik_geoid2021-PL-EVRF2007-NH.tif',
                      'pl_gugik_geoid2011-PL-EVRF2007-NH.tif']:
            if self._vert_method != "none":
                break
            try:
                pipeline = '+proj=vgridshift +grids=%s' % grid
                t = Transformer.from_pipeline(pipeline)
                # Test: lon, lat, h (pipeline uzywa lon,lat nie lat,lon)
                _, _, h_test = t.transform(19.0, 50.0, 300.0)
                if abs(h_test - 300.0) > 1.0:
                    self._t_vertical = t
                    self._vert_method = "EVRF2007-grid"
                    self._vert_lonlat = True  # pipeline: lon,lat
                    logger.info("Wysokosc: EVRF2007-NH (siatka %s)", grid)
            except Exception:
                pass

        # Proba 2: CRS compound
        if self._vert_method == "none":
            try:
                t = Transformer.from_crs("EPSG:4979", "EPSG:4326+5621", always_xy=False)
                _, _, h_test = t.transform(50.0, 19.0, 300.0)
                if abs(h_test - 300.0) > 1.0:
                    self._t_vertical = t
                    self._vert_method = "EVRF2007-CRS"
                    self._vert_lonlat = False  # CRS: lat,lon
                    logger.info("Wysokosc: EVRF2007-NH (CRS compound)")
            except Exception:
                pass

        # Proba 3: EGM2008
        if self._vert_method == "none":
            try:
                t = Transformer.from_crs("EPSG:4979", "EPSG:3855", always_xy=False)
                _, _, h_test = t.transform(50.0, 19.0, 300.0)
                if abs(h_test - 300.0) > 1.0:
                    self._t_vertical = t
                    self._vert_method = "EGM2008"
                    self._vert_lonlat = False
                    logger.info("Wysokosc: EGM2008 (przyblizenie)")
            except Exception:
                pass

        # Fallback: przyblizenie regionalne
        if self._vert_method == "none":
            self._vert_method = "approx"
            logger.warning(
                "Wysokosc: przyblizenie regionalne (~0.5-1m). "
                "Zainstaluj siatke: projsync --file pl_gugik_geoid2021-PL-EVRF2007-NH.tif"
            )

    @property
    def available(self):
        return self._t_pl2000 is not None

    @property
    def height_method(self):
        return self._vert_method

    def wgs84_to_pl2000(self, lat, lon):
        """
        WGS84 (lat, lon) -> PL-2000 strefa 6 (X, Y).
        X = northing (5XXXXXX)
        Y = easting  (6XXXXXX)
        Zwraca (X, Y) lub (None, None) jesli blad.
        """
        if not self._t_pl2000:
            return None, None
        try:
            x, y = self._t_pl2000.transform(lat, lon)
            return x, y
        except Exception as e:
            logger.error("Blad konwersji PL-2000: %s", e)
            return None, None

    def ellipsoidal_to_normal(self, lat, lon, h_ell):
        """
        Wysokosc elipsoidalna (z GPS) -> normalna (EVRF2007-NH).
        H = h - N (N = odstep geoidy)
        Zwraca H_normal lub None.
        """
        if h_ell is None:
            return None

        if self._t_vertical and self._vert_method not in ("approx", "none"):
            try:
                if self._vert_lonlat:
                    # Pipeline vgridshift: lon, lat, h
                    _, _, h_normal = self._t_vertical.transform(lon, lat, h_ell)
                else:
                    # CRS Transformer: lat, lon, h
                    _, _, h_normal = self._t_vertical.transform(lat, lon, h_ell)
                return h_normal
            except Exception as e:
                logger.debug("Blad transformacji wysokosci: %s", e)

        # Fallback: przyblizenie regionalne
        # Odstep geoidy dla Polski poludniowej (49-51°N, 18-20°E)
        # EGM2008: ok 39-42 m w tym regionie
        N_approx = self._approximate_geoid(lat, lon)
        return h_ell - N_approx

    def _approximate_geoid(self, lat, lon):
        """
        Przyblizone N geoidy dla Polski.
        Bazuje na modelu liniowym dopasowanym do EGM2008.
        Dokladnosc ~0.5-1.0 m. Uzyj pelnej siatki dla lepszych wynikow.
        """
        # Wspolczynniki dopasowane do Polski (49-55°N, 14-24°E)
        # N ~ 29.0 + 1.6*(lat-52) + 0.4*(lon-19) [przyblizone]
        N = 29.0 + 1.6 * (lat - 52.0) + 0.4 * (lon - 19.0)
        return N

    def convert_point(self, lat, lon, h_ell):
        """
        Pelna konwersja: WGS84 -> PL-2000/6 + EVRF2007-NH.
        Zwraca dict z X, Y, H i metadanymi.
        """
        x, y = self.wgs84_to_pl2000(lat, lon)
        h_normal = self.ellipsoidal_to_normal(lat, lon, h_ell)

        return {
            'x_pl2000': x,
            'y_pl2000': y,
            'h_normal': h_normal,
            'h_ellipsoidal': h_ell,
            'lat_wgs84': lat,
            'lon_wgs84': lon,
            'height_method': self._vert_method,
            'valid': x is not None and y is not None,
        }
