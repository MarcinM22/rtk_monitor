# RTK Monitor

Aplikacja webowa do monitorowania pozycji GPS/RTK i pomiarow geodezyjnych na Raspberry Pi z modulem Waveshare LC29H(DA) RTK HAT. Zintegrowany klient NTRIP dla ASG-EUPOS.

## Funkcje

- **Status Fix**: No Fix / GPS / DGPS / RTK Float / RTK Fixed
- **Pozycja GPS** w czasie rzeczywistym (HTTP polling 1 Hz)
- **Dokladnosc DOP**: HDOP, PDOP, VDOP z kolorowaniem
- **Estymacja dokladnosci**: pozioma i wysokosciowa (2-sigma, 95%) na podstawie fixu i DOP
- **Zintegrowany klient NTRIP** sterowany z przegladarki (ASG-EUPOS)
- **Pomiary geodezyjne**: zbieranie probek RTK Fixed, usrednianie, zapis CSV + raport
- **Wspolrzedne PL-2000 strefa 6** (EPSG:2177) + **wysokosc EVRF2007-NH** (siatka GUGiK 2021)
- **Wysokosc anteny**: konfigurowalny offset odejmowany od wysokosci normalnej
- **Wytyczanie punktow**: z pliku, z projektu lub reczne z nawigacja N/S/E/W
- **Podglad mapy**: Canvas z punktami projektu + overlay DXF (pan/zoom/dotyk)
- **Temperatura CPU**: monitoring w naglowku (kolorowanie wg progow)
- **Projekty zewnetrzne**: `~/rtk_projekty` - przetrwaja reinstalacje aplikacji
- **Auto-detekcja portu UART** (RPi 4/5/USB)
- **Responsywny design** (Chrome na Android, tablet, desktop)

## Wymagania

- Raspberry Pi 4 lub 5
- Waveshare LC29H(DA) RTK HAT
- Antena GNSS
- Raspberry Pi OS (Bullseye/Bookworm)
- Python 3.7+

## Instalacja

```bash
cd ~
git clone https://github.com/MarcinM22/rtk_monitor.git
cd rtk_monitor
chmod +x install.sh
./install.sh
```

Po restarcie (jesli wymagany):

```bash
cd ~/rtk_monitor
source venv/bin/activate
python3 app.py
```

Otworz przegladarke: `http://<IP_RASPBERRY>:5000`

## Konfiguracja sprzetowa

Jumper na module LC29H:
- Pozycja B -> komunikacja przez GPIO UART (zalecane)
- Pozycja A -> komunikacja przez USB

Port UART (auto-detekcja):
- RPi 4B: `/dev/ttyS0`
- RPi 5: `/dev/ttyAMA0`
- USB: `/dev/ttyUSB0`

## Polaczenie w terenie

Zalecane polaczenie RPi z telefonem: **kabel USB** (USB tethering).
Unika problemow z izolacja klientow hotspota Wi-Fi na Androidzie.

1. Podlacz telefon kablem USB do RPi
2. Na telefonie: wlacz USB tethering (Ustawienia -> Siec -> Hotspot -> Tethering USB)
3. RPi automatycznie dostanie internet przez `usb0`
4. SSH i przegladarka dzialaja bez problemow

## Konfiguracja ASG-EUPOS (RTK)

1. Zarejestruj konto na https://system.asgeupos.pl
2. Uruchom aplikacje i otworz w przegladarce
3. Kliknij "Ustawienia" przy sekcji NTRIP
4. Wpisz login i haslo ASG-EUPOS
5. Wybierz najblizszaja stacje (lub AUTO)
6. Kliknij "Zapisz i polacz"

Parametry polaczenia ASG-EUPOS:

| Port | Format | Systemy satelitarne |
|------|--------|---------------------|
| 8086 | RTCM 3.4 | GPS+GLO+GAL+BDS (zalecany) |
| 8082 | RTCM 3.1 | GPS+GLO (polnoc) |
| 8083 | RTCM 3.1 | GPS+GLO (poludnie) |

## Wysokosc anteny

W sekcji "Pomiary" mozna ustawic wysokosc anteny nad mierzonym punktem (0-10 m).
Wartosc jest odejmowana od obliczonej wysokosci normalnej EVRF2007-NH przy kazdym pomiarze
i przy wytyczaniu. Zapisywana w `config.json` i w CSV przy kazdym punkcie.

## Podglad mapy

Blok "Mapa" wyswietla:
- Punkty z biezacego projektu (niebieskie z etykieta)
- Overlay pliku DXF (linie, polylinie, okregi, luki, punkty, teksty)

Obsluga:
- **Pan**: przeciagnij palcem (Android) lub mysza
- **Zoom**: pinch (Android) lub scroll mysza
- **DXF**: wgraj plik przyciskiem "+ DXF", wybierz z listy
- **Dopasuj**: przycisk "Dopasuj" centruje widok na danych

Pliki DXF naleza do projektu - wgrywane do katalogu projektu w `~/rtk_projekty/<nazwa>/`.

## Estymacja dokladnosci

Aplikacja szacuje dokladnosc pozycji na podstawie jakosci fixu i wartosci DOP:

| Fix | Baza H (1σ) | Baza V (1σ) |
|-----|-------------|-------------|
| RTK Fixed | 0.008 m | 0.015 m |
| RTK Float | 0.20 m | 0.30 m |
| DGPS | 0.50 m | 0.80 m |
| GPS | 2.50 m | 4.00 m |

Wyswietlana wartosc = baza × DOP × 2 (2-sigma, 95% ufnosc).

## Interpretacja danych

Fix Type:
- No Fix: brak sygnalu
- GPS Fix: standardowy GPS (~5 m)
- DGPS Fix: GPS roznicowy (~1 m)
- RTK Float: RTK zmiennoprzecinkowy (~10-50 cm)
- RTK Fixed: RTK calkowity (~1-2 cm)

DOP:
- < 2: Idealnie | 2-5: Dobrze | 5-10: Umiarkowanie | > 10: Slabo

## Autostart (systemd)

```bash
sudo tee /etc/systemd/system/rtk-monitor.service << EOF
[Unit]
Description=RTK Monitor
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/rtk_monitor
ExecStart=$HOME/rtk_monitor/venv/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable rtk-monitor
sudo systemctl start rtk-monitor
```

## Rozwiazywanie problemow

Brak danych GPS:
```bash
sudo cat /dev/ttyS0     # RPi 4
sudo cat /dev/ttyAMA0   # RPi 5
```

Port zajety:
```bash
sudo systemctl stop serial-getty@ttyS0.service
sudo systemctl disable serial-getty@ttyS0.service
```

## Struktura

```
rtk_monitor/
├── app.py              # Backend Flask + NTRIP + API
├── gps_reader.py       # Czytnik NMEA z auto-detekcja portu
├── ntrip_client.py     # Klient NTRIP dla ASG-EUPOS
├── coordinates.py      # Konwersja WGS84 -> PL-2000 + EVRF2007
├── surveyor.py         # Pomiary, projekty, DXF, wytyczanie
├── diagnose.py         # Narzedzie diagnostyczne
├── requirements.txt
├── install.sh
├── config.json         # (tworzony automatycznie)
├── README.md
├── LICENSE
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
└── wytyczenie/         # Pliki do wytyczania
    └── przyklad.txt

~/rtk_projekty/         # Katalog projektow (poza aplikacja!)
├── Projekt_1/
│   ├── wspolrzedne.csv
│   ├── raport.txt
│   └── podklad.dxf     # Opcjonalny overlay mapy
└── Projekt_2/
    └── ...
```

## Licencja

MIT
