# RTK Monitor

Aplikacja webowa do monitorowania pozycji GPS/RTK na Raspberry Pi z modulem Waveshare LC29H(DA) RTK HAT. Zintegrowany klient NTRIP dla ASG-EUPOS.

## Funkcje

- Status Fix: No Fix / GPS / DGPS / RTK Float / RTK Fixed
- Pozycja GPS w czasie rzeczywistym (WebSocket co 1s)
- Dokladnosc: HDOP, PDOP, VDOP
- Zintegrowany klient NTRIP sterowany z przegladarki
- Konfiguracja ASG-EUPOS z UI (stacja, port, login)
- Auto-detekcja portu UART (RPi 4/5/USB)
- Responsywny design (smartfon, tablet)

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
├── app.py              # Backend Flask + SocketIO + NTRIP
├── gps_reader.py       # Czytnik NMEA z auto-detekcja portu
├── ntrip_client.py     # Klient NTRIP v2.0 dla ASG-EUPOS
├── requirements.txt
├── install.sh
├── config.json         # (tworzony automatycznie)
├── README.md
├── LICENSE
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

## Licencja

MIT
