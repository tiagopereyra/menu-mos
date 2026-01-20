#!/usr/bin/env python3
import json
import subprocess
import sys
import time
import os
import socket
from pathlib import Path

# Intentar importar evdev para leer joystick/teclado globalmente
try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:
    print("Falta evdev. Instalar con: sudo apt install python3-evdev", file=sys.stderr)
    sys.exit(1)

import selectors

# Rutas
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
OVERLAY_SCRIPT = BASE_DIR / "menu_overlay.py"
SOCK_PATH = "/tmp/mos_overlay.sock" # Socket para comunicarnos con el menú

# ==========================================
# ⚙️ CONFIGURACIÓN DE BOTONES (Hardcoded por seguridad)
# ==========================================
# Puedes cambiar esto o usar el config.json, pero aquí es más directo.
# Nombres comunes: BTN_START, BTN_SELECT, BTN_TL (L1), BTN_TR (R1), BTN_MODE (Home)

COMBO_JOYSTICK = ["BTN_TL", "BTN_TR"] # L1 + R1 para abrir menú
COMBO_TECLADO  = ["KEY_LEFTCTRL", "KEY_M"] # Ctrl + M para abrir menú

COOLDOWN = 1.0 # Segundos de espera entre activaciones

# ==========================================

def send_toggle_command():
    """
    Intenta mandar la orden 'toggle' al menú si ya está abierto.
    Si el menú no está corriendo, lo lanza desde cero.
    """
    # 1. Intentar conectar por socket (forma rápida)
    if os.path.exists(SOCK_PATH):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCK_PATH)
            s.sendall(b"toggle\n")
            s.close()
            print("[Daemon] Toggle enviado por socket.")
            return
        except Exception:
            pass # Si falla, intentamos lanzarlo normalmente

    # 2. Si no hay socket, lanzamos el script (asegura que se abra si estaba cerrado)
    print("[Daemon] Lanzando menú...")
    subprocess.Popen(
        [sys.executable, str(OVERLAY_SCRIPT)],
        cwd=str(BASE_DIR),
        start_new_session=True
    )

def find_input_devices():
    """Busca todos los teclados y joysticks conectados"""
    devices = []
    try:
        for path in list_devices():
            try:
                dev = InputDevice(path)
                devices.append(dev)
            except Exception:
                pass
    except Exception:
        pass
    return devices

def check_combo(pressed_keys, combo_needed):
    """Devuelve True si TODAS las teclas del combo están presionadas"""
    for btn in combo_needed:
        if btn not in pressed_keys:
            return False
    return True

def main():
    print(f"[Daemon] Iniciando servicio M-OS Daemon...")
    print(f"[Daemon] Combo Joystick: {COMBO_JOYSTICK}")
    
    selector = selectors.DefaultSelector()
    devices = find_input_devices()
    
    if not devices:
        print("[Daemon] ¡OJO! No detecté dispositivos. Conecta un Joystick o Teclado.")
    
    for dev in devices:
        print(f"  -> Escuchando: {dev.name} ({dev.path})")
        selector.register(dev.fd, selectors.EVENT_READ, dev)

    pressed = set()
    last_fire = 0.0

    while True:
        # Re-escanear dispositivos cada tanto si se desconectan? 
        # Por simplicidad, asumimos que están conectados.
        
        try:
            events = selector.select(timeout=2.0)
        except Exception:
            continue

        for key, _ in events:
            dev = key.data
            try:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    
                    # Convertir código numérico a nombre (ej: 304 -> BTN_A)
                    key_name = ecodes.KEY.get(event.code)
                    if not key_name: 
                        key_name = f"UNKNOWN_{event.code}"

                    # event.value: 1=Pulsado, 0=Soltado, 2=Mantenido
                    if event.value == 1:
                        pressed.add(key_name)
                    elif event.value == 0:
                        pressed.discard(key_name)

                    # Chequear activación
                    now = time.time()
                    if (now - last_fire) > COOLDOWN:
                        
                        # ¿Se apretó el combo del Joystick?
                        if check_combo(pressed, COMBO_JOYSTICK):
                            print(f"[Daemon] ¡Combo Joystick detectado! {COMBO_JOYSTICK}")
                            send_toggle_command()
                            last_fire = now
                            pressed.clear() # Reset para evitar rebotes
                        
                        # ¿Se apretó el combo del Teclado?
                        elif check_combo(pressed, COMBO_TECLADO):
                            print(f"[Daemon] ¡Combo Teclado detectado!")
                            send_toggle_command()
                            last_fire = now
                            pressed.clear()

            except OSError:
                # Dispositivo desconectado
                selector.unregister(dev.fd)
                print(f"[Daemon] Dispositivo desconectado: {dev.name}")

if __name__ == "__main__":
    main()