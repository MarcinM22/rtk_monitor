#!/bin/bash
set -e

echo "========================================"
echo "  RTK Monitor - Instalacja"
echo "========================================"
echo

# Aktualizacja
echo "[1/5] Aktualizacja pakietow..."
sudo apt-get update -q

echo "[2/5] Instalacja zaleznosci..."
sudo apt-get install -y python3 python3-pip python3-venv libproj-dev proj-data proj-bin

# UART
echo "[3/5] Konfiguracja UART..."
NEEDS_REBOOT=0

CONFIG_FILE=""
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
fi

if [ -n "$CONFIG_FILE" ]; then
    if ! grep -q "^enable_uart=1" "$CONFIG_FILE"; then
        echo "enable_uart=1" | sudo tee -a "$CONFIG_FILE" > /dev/null
        echo "  Dodano: enable_uart=1"
        NEEDS_REBOOT=1
    fi
    if ! grep -q "dtoverlay=miniuart-bt" "$CONFIG_FILE" && ! grep -q "dtoverlay=disable-bt" "$CONFIG_FILE"; then
        echo "dtoverlay=miniuart-bt" | sudo tee -a "$CONFIG_FILE" > /dev/null
        echo "  Dodano: dtoverlay=miniuart-bt"
        NEEDS_REBOOT=1
    fi
else
    echo "  UWAGA: nie znaleziono config.txt"
fi

# Wylacz konsole szeregowa
sudo systemctl stop serial-getty@ttyS0.service 2>/dev/null || true
sudo systemctl disable serial-getty@ttyS0.service 2>/dev/null || true
sudo systemctl stop serial-getty@ttyAMA0.service 2>/dev/null || true
sudo systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true

# Usun console= z cmdline.txt
CMDLINE=""
if [ -f /boot/firmware/cmdline.txt ]; then
    CMDLINE="/boot/firmware/cmdline.txt"
elif [ -f /boot/cmdline.txt ]; then
    CMDLINE="/boot/cmdline.txt"
fi
if [ -n "$CMDLINE" ]; then
    if grep -q "console=serial" "$CMDLINE" || grep -q "console=ttyAMA" "$CMDLINE" || grep -q "console=ttyS" "$CMDLINE"; then
        sudo sed -i 's/console=serial0,[0-9]* //g' "$CMDLINE"
        sudo sed -i 's/console=ttyAMA0,[0-9]* //g' "$CMDLINE"
        sudo sed -i 's/console=ttyS0,[0-9]* //g' "$CMDLINE"
        echo "  Usunieto console= z cmdline.txt"
        NEEDS_REBOOT=1
    fi
fi

# Grupa dialout
sudo usermod -a -G dialout "$USER" 2>/dev/null || true

# Python venv
echo "[4/5] Srodowisko Python..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Opcjonalnie: pelna siatka geoidy dla dokladnych wysokosci
echo
echo "  [INFO] Instaluje siatke geoidy PL-EVRF2007-NH..."
PROJ_DIR=$(python3 -c "import pyproj; print(pyproj.datadir.get_data_dir())" 2>/dev/null)
if [ -n "$PROJ_DIR" ]; then
    # Napraw proj.db version mismatch
    if [ -f /usr/share/proj/proj.db ]; then
        cp /usr/share/proj/proj.db "$PROJ_DIR/proj.db" 2>/dev/null || true
    fi
    # Pobierz polska siatke geoidy
    projsync --target-dir "$PROJ_DIR" --file pl_gugik_geoid2021-PL-EVRF2007-NH.tif 2>/dev/null && \
        echo "  [OK] Siatka geoidy zainstalowana" || \
        echo "  [!!] Nie udalo sie pobrac siatki (dziala bez niej z przyblizeniem)"
else
    echo "  [!!] Brak pyproj - pominam siatke geoidy"
fi

echo
echo "[5/5] Gotowe!"
echo
echo "  Uruchomienie:"
echo "    cd $SCRIPT_DIR"
echo "    source venv/bin/activate"
echo "    python3 app.py"
echo

if [ "$NEEDS_REBOOT" -eq 1 ]; then
    echo "  *** WYMAGANY RESTART! ***"
    echo
    read -p "  Restartowac teraz? (t/n): " ANSWER
    if [ "$ANSWER" = "t" ] || [ "$ANSWER" = "T" ] || [ "$ANSWER" = "y" ] || [ "$ANSWER" = "Y" ]; then
        sudo reboot
    else
        echo "  Pamietaj: sudo reboot"
    fi
fi
