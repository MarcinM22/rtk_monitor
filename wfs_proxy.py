"""
wfs_proxy.py - Proxy WFS dla RTK Monitor
Pobiera GetCapabilities i GetFeature, parsuje GML na prosty JSON.
Obsluguje WFS 1.0/1.1/2.0 z GML 2/3.

Wspolrzedne zwracane jako [easting, northing] (Y_PL, X_PL w konwencji PL-2000).
"""

import re
import logging
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, urlparse, parse_qs

logger = logging.getLogger(__name__)

# Timeout dla zapytan WFS [s]
WFS_TIMEOUT = 15

# Max features per request
MAX_FEATURES = 5000

# Znane namespace'y GML
GML_NS = [
    'http://www.opengis.net/gml',
    'http://www.opengis.net/gml/3.2',
]

WFS_NS = [
    'http://www.opengis.net/wfs',
    'http://www.opengis.net/wfs/2.0',
]


def _fetch_url(url, timeout=WFS_TIMEOUT):
    """Pobierz URL z timeoutem."""
    try:
        req = Request(url, headers={
            'User-Agent': 'RTKMonitor/1.0',
            'Accept': 'application/xml, text/xml, application/gml+xml, */*',
        })
        resp = urlopen(req, timeout=timeout)
        data = resp.read()
        return data.decode('utf-8', errors='ignore')
    except HTTPError as e:
        logger.error("WFS HTTP %d: %s", e.code, url[:120])
        raise
    except URLError as e:
        logger.error("WFS URL error: %s (%s)", e.reason, url[:120])
        raise
    except Exception as e:
        logger.error("WFS fetch error: %s", e)
        raise


def _build_wfs_url(base_url, params):
    """Zbuduj URL WFS z parametrami, zachowujac istniejace."""
    parsed = urlparse(base_url)
    existing = parse_qs(parsed.query, keep_blank_values=True)

    # Merge - nowe params nadpisuja istniejace (case-insensitive)
    existing_upper = {k.upper(): v for k, v in existing.items()}
    for k, v in params.items():
        existing_upper[k.upper()] = [v] if isinstance(v, str) else v

    # Zbuduj query string
    query_parts = []
    for k, vals in existing_upper.items():
        for v in vals:
            query_parts.append('%s=%s' % (k, v))
    query = '&'.join(query_parts)

    # Odbuduj URL
    base = parsed._replace(query='').geturl()
    return base + '?' + query


def _find_elem(root, local_name, namespaces=None):
    """Znajdz element po nazwie lokalnej (ignorujac namespace)."""
    for elem in root.iter():
        tag = elem.tag
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag == local_name:
            return elem
    return None


def _find_all(root, local_name):
    """Znajdz wszystkie elementy po nazwie lokalnej."""
    results = []
    for elem in root.iter():
        tag = elem.tag
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag == local_name:
            results.append(elem)
    return results


def get_capabilities(wfs_url):
    """Pobierz GetCapabilities i zwroc liste warstw.

    Returns:
        {
            'layers': [{'name': 'xxx', 'title': 'yyy', 'srs': 'EPSG:2177'}, ...],
            'version': '1.1.0',
            'title': 'Serwer WFS',
        }
    """
    url = _build_wfs_url(wfs_url, {
        'SERVICE': 'WFS',
        'REQUEST': 'GetCapabilities',
    })

    logger.info("WFS GetCapabilities: %s", url[:150])
    xml_text = _fetch_url(url)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("WFS: blad parsowania XML: %s", e)
        return {'error': 'Blad parsowania odpowiedzi XML', 'layers': []}

    # Wersja WFS
    version = root.attrib.get('version', '1.1.0')

    # Tytul serwisu
    title_elem = _find_elem(root, 'Title')
    title = title_elem.text if title_elem is not None and title_elem.text else ''

    # Warstwy (FeatureType)
    layers = []
    for ft in _find_all(root, 'FeatureType'):
        name_elem = _find_elem(ft, 'Name')
        title_elem = _find_elem(ft, 'Title')

        if name_elem is None or not name_elem.text:
            continue

        # SRS/CRS
        srs = ''
        for srs_tag in ('DefaultSRS', 'DefaultCRS', 'SRS'):
            srs_elem = _find_elem(ft, srs_tag)
            if srs_elem is not None and srs_elem.text:
                srs = srs_elem.text.strip()
                break

        # Uprość URN do EPSG:XXXX
        if 'EPSG' in srs:
            m = re.search(r'EPSG[:/]+([\d]+)', srs)
            if m:
                srs = 'EPSG:' + m.group(1)

        layers.append({
            'name': name_elem.text.strip(),
            'title': title_elem.text.strip() if title_elem is not None and title_elem.text else name_elem.text.strip(),
            'srs': srs,
        })

    logger.info("WFS: %d warstw, wersja %s", len(layers), version)
    return {
        'layers': layers,
        'version': version,
        'title': title,
    }


def get_features(wfs_url, layer_names, bbox, srs='EPSG:2177', version='1.1.0'):
    """Pobierz features z BBOX.

    Args:
        wfs_url: bazowy URL WFS
        layer_names: lista nazw warstw (lub string z przecinkami)
        bbox: (min_easting, min_northing, max_easting, max_northing) - PL-2000
        srs: uklad odniesienia
        version: wersja WFS

    Returns:
        {'features': [{'type': 'line', 'coords': [[e,n],[e,n],...]}, ...]}
    """
    if isinstance(layer_names, list):
        layer_names = ','.join(layer_names)

    # BBOX: minx,miny,maxx,maxy - w PL-2000 to easting,northing
    # Ale WFS 1.1+ z EPSG:2177 moze oczekiwac northing,easting
    # Probujemy oba formaty - najpierw easting,northing (czesciej dziala)
    bbox_str = '%.3f,%.3f,%.3f,%.3f' % (bbox[0], bbox[1], bbox[2], bbox[3])

    params = {
        'SERVICE': 'WFS',
        'REQUEST': 'GetFeature',
        'TYPENAME': layer_names,
        'SRSNAME': srs,
        'BBOX': bbox_str,
        'MAXFEATURES': str(MAX_FEATURES),
    }

    # Dodaj wersje jesli != 1.0
    if version and version != '1.0.0':
        params['VERSION'] = version

    url = _build_wfs_url(wfs_url, params)

    logger.info("WFS GetFeature: layers=%s bbox=%s", layer_names, bbox_str)
    xml_text = _fetch_url(url)

    # Parsuj GML
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("WFS: blad parsowania GML: %s", e)
        return {'features': [], 'error': 'Blad parsowania GML'}

    features = _parse_gml_features(root)

    # Auto-detect i napraw kolejnosc wspolrzednych
    features = _fix_coordinate_order(features)

    logger.info("WFS: %d features sparsowanych", len(features))
    return {'features': features, 'count': len(features)}


def _parse_gml_features(root):
    """Parsuj geometrie z GML response."""
    features = []

    # Szukaj elementow geometrycznych w calym drzewie
    for geom_tag in ('Point', 'LineString', 'Polygon', 'MultiLineString',
                     'MultiPolygon', 'MultiCurve', 'MultiSurface',
                     'Curve', 'Surface', 'LinearRing'):
        for elem in _find_all(root, geom_tag):
            parsed = _parse_geometry(elem, geom_tag)
            if parsed:
                features.extend(parsed) if isinstance(parsed, list) else features.append(parsed)

    return features


def _parse_geometry(elem, geom_type):
    """Parsuj pojedynczy element geometryczny GML."""

    if geom_type == 'Point':
        coords = _extract_coords(elem)
        if coords and len(coords) >= 1:
            return {'type': 'point', 'x': coords[0][0], 'y': coords[0][1]}

    elif geom_type in ('LineString', 'Curve'):
        coords = _extract_coords(elem)
        if coords and len(coords) >= 2:
            return {'type': 'polyline', 'coords': coords, 'closed': False}

    elif geom_type == 'LinearRing':
        coords = _extract_coords(elem)
        if coords and len(coords) >= 3:
            return {'type': 'polyline', 'coords': coords, 'closed': True}

    elif geom_type == 'Polygon':
        # Wyciagnij exterior ring
        rings = []
        ext = _find_elem(elem, 'exterior') or _find_elem(elem, 'outerBoundaryIs')
        if ext is not None:
            ring = _find_elem(ext, 'LinearRing')
            if ring is not None:
                coords = _extract_coords(ring)
                if coords and len(coords) >= 3:
                    rings.append({'type': 'polyline', 'coords': coords, 'closed': True})
        # Fallback: szukaj coordinates/posList bezposrednio
        if not rings:
            coords = _extract_coords(elem)
            if coords and len(coords) >= 3:
                rings.append({'type': 'polyline', 'coords': coords, 'closed': True})
        return rings if rings else None

    elif geom_type in ('MultiLineString', 'MultiCurve'):
        results = []
        for member in list(elem):
            for child in list(member):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                parsed = _parse_geometry(child, tag)
                if parsed:
                    results.extend(parsed) if isinstance(parsed, list) else results.append(parsed)
        # Fallback
        if not results:
            for ls in _find_all(elem, 'LineString'):
                p = _parse_geometry(ls, 'LineString')
                if p:
                    results.append(p)
        return results if results else None

    elif geom_type in ('MultiPolygon', 'MultiSurface'):
        results = []
        for poly in _find_all(elem, 'Polygon'):
            p = _parse_geometry(poly, 'Polygon')
            if p:
                results.extend(p) if isinstance(p, list) else results.append(p)
        return results if results else None

    return None


def _extract_coords(elem):
    """Wyciagnij wspolrzedne z elementu GML.
    Obsluguje <coordinates>, <posList>, <pos>.
    Zwraca [[x1,y1], [x2,y2], ...].
    """
    coords = []

    # 1. <gml:coordinates> - format: "x1,y1 x2,y2 ..."
    for coord_elem in _find_all(elem, 'coordinates'):
        if coord_elem.text:
            text = coord_elem.text.strip()
            for pair in text.split():
                parts = pair.split(',')
                if len(parts) >= 2:
                    try:
                        coords.append([float(parts[0]), float(parts[1])])
                    except ValueError:
                        pass

    if coords:
        return coords

    # 2. <gml:posList> - format: "x1 y1 x2 y2 ..."
    for pos_list in _find_all(elem, 'posList'):
        if pos_list.text:
            text = pos_list.text.strip()
            nums = text.split()
            # Sprawdz srsDimension
            dim = int(pos_list.attrib.get('srsDimension', '2'))
            for i in range(0, len(nums) - dim + 1, dim):
                try:
                    coords.append([float(nums[i]), float(nums[i + 1])])
                except (ValueError, IndexError):
                    pass

    if coords:
        return coords

    # 3. <gml:pos> - format: "x1 y1"
    for pos_elem in _find_all(elem, 'pos'):
        if pos_elem.text:
            parts = pos_elem.text.strip().split()
            if len(parts) >= 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass

    return coords


def _fix_coordinate_order(features):
    """Wykryj i napraw kolejnosc wspolrzednych.

    PL-2000/6: easting (Y_PL) ~6,400,000-6,700,000, northing (X_PL) ~5,300,000-5,700,000
    Chcemy: [easting, northing] czyli [~6.5M, ~5.5M]

    WFS moze zwrocic [northing, easting] (WFS 1.1+ z EPSG:2177).
    Wykrywamy to na podstawie zakresow wartosci.
    """
    # Zbierz probe wspolrzednych
    sample_first = []
    sample_second = []

    for f in features[:50]:
        if f['type'] == 'point':
            sample_first.append(f['x'])
            sample_second.append(f['y'])
        elif f['type'] == 'polyline' and f.get('coords'):
            for c in f['coords'][:5]:
                sample_first.append(c[0])
                sample_second.append(c[1])

    if not sample_first:
        return features

    avg_first = sum(sample_first) / len(sample_first)
    avg_second = sum(sample_second) / len(sample_second)

    # PL-2000/6: easting ~6.4-6.7M, northing ~5.3-5.7M
    need_swap = False
    if 5000000 < avg_first < 5800000 and 6300000 < avg_second < 6800000:
        # first=northing, second=easting -> swap
        need_swap = True
        logger.info("WFS: wykryto northing,easting -> zamieniam na easting,northing")
    elif 6300000 < avg_first < 6800000 and 5000000 < avg_second < 5800000:
        # first=easting, second=northing -> OK
        logger.info("WFS: wspolrzedne easting,northing -> OK")
    else:
        logger.warning("WFS: nierozpoznany zakres wspolrzednych (avg=%.0f, %.0f)", avg_first, avg_second)

    if need_swap:
        for f in features:
            if f['type'] == 'point':
                f['x'], f['y'] = f['y'], f['x']
            elif f['type'] == 'polyline' and f.get('coords'):
                for c in f['coords']:
                    c[0], c[1] = c[1], c[0]

    return features
