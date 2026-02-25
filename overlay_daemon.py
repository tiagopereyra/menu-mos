#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

try:
    from evdev import InputDevice, ecodes, list_devices
    import selectors
except ImportError:
    print("Falta evdev. Instalá con: sudo apt install python3-evdev", file=sys.stderr)
    sys.exit(1)

# =========================
# RUTAS
# =========================
BASE_DIR = Path(__file__).resolve().parent
OVERLAY_SCRIPT = BASE_DIR / "menu_overlay.py"
SOCK_PATH = "/tmp/mos_overlay.sock"

# =========================
# CONFIG
# =========================
COOLDOWN = 0.8          # anti doble-trigger
RESCAN_EVERY = 5.0      # reescanea /dev/input por si reconectás el joystick
DEBUG_KEYS = False      # ponelo True si querés ver qué llega
GRAB_DEVICES = False    # dejalo False para no interferir con ES-DE/Steam

# =========================
# COMBOS
# =========================
# DualShock / PS Controller:
# SHARE  = BTN_SELECT (314)
# OPTIONS= BTN_START  (315)
JOY_COMBO = {ecodes.BTN_SELECT, ecodes.BTN_START}

# Teclado:
KEY_COMBO = {ecodes.KEY_LEFTCTRL, ecodes.KEY_M}

# =========================
# HELPERS
# =========================
def code_name(code: int) -> str:
    try:
        return ecodes.bytype[ecodes.EV_KEY].get(code, str(code))
    except Exception:
        return str(code)

def is_gamepad(dev: InputDevice) -> bool:
    """Filtra para quedarnos con gamepads/joysticks."""
    try:
        caps = dev.capabilities(verbose=False)
        if ecodes.EV_KEY not in caps:
            return False
        keys = set(caps.get(ecodes.EV_KEY, []))

        hints = {
            ecodes.BTN_GAMEPAD,
            ecodes.BTN_SOUTH,
            ecodes.BTN_EAST,
            ecodes.BTN_NORTH,
            ecodes.BTN_WEST,
            ecodes.BTN_SELECT,  # Share
            ecodes.BTN_START,   # Options
        }
        return len(keys.intersection(hints)) > 0
    except Exception:
        return False

def is_keyboard(dev: InputDevice) -> bool:
    """Detecta si el dispositivo es un teclado capaz de hacer el combo."""
    try:
        caps = dev.capabilities(verbose=False)
        if ecodes.EV_KEY not in caps:
            return False
        keys = set(caps.get(ecodes.EV_KEY, []))
        
        # Verificamos si tiene las teclas necesarias para el combo
        # Esto evita agarrar mouses o botones de encendido
        if ecodes.KEY_M in keys and ecodes.KEY_LEFTCTRL in keys:
            return True
            
        return False
    except Exception:
        return False

def combo_match(pressed_codes: set[int], combo_codes: set[int]) -> bool:
    return combo_codes.issubset(pressed_codes)

def send_toggle_command():
    """Si el menú está abierto, manda toggle por socket; si no, lo lanza."""
    if os.path.exists(SOCK_PATH):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCK_PATH)
            s.sendall(b"toggle\n")
            s.close()
            return
        except Exception:
            pass

def scan_devices():
    found = []
    try:
        for path in list_devices():
            try:
                d = InputDevice(path)
                # AHORA ACEPTAMOS GAMEPAD O TECLADO
                if is_gamepad(d) or is_keyboard(d):
                    found.append(d)
                else:
                    try: d.close()
                    except: pass
            except Exception:
                pass
    except Exception:
        pass
    return found

# =========================
# MAIN
# =========================
def main():
    print("[Daemon] M-OS overlay daemon activo.")
    print("[Daemon] Combo Joystick:", " + ".join(code_name(c) for c in sorted(JOY_COMBO)))
    print("[Daemon] Combo Teclado :", " + ".join(code_name(c) for c in sorted(KEY_COMBO)))

    selector = selectors.DefaultSelector()
    devices_by_path: dict[str, InputDevice] = {}

    pressed: set[int] = set()
    last_fire = 0.0
    last_scan = 0.0

    def register_device(dev: InputDevice):
        if dev.path in devices_by_path:
            return
        devices_by_path[dev.path] = dev
        try:
            if GRAB_DEVICES:
                try:
                    dev.grab()
                except Exception:
                    pass
            selector.register(dev.fd, selectors.EVENT_READ, dev)
            print(f"[Daemon] -> Escuchando: {dev.name} ({dev.path})")
        except Exception as e:
            print(f"[Daemon] No pude registrar {dev.path}: {e}")
            try: dev.close()
            except: pass
            devices_by_path.pop(dev.path, None)

    def unregister_device(dev: InputDevice):
        try: selector.unregister(dev.fd)
        except: pass
        try: dev.close()
        except: pass
        devices_by_path.pop(dev.path, None)
        print(f"[Daemon] Dispositivo desconectado: {dev.name} ({dev.path})")

    # Primer scan
    for d in scan_devices():
        register_device(d)

    if not devices_by_path:
        print("[Daemon] OJO: no detecté dispositivos compatibles (permisos o no conectados).")

    while True:
        now = time.time()

        # Re-scan periódico
        if (now - last_scan) >= RESCAN_EVERY:
            last_scan = now
            for d in scan_devices():
                register_device(d)

        # Leer eventos
        try:
            events = selector.select(timeout=1.0)
        except Exception:
            continue

        for key, _ in events:
            dev: InputDevice = key.data
            try:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue

                    # 1=down, 0=up, 2=hold
                    if event.value == 1:
                        pressed.add(event.code)
                        if DEBUG_KEYS:
                            print(f"[DBG] DOWN {dev.name}: {code_name(event.code)} ({event.code})")
                    elif event.value == 0:
                        if DEBUG_KEYS:
                            print(f"[DBG] UP    {dev.name}: {code_name(event.code)} ({event.code})")
                        pressed.discard(event.code)

                    # Chequear combos con cooldown
                    now2 = time.time()
                    if (now2 - last_fire) > COOLDOWN:
                        if combo_match(pressed, JOY_COMBO) or combo_match(pressed, KEY_COMBO):
                            send_toggle_command()
                            last_fire = now2
                            pressed.clear()

            except OSError:
                unregister_device(dev)
            except Exception:
                pass

if __name__ == "__main__":
    main()