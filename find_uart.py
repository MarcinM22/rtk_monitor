#!/usr/bin/env python3
"""
Skrypt do wykrywania dostępnych portów szeregowych na Raspberry Pi
"""

import os
import glob

print("=" * 60)
print("Wykrywanie portów szeregowych UART")
print("=" * 60)
print()

# Sprawdź porty tty
print("📍 Dostępne porty tty:")
tty_ports = glob.glob('/dev/tty[A-Z]*[0-9]*')
if tty_ports:
    for port in sorted(tty_ports):
        print(f"  ✓ {port}")
else:
    print("  ✗ Brak portów tty*")

print()

# Sprawdź porty serial
print("📍 Dostępne porty serial:")
serial_ports = glob.glob('/dev/serial*')
if serial_ports:
    for port in sorted(serial_ports):
        # Sprawdź czy to symlink
        if os.path.islink(port):
            target = os.readlink(port)
            print(f"  ✓ {port} -> {target}")
        else:
            print(f"  ✓ {port}")
else:
    print("  ✗ Brak portów serial*")

print()

# Typowe porty dla Raspberry Pi
common_ports = [
    '/dev/ttyAMA0',
    '/dev/ttyS0', 
    '/dev/serial0',
    '/dev/serial1',
    '/dev/ttyUSB0'
]

print("📍 Sprawdzanie typowych portów UART:")
existing = []
for port in common_ports:
    if os.path.exists(port):
        print(f"  ✓ {port} - ISTNIEJE")
        existing.append(port)
    else:
        print(f"  ✗ {port} - brak")

print()
print("=" * 60)

if existing:
    print(f"✅ Znaleziono {len(existing)} dostępnych portów")
    print()
    print("💡 Zalecenie:")
    print(f"   Użyj portu: {existing[0]}")
    print()
    print("   W pliku app.py zmień na:")
    print(f"   gps = GPSReader(port='{existing[0]}', baudrate=115200)")
else:
    print("❌ Nie znaleziono żadnych portów UART!")
    print()
    print("🔧 Sprawdź konfigurację:")
    print("   1. Czy UART jest włączony w /boot/firmware/config.txt?")
    print("      Powinno być: enable_uart=1")
    print()
    print("   2. Czy moduł LC29H HAT jest poprawnie zamontowany na GPIO?")
    print()
    print("   3. Czy po dodaniu enable_uart=1 wykonałeś restart?")
    print("      sudo reboot")

print()
print("=" * 60)
