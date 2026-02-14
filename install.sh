#!/bin/bash
# RTK Monitor - Skrypt instalacyjny dla Raspberry Pi

echo "======================================================================"
echo "RTK Monitor - Instalator"
echo "LC29H GPS/RTK HAT dla Raspberry Pi 4"
echo "======================================================================"
echo ""

# Sprawdź czy uruchamiany jako root
if [ "$EUID" -eq 0 ]; then 
    echo "⚠️  Nie uruchamiaj tego skryptu jako root!"
    echo "Użyj: ./install.sh"
    exit 1
fi

# Aktualizacja systemu
echo "📦 Aktualizacja systemu..."
sudo apt update

# Instalacja Pythona i pip
echo "🐍 Sprawdzanie Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "Instalacja Python 3..."
    sudo apt install -y python3 python3-pip python3-venv
else
    echo "✓ Python 3 jest zainstalowany"
fi

# Włączenie UART
echo ""
echo "🔧 Konfiguracja UART..."
echo "Sprawdzanie /boot/firmware/config.txt..."

CONFIG_FILE="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="/boot/config.txt"
fi

if grep -q "^enable_uart=1" "$CONFIG_FILE"; then
    echo "✓ UART już włączony"
else
    echo "Włączanie UART..."
    echo "enable_uart=1" | sudo tee -a "$CONFIG_FILE"
    echo "dtoverlay=disable-bt" | sudo tee -a "$CONFIG_FILE"
    REBOOT_REQUIRED=true
fi

# Wyłączenie konsoli szeregowej
echo "Wyłączanie konsoli szeregowej..."
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service

# Utworzenie środowiska wirtualnego
echo ""
echo "📦 Tworzenie środowiska wirtualnego Python..."
python3 -m venv venv

# Aktywacja venv
source venv/bin/activate

# Instalacja zależności
echo ""
echo "📦 Instalacja zależności Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "======================================================================"
echo "✅ Instalacja zakończona!"
echo "======================================================================"
echo ""

if [ "$REBOOT_REQUIRED" = true ]; then
    echo "⚠️  WYMAGANY RESTART SYSTEMU"
    echo ""
    echo "Zmiany w konfiguracji UART wymagają restartu Raspberry Pi."
    echo "Po restarcie uruchom aplikację komendą:"
    echo ""
    echo "    cd $(pwd)"
    echo "    source venv/bin/activate"
    echo "    python3 app.py"
    echo ""
    read -p "Czy chcesz teraz zrestartować system? (t/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Tt]$ ]]; then
        sudo reboot
    fi
else
    echo "🚀 Możesz teraz uruchomić aplikację:"
    echo ""
    echo "    source venv/bin/activate"
    echo "    python3 app.py"
    echo ""
    echo "Aplikacja będzie dostępna pod adresem:"
    echo "    http://$(hostname -I | awk '{print $1}'):5000"
    echo ""
fi

echo "📖 Więcej informacji w README.md"
echo ""
