#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
import time
import socket
import threading
import tkinter as tk
import tkinter.font as tkfont

# ==========================================
# 📦 IMPORTACIÓN DE LIBRERÍAS OPCIONALES
# ==========================================

# PIL (Pillow) para imágenes de alta calidad
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# EVDEV para soporte de Joystick
ENABLE_JOYSTICK = True
HAS_EVDEV = False

if ENABLE_JOYSTICK:
    try:
        from evdev import InputDevice, ecodes, list_devices
        import selectors
        HAS_EVDEV = True
    except ImportError:
        HAS_EVDEV = False
    except Exception:
        HAS_EVDEV = False

# ==========================================
# ⚙️ CONFIGURACIÓN Y CONSTANTES
# ==========================================

# Comportamiento
WRAP_AROUND = False  # True: vuelve al inicio al bajar del todo
JOY_NAV_COOLDOWN = 0.15  # Segundos entre movimientos del stick
JOY_AXIS_THRESHOLD = 18000  # Zona muerta del stick (aprox 50%)

# Actualizaciones OTA
OTA_STATE_FILE = "/opt/ota/state"
SCRIPT_STATE_FILE = "/opt/ota/script-state"

# Rutas y Archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
UID = os.getuid()
PULSE_SOCKET = f"unix:/run/user/{UID}/pulse/native"

# Visual
APP_TITLE = "M-OS Overlay"
WINDOW_ALPHA = 1.0
UI_SCALE = 1.0
ICON_SIZE_BASE = 48

# Colores
C_BG_MAIN = "#000000"
C_CARD_BG = "#111111"
C_CARD_HOVER = "#1E6BFF"
C_TEXT_MAIN = "#FFFFFF"
C_TEXT_SEC = "#AAAAAA"
C_DANGER = "#CF0000"
ACCENT = "#22c55e"
BORDER = "#333333"

HAS_NERD_FONT = False

# ==========================================
# 🛠️ FUNCIONES UTILITARIAS Y DE ESTADO
# ==========================================

def sc(x: int) -> int: return max(1, int(x * UI_SCALE))
def fs(x: int) -> int: return max(10, int(x * UI_SCALE))


def read_state_file(path):
    try:
        if not os.path.exists(path):
            return "IDLE"
        with open(path, "r") as f:
            return f.read().strip().upper() or "IDLE"
    except:
        return "IDLE"

def get_update_status():
    ota = read_state_file(OTA_STATE_FILE)
    script = read_state_file(SCRIPT_STATE_FILE)

    # Si cualquiera está en proceso, consideramos “actualizando”
    busy_states = {"CHECKING", "CHECKED", "DOWNLOADING", "DOWNLOADED", "INSTALLING"}

    if ota in busy_states or script in busy_states:
        # Devolvemos algo legible para el usuario
        return f"OTA={ota}, Scripts={script}"

    # Si ambos están DONE o IDLE, consideramos seguro
    if ota in {"IDLE", "DONE"} and script in {"IDLE", "DONE"}:
        return None  # sin actualización

    # Cualquier FAILED también es interesante avisar
    if ota == "FAILED" or script == "FAILED":
        return f"ERROR: OTA={ota}, Scripts={script}"

    return None




def register_app(identifier, path="/tmp/open_apps"):
    """Registra una app abierta para gestión externa"""
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("")
    with open(path, "a") as f:
        f.write(str(identifier) + "\n")

def kill_es_de():
    """Mata procesos de EmulationStation si existen"""
    try:
        cmd = "ps w | grep -i 'es-de' | grep -v grep | awk '{print $1}'"
        pids = os.popen(cmd).read().strip().split()
        for pid in pids:
            if pid.isdigit():
                os.system(f"kill -9 {pid}")
    except:
        pass

def run_fast(cmd):
    """Ejecuta un comando sin esperar retorno"""
    try:
        subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        print(f"[Err] {cmd}: {e}")

def run_threaded_action(cmd_list, on_finish=None):
    """Ejecuta una lista de comandos en hilo separado"""
    def worker():
        for cmd in cmd_list:
            try:
                subprocess.run(cmd, check=True, timeout=1)
            except Exception:
                pass
        if on_finish:
            on_finish()
    threading.Thread(target=worker, daemon=True).start()

# --- Lectores de Estado del Sistema ---

def get_volume_text():
    try:
        res = subprocess.check_output(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            text=True, timeout=1
        )
        for part in res.replace("/", " ").replace(",", " ").split():
            if part.endswith("%") and part[:-1].isdigit():
                return f"Volumen: {part}"
        return "Volumen: --"
    except:
        return "Volumen: N/A"

def get_brightness_text():
    try:
        curr = int(subprocess.check_output(["brightnessctl", "g"], text=True, timeout=1))
        max_b = int(subprocess.check_output(["brightnessctl", "m"], text=True, timeout=1))
        if max_b == 0: return "Brillo: --"
        percent = int((curr / max_b) * 100)
        return f"Brillo: {percent}%"
    except:
        try:
            val = float(subprocess.check_output(["light", "-G"], text=True, timeout=1).strip())
            return f"Brillo: {int(val)}%"
        except:
            return "Nivel de Brillo"

def get_wifi_text():
    try:
        cmd = "nmcli -t -f active,ssid dev wifi | grep '^yes'"
        res = subprocess.check_output(cmd, shell=True, text=True, timeout=1).strip()
        ssid = res.split(":", 1)[1].strip() if ":" in res else ""
        return f"Conectado a: {ssid}" if ssid else "Wi-Fi: Desconectado"
    except:
        return "Wi-Fi: Sin datos"

def get_bt_text():
    try:
        res = subprocess.check_output(["bluetoothctl", "show"], text=True, timeout=1)
        return "Bluetooth: Encendido" if "Powered: yes" in res else "Bluetooth: Apagado"
    except:
        return "Bluetooth: N/A"

def get_night_light_state():
    return os.path.exists("/tmp/nightlight_state")

# ==========================================
# 🎮 ACCIONES DEL MENÚ
# ==========================================

def action_vol_up():
    return [["pactl", "--server", PULSE_SOCKET, "set-sink-volume", "@DEFAULT_SINK@", "+5%"]]

def action_vol_down():
    return [["pactl", "--server", PULSE_SOCKET, "set-sink-volume", "@DEFAULT_SINK@", "-5%"]]

def action_bri_up():
    return [["brightnessctl", "set", "5%+"], ["light", "-A", "5"]]

def action_bri_down():
    return [["brightnessctl", "set", "5%-"], ["light", "-U", "5"]]

def action_toggle_night_light():
    state_file = "/tmp/nightlight_state"
    if os.path.exists(state_file):
        return [["gammastep", "-x"], ["rm", "-f", state_file]]
    else:
        return [["gammastep", "-O", "3500"], ["touch", state_file]]

def action_es():
    run_threaded_action(["/usr/bin/cerrar_apps.sh"])
    kill_es_de()
    run_fast(["es-de", "--force-kiosk", "--no-splash", "--no-update-check"])
    return "exit"

def action_files():
    register_app("dolphin")
    run_fast(["flatpak", "run", "org.kde.dolphin"])
    return "exit"

def action_discord():
    register_app("Discord")
    run_fast(["flatpak", "run", "--branch=stable", "--arch=x86_64", "com.discordapp.Discord"])
    return "exit"

def action_wifi():
    run_fast(["python3", "/home/muser/ROMs/system/WiFi.sh" ])
    return "exit"

def action_bt():
    run_fast(["python3", "/home/muser/ROMs/system/Bluetooth.sh" ])
    return "exit"

def action_spotify():
    run_fast(["python3", "/home/muserROMs/multimedia/Spotify.sh"])
    return "exit"

def action_reboot():
    status = get_update_status()
    if status:
        return {
            "warning": f"El sistema está en actualización o con estado especial:\n{status}\n\n¿Reiniciar igualmente?",
            "cmd": ["systemctl", "reboot"],
        }

    run_fast(["systemctl", "reboot"])
    return "exit"


def action_shutdown():
    status = get_update_status()
    if status:
        return {
            "warning": f"El sistema está en actualización o con estado especial:\n{status}\n\n¿Apagar igualmente?",
            "cmd": ["systemctl", "poweroff"],
        }

    run_fast(["systemctl", "poweroff"])
    return "exit"


def action_back(): return "exit"

# ==========================================
# 📋 DEFINICIÓN DEL MENÚ
# ==========================================

MENU_ITEMS = [
    {"type": "header", "label": "APLICACIONES"},
    {"icon": {"nf": "󰔟", "fallback": ""}, "label": "Volver al menu principal", "desc": "Cerrar aplicaciones y volver", "fn": action_es},
    {"icon": {"nf": "󰉋", "fallback": "📁"}, "label": "Explorador de Archivos", "desc": "Gestionar archivos", "fn": action_files},
    {"icon": {"nf": "󰙯", "fallback": "💬"}, "label": "Discord", "desc": "Abrir chat de voz", "fn": action_discord},
    {"icon": {"nf": "󰙯", "fallback": "💬"}, "label": "Spotify", "desc": "Abrir reproductor de música", "fn": action_spotify},

    {"type": "header", "label": "SISTEMA"},
    {"icon": {"nf": "󰊴", "fallback": "🎮"}, "label": "Salir del menu", "desc": "Ocultar menú", "fn": action_back},
    {"icon": {"nf": "󰕾", "fallback": "🔊"}, "label": "Subir Volumen", "desc_fn": get_volume_text, "fn": action_vol_up, "tag": "volume"},
    {"icon": {"nf": "󰕿", "fallback": "🔉"}, "label": "Bajar Volumen", "desc_fn": get_volume_text, "fn": action_vol_down, "tag": "volume"},
    {"icon": {"nf": "󰖩", "fallback": "📶"}, "label": "Wi-Fi", "desc_fn": get_wifi_text, "fn": action_wifi},
    {"icon": {"nf": "󰂯", "fallback": "📡"}, "label": "Bluetooth", "desc_fn": get_bt_text, "fn": action_bt},

    {"type": "header", "label": "ENERGÍA"},
    {"icon": {"nf": "󰜉", "fallback": "♻️"}, "label": "Reiniciar", "desc": "Reboot system", "fn": action_reboot, "danger": True},
    {"icon": {"nf": "󰐥", "fallback": "⏻"}, "label": "Apagar", "desc": "Shutdown system", "fn": action_shutdown, "danger": True},
]

# ==========================================
# 🧩 COMPONENTES UI
# ==========================================

def pick_first_font(root, candidates):
    try:
        fam = set(tkfont.families(root))
        for c in candidates:
            if c in fam: return c
    except Exception: pass
    return None

def get_icon_text(data):
    ico = data.get("icon", "•")
    if isinstance(ico, dict):
        if globals().get("HAS_NERD_FONT", False) and ico.get("nf"):
            return ico.get("nf")
        return ico.get("fallback", "•")
    return ico

class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, width=50, height=26, bg=C_CARD_BG):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.state = False
        self.w, self.h = width, height

    def set_state(self, state):
        self.state = bool(state)
        self.draw()

    def draw(self):
        self.delete("all")
        track_col = ACCENT if self.state else BORDER
        pad = 4
        # Dibujar track
        self.create_oval(0, 0, self.h, self.h, fill=track_col, outline="")
        self.create_oval(self.w-self.h, 0, self.w, self.h, fill=track_col, outline="")
        self.create_rectangle(self.h/2, 0, self.w-self.h/2, self.h, fill=track_col, outline="")
        # Dibujar knob
        d = self.h - (pad*2)
        x = (self.w - d - pad) if self.state else pad
        self.create_oval(x, pad, x+d, pad+d, fill="#FFFFFF", outline="")

class DashboardCard(tk.Frame):
    def __init__(self, parent, data, font_main, font_sub, icon_font, on_click):
        super().__init__(parent, bg=C_BG_MAIN, highlightthickness=0)
        self.data = data
        self.on_click = on_click
        self.is_selected = False
        self.switch_widget = None
        self.icon_font = icon_font

        self.inner = tk.Frame(self, bg=C_CARD_BG, bd=0, highlightthickness=0)
        self.inner.pack(fill="x", pady=sc(2), padx=0, ipady=sc(8))

        # Icono
        self._setup_icon(data, font_main)

        # Contenedor de Texto
        self.text_frame = tk.Frame(self.inner, bg=C_CARD_BG)
        self.text_frame.pack(side="left", fill="both", expand=True)

        if data.get("switch"):
            self.switch_widget = ToggleSwitch(self.inner, width=sc(50), height=sc(26), bg=C_CARD_BG)
            self.switch_widget.pack(side="right", padx=sc(20))

        # Título
        fg_title = C_DANGER if data.get("danger") else C_TEXT_MAIN
        self.lbl_title = tk.Label(
            self.text_frame, text=data.get("label", ""),
            font=(font_main, fs(14), "bold"), bg=C_CARD_BG, fg=fg_title, anchor="w"
        )
        self.lbl_title.pack(fill="x", pady=(sc(2), 0))

        # Descripción
        init_desc = data.get("desc", "...")
        self.lbl_desc = tk.Label(
            self.text_frame, text=init_desc,
            font=(font_sub, fs(10)), bg=C_CARD_BG, fg=C_TEXT_SEC, anchor="w"
        )
        self.lbl_desc.pack(fill="x")

        # Event bindings
        widgets = [self.inner, self.icon_container, self.icon_lbl, self.text_frame, self.lbl_title, self.lbl_desc]
        if self.switch_widget: widgets.append(self.switch_widget)

        for w in widgets:
            if not w: continue
            w.bind("<Enter>", lambda e: self.set_highlight(True))
            w.bind("<Leave>", lambda e: self.set_highlight(False))
            w.bind("<Button-1>", lambda e: self.execute())

    def _setup_icon(self, data, font_fallback):
        icon_txt = get_icon_text(data)
        self.icon_container = tk.Frame(self.inner, bg=C_CARD_BG, width=sc(70), height=sc(52), bd=0, highlightthickness=0)
        self.icon_container.pack_propagate(False)
        self.icon_container.pack(side="left", padx=(sc(12), sc(10)), fill="y")

        self.icon_lbl = tk.Label(
            self.icon_container, text=icon_txt,
            font=(self.icon_font or font_fallback, fs(22)),
            bg=C_CARD_BG, fg=C_TEXT_MAIN, bd=0
        )
        self.icon_lbl.pack(expand=True)

    def update_data(self):
        if "desc_fn" in self.data:
            try: self.lbl_desc.config(text=self.data["desc_fn"]())
            except: pass
        if self.switch_widget and "switch_val" in self.data:
            try: self.switch_widget.set_state(self.data["switch_val"]())
            except: pass

    def set_highlight(self, active: bool):
        if self.is_selected == active: return
        self.is_selected = active
        bg = C_CARD_HOVER if active else C_CARD_BG
        if active and self.data.get("danger"): bg = C_DANGER

        self.inner.configure(bg=bg)
        if self.icon_container: self.icon_container.configure(bg=bg)
        self.icon_lbl.configure(bg=bg)
        if self.text_frame: self.text_frame.configure(bg=bg)

        base_title_fg = C_DANGER if self.data.get("danger") else C_TEXT_MAIN
        self.lbl_title.configure(bg=bg, fg=C_TEXT_MAIN if active else base_title_fg)
        self.lbl_desc.configure(bg=bg, fg=C_TEXT_MAIN if active else C_TEXT_SEC)

        if self.switch_widget:
            self.switch_widget.configure(bg=bg)
            self.switch_widget.draw()

    def execute(self):
        self.on_click(self)

# ==========================================
# 🖥️ APP PRINCIPAL (MAIN LOOP)
# ==========================================

class OverlayApp:
    def __init__(self):
        global UI_SCALE
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.configure(bg="black")
        
        # Estado del Joystick
        self._joy_last_nav = 0.0

        # --- FASE 1: LOADING ---
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        
        self.loading_img = None
        loading_path = os.path.join(ASSETS_DIR, "loading.png")
        if os.path.exists(loading_path):
            try:
                if HAS_PIL:
                    pil_img = Image.open(loading_path)
                    pil_img = pil_img.resize((self.sw, self.sh), Image.Resampling.LANCZOS)
                    self.loading_img = ImageTk.PhotoImage(pil_img)
                else:
                    raw_img = tk.PhotoImage(file=loading_path)
                    if self.sw > 1500: self.loading_img = raw_img.zoom(2)
                    else: self.loading_img = raw_img
            except Exception: pass

        self.loading_lbl = tk.Label(self.root, image=self.loading_img, bg="black", bd=0, anchor="center")
        self.loading_lbl.pack(fill="both", expand=True)

        try: self.root.attributes("-fullscreen", True)
        except: pass
        self.root.update()

        # --- FASE 2: CONSTRUCCIÓN INTERFAZ ---
        try: self.root.attributes("-alpha", WINDOW_ALPHA)
        except: pass

        UI_SCALE = max(1.0, min(min(self.sw/1920, self.sh/1080), 1.8))
        self.font = "Segoe UI" if os.name == "nt" else "Inter"
        
        self.main = tk.Frame(self.root, bg=C_BG_MAIN)
        
        # Fuentes
        self.font = pick_first_font(self.root, ["Inter", "Segoe UI", "Ubuntu", "DejaVu Sans"]) or self.font
        self.icon_font = pick_first_font(self.root, ["JetBrainsMono Nerd Font", "Symbols Nerd Font", "Nerd Font"]) or self.font
        
        global HAS_NERD_FONT
        HAS_NERD_FONT = any(k in (self.icon_font or "") for k in ["Nerd", "Symbols"])

        self._build_header()

        # Canvas con Scroll
        self.canvas = tk.Canvas(self.main, bg=C_BG_MAIN, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=sc(20), pady=sc(10))
        self.scroll_inner = tk.Frame(self.canvas, bg=C_BG_MAIN)
        self.win_id = self.canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")

        self.scroll_inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.cards = []
        self.idx = 0
        self._build_menu()

        # Pie de página
        tk.Label(self.main, text="ESC: Cerrar | ENTER: Seleccionar | JOYSTICK Compatible",
                 bg=C_BG_MAIN, fg="#444", font=(self.font, fs(10))).pack(side="bottom", pady=sc(20))

        # Bindings Teclado
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Up>", lambda e: self.move_sel(-1))
        self.root.bind("<Down>", lambda e: self.move_sel(1))
        self.root.bind("<Return>", lambda e: self.trigger())
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.update_vis()
        self.update_clock()
        self._start_socket()
        self._start_joystick_listener()

        self.root.after(0, self.refresh_all_cards)
        self.periodic_refresh()
        self.root.after(2000, self.reveal_menu_final)

    def show_warning(self, message, on_confirm):
        win = tk.Toplevel(self.root)
        win.title("Advertencia")
        win.configure(bg="#111111")
        win.transient(self.root)
        win.grab_set()

        w, h = 420, 200
        x = (self.sw - w) // 2
        y = (self.sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(
            win,
            text=message,
            fg="white",
            bg="#111111",
            font=(self.font, fs(12)),
            wraplength=w - 40,
            justify="left"
        ).pack(pady=20, padx=20)

        btn_frame = tk.Frame(win, bg="#111111")
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame,
            text="Cancelar",
            width=12,
            command=win.destroy
        ).pack(side="left", padx=10)

        def _confirm():
            win.destroy()
            on_confirm()

        tk.Button(
            btn_frame,
            text="Continuar",
            width=12,
            command=_confirm
        ).pack(side="right", padx=10)

    # ---------------------------
    # LÓGICA DE JOYSTICK CORREGIDA
    # ---------------------------
    def _joy_nav(self, direction):
        now = time.time()
        if (now - self._joy_last_nav) < JOY_NAV_COOLDOWN: return
        self._joy_last_nav = now
        self.root.after(0, lambda: (self.move_sel(direction), self._force_focus()))

    def _joy_select(self):
        self.root.after(0, lambda: (self.trigger(), self._force_focus()))

    def _joy_back(self):
        self.root.after(0, lambda: self.root.destroy())

    def _force_focus(self):
        try: self.root.focus_force()
        except: pass

    def _start_joystick_listener(self):
        if not HAS_EVDEV: return

        # Buscar dispositivos
        devices = []
        try:
            for path in list_devices():
                try:
                    d = InputDevice(path)
                    caps = d.capabilities(verbose=False)
                    if ecodes.EV_KEY in caps:
                        keys = caps[ecodes.EV_KEY]
                        if ecodes.BTN_SOUTH in keys or ecodes.BTN_GAMEPAD in keys:
                            devices.append(d)
                except: pass
        except: pass

        if not devices: return

        def worker(devs):
            sel = selectors.DefaultSelector()
            for d in devs:
                try: sel.register(d.fd, selectors.EVENT_READ, d)
                except: pass
            
            # Alias de códigos comunes
            BTN_ACCEPT = [ecodes.BTN_SOUTH, ecodes.BTN_A] # A, Start
            BTN_CANCEL = [ecodes.BTN_EAST, ecodes.BTN_B] # B
            
            ABS_Y = ecodes.ABS_Y
            ABS_HAT0Y = ecodes.ABS_HAT0Y

            while True:
                try:
                    events = sel.select(timeout=0.5)
                    for key, _ in events:
                        dev = key.data
                        for event in dev.read():
                            # 1. BOTONES
                            if event.type == ecodes.EV_KEY and event.value == 1: # Key Down
                                if event.code in BTN_ACCEPT:
                                    self._joy_select()
                                elif event.code in BTN_CANCEL:
                                    self._joy_back()
                                elif event.code == ecodes.BTN_THUMBL: # L3 Click
                                    self._joy_select()

                            # 2. EJES (D-PAD y Stick)
                            elif event.type == ecodes.EV_ABS:
                                val = event.value
                                code = event.code
                                
                                # D-PAD (Hat)
                                if code == ABS_HAT0Y:
                                    if val == -1: self._joy_nav(-1)
                                    elif val == 1: self._joy_nav(+1)
                                
                                # Analog Stick Y
                                elif code == ABS_Y:
                                    # Zona muerta simple
                                    if val < -JOY_AXIS_THRESHOLD: self._joy_nav(-1)
                                    elif val > JOY_AXIS_THRESHOLD: self._joy_nav(+1)
                                    # Soporte para pads 0..255 (estilo 8bitdo antiguos)
                                    elif 0 <= val <= 255:
                                        if val < 50: self._joy_nav(-1)
                                        elif val > 200: self._joy_nav(+1)
                except Exception:
                    time.sleep(1) # Si falla, espera un poco y sigue

        threading.Thread(target=worker, args=(devices,), daemon=True).start()

    # ---------------------------
    # LÓGICA DE UI
    # ---------------------------
    def reveal_menu_final(self):
        self.loading_lbl.pack_forget()
        self.main.place(relx=0.5, rely=0.5, anchor="center", width=sc(800), relheight=1.0)
        self.initial_position()

    def initial_position(self):
        self.idx = 0
        self.update_vis()
        self.scroll_to_top()

    def scroll_to_top(self):
        self._sync_scrollregion()
        self.canvas.yview_moveto(0.0)

    def _sync_scrollregion(self):
        self.scroll_inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.win_id, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_header(self):
        h = tk.Frame(self.main, bg=C_BG_MAIN)
        h.pack(fill="x", pady=(sc(40), sc(20)), padx=sc(20))
        tk.Label(h, text="M-OS | ODEON ", font=(self.font, fs(28), "bold"), fg=C_CARD_HOVER, bg=C_BG_MAIN).pack(side="left")
        self.clock = tk.Label(h, text="00:00", font=(self.font, fs(24)), fg=C_TEXT_MAIN, bg=C_BG_MAIN)
        self.clock.pack(side="right")

    def _build_menu(self):
        for item in MENU_ITEMS:
            if item.get("type") == "header":
                tk.Label(self.scroll_inner, text=item["label"], fg=C_CARD_HOVER, bg=C_BG_MAIN,
                         font=(self.font, fs(9), "bold")).pack(anchor="w", pady=(sc(15), sc(5)))
                tk.Frame(self.scroll_inner, bg="#333", height=1).pack(fill="x", pady=(0, sc(5)))
            else:
                c = DashboardCard(self.scroll_inner, item, self.font, self.font, self.icon_font, self.on_card_click)
                c.pack(fill="x", pady=sc(3))
                self.cards.append(c)
        tk.Frame(self.scroll_inner, bg=C_BG_MAIN, height=sc(50)).pack(fill="x")

    def move_sel(self, d):
        if not self.cards: return
        n = len(self.cards)
        prev = self.idx
        if WRAP_AROUND: self.idx = (self.idx + d) % n
        else: self.idx = max(0, min(n - 1, self.idx + d))
        
        if self.idx != prev:
            self.update_vis()
            self.ensure_visible()

    def ensure_visible(self):
        if not self.cards: return
        card = self.cards[self.idx]
        self._sync_scrollregion()
        
        c_h = self.canvas.winfo_height()
        i_h = self.scroll_inner.winfo_height()
        if i_h <= c_h: return

        card_y = card.winfo_y()
        card_h = card.winfo_height()
        
        # Centrar selección
        target = card_y + (card_h / 2) - (c_h / 2)
        max_scroll = i_h - c_h
        
        if target < 0: target = 0
        if target > max_scroll: target = max_scroll
        
        frac = target / max_scroll if max_scroll > 0 else 0
        self.canvas.yview_moveto(frac)

    def update_vis(self):
        for i, c in enumerate(self.cards):
            c.set_highlight(i == self.idx)

    def trigger(self):
        if self.cards: self.cards[self.idx].execute()

    def _execute_final_action(self, card):
        fn = card.data["fn"]
        res = fn()
        if res == "exit":
            self.root.destroy()

    def on_card_click(self, card):
        fn = card.data["fn"]
        res = fn()

        # --- NUEVO: warning de actualización ---
        if isinstance(res, dict) and "warning" in res:
            msg = res["warning"]
            cmd = res.get("cmd")

            def do_cmd():
                if cmd:
                    run_fast(cmd)
                self.root.destroy()

            self.show_warning(msg, do_cmd)
            return

        # Lo que ya tenías:
        if isinstance(res, dict) and "dummy_cmd" in res:
            self.root.withdraw()
            def runner():
                try: subprocess.run(res["dummy_cmd"], check=False)
                except: pass
                self.root.after(0, self.root.deiconify)
                self.root.after(0, lambda: self.root.attributes("-fullscreen", True))
                self.root.after(0, self._force_focus)
            threading.Thread(target=runner, daemon=True).start()
            return

        if res == "exit":
            self.root.destroy()
        elif isinstance(res, list):
            tag = card.data.get("tag")
            run_threaded_action(res, on_finish=lambda: self.root.after(0, self.refresh_all_cards))


    def refresh_all_cards(self):
        for c in self.cards: c.update_data()
        try: self.root.update_idletasks()
        except: pass

    def periodic_refresh(self):
        self.refresh_all_cards()
        self.root.after(2500, self.periodic_refresh)

    def update_clock(self):
        self.clock.config(text=time.strftime("%H:%M"))
        self.root.after(1000, self.update_clock)

    def _start_socket(self):
        p = "/tmp/mos_overlay.sock"
        if os.path.exists(p):
            try: os.unlink(p)
            except: pass

        def srv():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(p)
            s.listen(1)
            try: os.chmod(p, 0o666)
            except: pass
            while True:
                try:
                    c, _ = s.accept()
                    msg = c.recv(1024).decode(errors="ignore")
                    if "toggle" in msg:
                        self.root.after(0, lambda: self.root.withdraw() if self.root.state() == "normal" else self.root.deiconify())
                    c.close()
                except: pass
        threading.Thread(target=srv, daemon=True).start()

if __name__ == "__main__":
    if "--toggle" in sys.argv:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect("/tmp/mos_overlay.sock")
            s.sendall(b"toggle")
            s.close()
        except: pass
        sys.exit()

    OverlayApp().root.mainloop()