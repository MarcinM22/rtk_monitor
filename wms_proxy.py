"""
wms_proxy.py - Proxy WMS dla RTK Monitor
Pobiera GetCapabilities (lista warstw) i proxy GetMap (obraz PNG/JPEG).
"""

import re
import logging
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, urlparse, parse_qs, quote

logger = logging.getLogger(__name__)

WMS_TIMEOUT = 15


def _fetch_raw(url, timeout=WMS_TIMEOUT):
    """Pobierz URL i zwroc surowe bajty + content-type."""
    try:
        req = Request(url, headers={
            'User-Agent': 'RTKMonitor/1.0',
        })
        resp = urlopen(req, timeout=timeout)
        ct = resp.headers.get('Content-Type', '')
        data = resp.read()
        return data, ct
    except (HTTPError, URLError) as e:
        logger.error("WMS fetch error: %s (%s)", e, url[:120])
        raise


def _build_url(base_url, params):
    """Zbuduj URL z parametrami (nadpisuj istniejace case-insensitive)."""
    parsed = urlparse(base_url)
    existing = parse_qs(parsed.query, keep_blank_values=True)

    merged = {}
    for k, v in existing.items():
        merged[k.upper()] = v
    for k, v in params.items():
        merged[k.upper()] = [v] if isinstance(v, str) else v

    query_parts = []
    for k, vals in merged.items():
        for v in vals:
            query_parts.append('%s=%s' % (k, quote(str(v), safe=',.:/')))
    query = '&'.join(query_parts)

    base = parsed._replace(query='').geturl()
    return base + '?' + query


def _find_elem(root, local_name):
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


def _get_child(elem, local_name):
    """Znajdz bezposrednie dziecko po nazwie lokalnej."""
    for child in elem:
        tag = child.tag
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag == local_name:
            return child
    return None


def get_capabilities(wms_url):
    """Pobierz GetCapabilities i zwroc liste warstw.

    Returns:
        {
            'layers': [{'name': 'xxx', 'title': 'yyy'}, ...],
            'version': '1.1.1',
            'title': 'Serwer WMS',
            'formats': ['image/png', ...],
        }
    """
    url = _build_url(wms_url, {
        'SERVICE': 'WMS',
        'REQUEST': 'GetCapabilities',
    })

    logger.info("WMS GetCapabilities: %s", url[:150])
    raw, ct = _fetch_raw(url)
    xml_text = raw.decode('utf-8', errors='ignore')

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("WMS: blad parsowania XML: %s", e)
        return {'error': 'Blad parsowania odpowiedzi XML', 'layers': []}

    # Wersja
    version = root.attrib.get('version', '1.1.1')

    # Tytul
    service_elem = _find_elem(root, 'Service')
    title = ''
    if service_elem is not None:
        title_elem = _get_child(service_elem, 'Title')
        if title_elem is not None and title_elem.text:
            title = title_elem.text.strip()

    # Formaty GetMap
    formats = []
    for fmt in _find_all(root, 'Format'):
        if fmt.text and 'image/' in fmt.text:
            formats.append(fmt.text.strip())
    # Deduplikuj
    formats = list(dict.fromkeys(formats))

    # Warstwy - szukamy Layer z atrybutem Name (queryable)
    layers = []
    for layer_elem in _find_all(root, 'Layer'):
        name_elem = _get_child(layer_elem, 'Name')
        title_elem = _get_child(layer_elem, 'Title')

        if name_elem is None or not name_elem.text:
            continue

        name = name_elem.text.strip()
        layer_title = title_elem.text.strip() if title_elem is not None and title_elem.text else name

        # Zbierz SRS/CRS
        srs_list = []
        for srs_tag in ('SRS', 'CRS'):
            for srs_elem in _find_all(layer_elem, srs_tag):
                if srs_elem.text:
                    srs_list.append(srs_elem.text.strip())

        # Sprawdz czy obsluguje EPSG:2177
        has_2177 = any('2177' in s for s in srs_list)

        layers.append({
            'name': name,
            'title': layer_title,
            'has_2177': has_2177,
            'srs': srs_list[:5],  # max 5 przykladowych
        })

    logger.info("WMS: %d warstw, wersja %s, %d formatow", len(layers), version, len(formats))
    return {
        'layers': layers,
        'version': version,
        'title': title,
        'formats': formats,
    }


def get_map_image(wms_url, layers, bbox, width, height,
                  srs='EPSG:2177', version='1.1.1', fmt='image/png'):
    """Pobierz obraz GetMap.

    Args:
        wms_url: bazowy URL WMS
        layers: lista nazw warstw (string z przecinkami)
        bbox: (min_easting, min_northing, max_easting, max_northing)
        width, height: rozmiar obrazu w pikselach
        srs: uklad odniesienia
        version: wersja WMS
        fmt: format obrazu

    Returns:
        (image_bytes, content_type) lub (None, error_msg)
    """
    min_e, min_n, max_e, max_n = bbox

    # WMS 1.1.x: BBOX=minx,miny,maxx,maxy, SRS=...
    # WMS 1.3.0: BBOX wg osi CRS (EPSG:2177 -> northing,easting), CRS=...
    if version.startswith('1.3'):
        srs_key = 'CRS'
        bbox_str = '%.3f,%.3f,%.3f,%.3f' % (min_n, min_e, max_n, max_e)
    else:
        srs_key = 'SRS'
        bbox_str = '%.3f,%.3f,%.3f,%.3f' % (min_e, min_n, max_e, max_n)

    params = {
        'SERVICE': 'WMS',
        'REQUEST': 'GetMap',
        'LAYERS': layers,
        srs_key: srs,
        'BBOX': bbox_str,
        'WIDTH': str(int(width)),
        'HEIGHT': str(int(height)),
        'FORMAT': fmt,
        'TRANSPARENT': 'TRUE',
        'VERSION': version,
        'STYLES': '',
    }

    url = _build_url(wms_url, params)
    logger.info("WMS GetMap: %s", url[:200])

    try:
        data, ct = _fetch_raw(url)
    except Exception as e:
        return None, str(e)

    # Sprawdz czy nie dostalismy XML bledu zamiast obrazu
    if ct and 'xml' in ct.lower():
        # To pewnie ServiceException
        try:
            text = data.decode('utf-8', errors='ignore')
            err_root = ET.fromstring(text)
            exc = _find_elem(err_root, 'ServiceException')
            err_msg = exc.text.strip() if exc is not None and exc.text else text[:100]
            logger.error("WMS Exception: %s", err_msg[:100])
            return None, err_msg[:100]
        except Exception:
            return None, 'WMS zwrocil XML zamiast obrazu'

    if not data or len(data) < 100:
        return None, 'Pusty obraz'

    logger.info("WMS: obraz %d bajtow (%s)", len(data), ct)
    return data, ct
