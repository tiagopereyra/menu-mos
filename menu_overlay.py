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

# =========================
# CONFIG COMPORTAMIENTO
# =========================
WRAP_AROUND = False  # <- CAMBIÁ a True si querés que vuelva arriba/abajo al pasar el límite

# ================================
# ARCHIVO GLOBAL DE ESTADO DE APPS 
# ================================

def register_app(identifier, path="/tmp/open_apps"):
    # Crear el archivo si no existe
    if not os.path.exists(path):
        with open(path, "w") as f:
            pass  # crea el archivo vacío

    # Agregar el identificador al archivo
    with open(path, "a") as f:
        f.write(str(identifier) + "\n")


# ==========================================
# 🔎 LECTURA DE ESTADO
# ==========================================

def get_volume_text():
    try:
        # timeout corto para evitar que el refresh del UI se congele si pactl se cuelga
        res = subprocess.check_output(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            text=True,
            timeout=1
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
        if max_b == 0:
            return "Brillo: --"
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
# 🎨 CONFIGURACIÓN VISUAL
# ==========================================

APP_TITLE = "M-OS Overlay"
WINDOW_ALPHA = 1.0  # más estable (evita glitches en algunos compositores)

C_BG_MAIN = "#000000"
C_CARD_BG = "#111111"
C_CARD_HOVER = "#1E6BFF"
C_TEXT_MAIN = "#FFFFFF"
C_TEXT_SEC = "#AAAAAA"
C_DANGER = "#CF0000"
ACCENT = "#22c55e"
BORDER = "#333333"

UI_SCALE = 1.0
ICON_SIZE_BASE = 48

HAS_NERD_FONT = False

def sc(x: int) -> int: return max(1, int(x * UI_SCALE))
def fs(x: int) -> int: return max(10, int(x * UI_SCALE))
def get_icon_size() -> int: return max(24, int(ICON_SIZE_BASE * UI_SCALE))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


# ==========================================
# 🔤 ICONOS (Emoji / Nerd Fonts)
# ==========================================

def pick_first_font(root, candidates):
    try:
        fam = set(tkfont.families(root))
        for c in candidates:
            if c in fam:
                return c
    except Exception:
        pass
    return None

def get_icon_text(data):
    """
    Permite:
      - data["icon"] = "texto"
      - data["icon"] = {"nf": "...", "fallback": "..."}
    """
    ico = data.get("icon", "•")
    if isinstance(ico, dict):
        # Si hay nerdfont disponible, elegimos nf, sino fallback
        if globals().get("HAS_NERD_FONT", False) and ico.get("nf"):
            return ico.get("nf")
        return ico.get("fallback", "•")
    return ico

# ==========================================
# ⚙️ EJECUCIÓN
# ==========================================

def run_fast(cmd):
    try:
        subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        print(f"[Err] {cmd}: {e}")

def run_threaded_action(cmd_list, on_finish=None):
    def worker():
        for cmd in cmd_list:
            try:
                subprocess.run(cmd, check=True, timeout=1)
            except Exception:
                pass
        if on_finish:
            on_finish()
    threading.Thread(target=worker, daemon=True).start()

# --- ACCIONES ---

UID = os.getuid()
PULSE_SOCKET = f"unix:/run/user/{UID}/pulse/native"

def action_vol_up():
    return [["pactl", "--server", PULSE_SOCKET,
             "set-sink-volume", "@DEFAULT_SINK@", "+5%"]]
def action_vol_down():
    return [["pactl", "--server", PULSE_SOCKET,
             "set-sink-volume", "@DEFAULT_SINK@", "-5%"]]
def action_bri_up(): return [["brightnessctl", "set", "5%+"], ["light", "-A", "5"]]
def action_bri_down(): return [["brightnessctl", "set", "5%-"], ["light", "-U", "5"]]

def action_toggle_night_light():
    state_file = "/tmp/nightlight_state"

    if os.path.exists(state_file):
        return [
            ["gammastep", "-x"],
            ["rm", "-f", state_file]
        ]
    else:
        return [
            ["gammastep", "-O", "3500"],
            ["touch", state_file]
        ]

def action_es():
    run_threaded_action(["/usr/bin/cerrar_apps.sh"])
    run_fast(["es-de", "--force-kiosk", "--no-splash", "--no-update-check"])
    return "exit"
def action_files():
    register_app("dolphin") 
    run_fast(["flatpak", "run", "org.kde.dolphin"]); return "exit"
def action_back(): return "exit"
def action_discord(): run_fast([ "flatpak", "run", "--branch=stable", "--arch=x86_64", "com.discordapp.Discord" ]); return "exit"


def action_wifi():
    # Abrimos el dummy y al cerrarlo volvemos automáticamente al menú
    return {"dummy_cmd": [sys.executable, os.path.join(BASE_DIR, "dummy_settings.py"), "wifi"]}

def action_bt():
    # Abrimos el dummy y al cerrarlo volvemos automáticamente al menú
    return {"dummy_cmd": [sys.executable, os.path.join(BASE_DIR, "dummy_settings.py"), "bluetooth"]}

def action_reboot(): run_fast(["systemctl", "reboot"])
def action_shutdown(): run_fast(["systemctl", "poweroff"])

# ==========================================
# 📋 MENÚ
# ==========================================

MENU_ITEMS = [
    {"type": "header", "label": "APLICACIONES"},
    {"icon": {"nf": "󰔟", "fallback": ""}, "label": "Volver al menu principal", "desc": "Cerrar aplicaciones y volver al menu", "fn": action_es},
    {"icon": {"nf": "󰉋", "fallback": "📁"}, "label": "Explorador de Archivos", "desc": "Gestionar archivos", "fn": action_files},
    {"icon": {"nf": "󰙯", "fallback": "💬"}, "label": "Discord", "desc": "Abrir chat de voz", "fn": action_discord},

    {"type": "header", "label": "SISTEMA"},
    {"icon": {"nf": "󰊴", "fallback": "🎮"}, "label": "Salir del menu", "desc": "Ocultar menú", "fn": action_back},

    {"icon": {"nf": "󰕾", "fallback": "🔊"}, "label": "Subir Volumen", "desc_fn": get_volume_text, "fn": action_vol_up, "tag": "volume"},
    {"icon": {"nf": "󰕿", "fallback": "🔉"}, "label": "Bajar Volumen", "desc_fn": get_volume_text, "fn": action_vol_down, "tag": "volume"},

    {"icon": {"nf": "󰛨", "fallback": "🌙"}, "label": "Filtro Luz Azul", "desc": "Descanso visual",
     "fn": action_toggle_night_light, "tag": "night", "switch": True, "switch_val": get_night_light_state},

    {"icon": {"nf": "󰖩", "fallback": "📶"}, "label": "Wi-Fi", "desc_fn": get_wifi_text, "fn": action_wifi},
    {"icon": {"nf": "󰂯", "fallback": "📡"}, "label": "Bluetooth", "desc_fn": get_bt_text, "fn": action_bt},

    {"type": "header", "label": "ENERGÍA"},
    {"icon": {"nf": "󰜉", "fallback": "♻️"}, "label": "Reiniciar", "desc": "Reboot system", "fn": action_reboot, "danger": True},
    {"icon": {"nf": "󰐥", "fallback": "⏻"}, "label": "Apagar", "desc": "Shutdown system", "fn": action_shutdown, "danger": True},
]

# ==========================================
# 🧩 UI COMPONENTS
# ==========================================

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
        self.create_oval(0, 0, self.h, self.h, fill=track_col, outline="")
        self.create_oval(self.w-self.h, 0, self.w, self.h, fill=track_col, outline="")
        self.create_rectangle(self.h/2, 0, self.w-self.h/2, self.h, fill=track_col, outline="")
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
        self.icon_container = None

        self.inner = tk.Frame(self, bg=C_CARD_BG, bd=0, highlightthickness=0)
        self.inner.pack(fill="x", pady=sc(2), padx=0, ipady=sc(8))

        # Icono (texto / Nerd Font / emoji) dentro de contenedor fijo (evita "escalones")
        self._setup_icon(data, font_main)

        self.text_frame = tk.Frame(self.inner, bg=C_CARD_BG)
        self.text_frame.pack(side="left", fill="both", expand=True)

        if data.get("switch"):
            self.switch_widget = ToggleSwitch(self.inner, width=sc(50), height=sc(26), bg=C_CARD_BG)
            self.switch_widget.pack(side="right", padx=sc(20))

        fg_title = C_DANGER if data.get("danger") else C_TEXT_MAIN
        self.lbl_title = tk.Label(
            self.text_frame,
            text=data.get("label", ""),
            font=(font_main, fs(14), "bold"),
            bg=C_CARD_BG,
            fg=fg_title,
            anchor="w"
        )
        self.lbl_title.pack(fill="x", pady=(sc(2), 0))

        init_desc = data.get("desc", "...")
        self.lbl_desc = tk.Label(
            self.text_frame,
            text=init_desc,
            font=(font_sub, fs(10)),
            bg=C_CARD_BG,
            fg=C_TEXT_SEC,
            anchor="w"
        )
        self.lbl_desc.pack(fill="x")

        # Bind hover/click en todos los widgets relevantes
        widgets = [self.inner, self.icon_container, self.icon_lbl, self.text_frame, self.lbl_title, self.lbl_desc]
        if self.switch_widget:
            widgets.append(self.switch_widget)

        for w in widgets:
            if not w:
                continue
            w.bind("<Enter>", lambda e: self.set_highlight(True))
            w.bind("<Leave>", lambda e: self.set_highlight(False))
            w.bind("<Button-1>", lambda e: self.execute())

    def _setup_icon(self, data, font_fallback):
        # Solo iconos en texto (emoji o Nerd Font). Sin imágenes.
        icon_txt = get_icon_text(data)

        # Contenedor fijo para evitar "escalones"
        self.icon_container = tk.Frame(
            self.inner, bg=C_CARD_BG, width=sc(70), height=sc(52), bd=0, highlightthickness=0
        )
        self.icon_container.pack_propagate(False)
        self.icon_container.pack(side="left", padx=(sc(12), sc(10)), fill="y")

        self.icon_lbl = tk.Label(
            self.icon_container,
            text=icon_txt,
            font=(self.icon_font or font_fallback, fs(22)),
            bg=C_CARD_BG,
            fg=C_TEXT_MAIN,
            bd=0
        )
        self.icon_lbl.pack(expand=True)

    def update_data(self):
        if "desc_fn" in self.data:
            try:
                self.lbl_desc.config(text=self.data["desc_fn"]())
            except Exception:
                pass
        if self.switch_widget and "switch_val" in self.data:
            try:
                self.switch_widget.set_state(self.data["switch_val"]())
            except Exception:
                pass
        try:
            self.inner.update_idletasks()
        except Exception:
            pass

    def set_highlight(self, active: bool):
        if self.is_selected == active:
            return
        self.is_selected = active

        bg = C_CARD_HOVER if active else C_CARD_BG
        if active and self.data.get("danger"):
            bg = C_DANGER

        # Pintar TODO (inner + icon container + texto) igual, para que no haya "recuadros"
        self.inner.configure(bg=bg)
        if self.icon_container:
            self.icon_container.configure(bg=bg)
        self.icon_lbl.configure(bg=bg)
        if self.text_frame:
            self.text_frame.configure(bg=bg)

        # Texto
        base_title_fg = C_DANGER if self.data.get("danger") else C_TEXT_MAIN
        self.lbl_title.configure(bg=bg, fg=C_TEXT_MAIN if active else base_title_fg)
        self.lbl_desc.configure(bg=bg, fg=C_TEXT_MAIN if active else C_TEXT_SEC)

        # Switch
        if self.switch_widget:
            self.switch_widget.configure(bg=bg)
            self.switch_widget.draw()

    def execute(self):
        self.on_click(self)


# ==========================================
# 🖥️ APP PRINCIPAL
# ==========================================

class OverlayApp:
    def __init__(self):
        global UI_SCALE
        self.root = tk.Tk()
        self.root.title(APP_TITLE)

        self.root.withdraw()
        self.root.configure(bg=C_BG_MAIN)
        try:
            self.root.attributes("-alpha", WINDOW_ALPHA)
        except:
            pass

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        UI_SCALE = max(1.0, min(min(sw/1920, sh/1080), 1.8))
        self.font = "Segoe UI" if os.name == "nt" else "Inter"

        # Fuente principal + fuente para iconos (Nerd Font si existe)
        main_candidates = ["Inter", "Segoe UI", "DejaVu Sans", "Ubuntu", "Noto Sans"]
        icon_candidates = [
            "JetBrainsMono Nerd Font", "FiraCode Nerd Font", "Hack Nerd Font",
            "Symbols Nerd Font Mono", "Symbols Nerd Font", "Nerd Font"
        ]

        self.font = pick_first_font(self.root, main_candidates) or self.font
        self.icon_font = pick_first_font(self.root, icon_candidates) or self.font

        global HAS_NERD_FONT
        HAS_NERD_FONT = any(k in (self.icon_font or "") for k in ["Nerd", "Symbols"])
        self.main = tk.Frame(self.root, bg=C_BG_MAIN)
        self.main.place(relx=0.5, rely=0.5, anchor="center", width=sc(800), relheight=1.0)

        self._build_header()

        self.canvas = tk.Canvas(self.main, bg=C_BG_MAIN, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=sc(20), pady=sc(10))
        self.scroll_inner = tk.Frame(self.canvas, bg=C_BG_MAIN)
        self.win_id = self.canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")

        self.scroll_inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.cards = []
        self.idx = 0
        self._build_menu()

        tk.Label(self.main, text="ESC: Cerrar  |  ENTER: Seleccionar  |  CONTROL+M: Abrir el menu",
                 bg=C_BG_MAIN, fg="#444", font=(self.font, fs(10))).pack(side="bottom", pady=sc(20))

        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Up>", lambda e: self.move_sel(-1))
        self.root.bind("<Down>", lambda e: self.move_sel(1))
        self.root.bind("<Return>", lambda e: self.trigger())
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.update_vis()
        self.update_clock()
        self._start_socket()

        self.root.after(0, self.refresh_all_cards)
        self.periodic_refresh()

        self.root.after(2000, self.reveal_window)

    def _sync_scrollregion(self):
        self.scroll_inner.update_idletasks()
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def scroll_to_top(self):
        self._sync_scrollregion()
        self.canvas.yview_moveto(0.0)

    def initial_position(self):
        self.idx = 0
        self.update_vis()
        self.scroll_to_top()

    def reveal_window(self):
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)
        self.root.after(80, self.initial_position)

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.win_id, width=event.width)

    def refresh_all_cards(self):
        for c in self.cards:
            try:
                c.update_data()
            except:
                pass
        try:
            self.root.update_idletasks()
        except:
            pass

    def periodic_refresh(self):
        self.refresh_all_cards()
        self.root.after(2500, self.periodic_refresh)

    def _on_mousewheel(self, event):
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except:
            pass

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

    def on_card_click(self, card):
        fn = card.data["fn"]
        res = fn()

        # Caso especial: dummy settings (Wi-Fi / Bluetooth)
        if isinstance(res, dict) and res.get("dummy_cmd"):
            dummy_cmd = res["dummy_cmd"]
            prev_idx = self.idx

            # ocultamos el overlay mientras está el dummy
            self.root.withdraw()

            try:
                proc = subprocess.Popen(dummy_cmd, start_new_session=True)
            except Exception:
                # si falla, volvemos al menú igual
                self.root.deiconify()
                self.root.attributes("-fullscreen", True)
                self.idx = prev_idx
                self.update_vis()
                self.ensure_visible()
                return

            def waiter():
                try:
                    proc.wait()
                except Exception:
                    pass

                def reopen_menu():
                    # volver automáticamente al menú
                    self.root.deiconify()
                    try:
                        self.root.attributes("-fullscreen", True)
                    except:
                        pass
                    self.idx = prev_idx
                    self.update_vis()
                    self.ensure_visible()
                    try:
                        self.root.lift()
                        self.root.focus_force()
                    except:
                        pass

                self.root.after(0, reopen_menu)

            threading.Thread(target=waiter, daemon=True).start()
            return

        # Caso especial: comandos que deben 'esperar' (p.ej. Explorador)
        if isinstance(res, dict) and res.get("wait_cmd"):
            cmd = res["wait_cmd"]
            prev_idx = self.idx
            self.root.withdraw()

            try:
                proc = subprocess.Popen(cmd, start_new_session=True)
            except Exception:
                # Si falla, volvemos al menú igual
                self.root.deiconify()
                try:
                    self.root.attributes("-fullscreen", True)
                except:
                    pass
                self.idx = prev_idx
                self.update_vis()
                self.ensure_visible()
                return

            def waiter():
                try:
                    proc.wait()
                except Exception:
                    pass

                def reopen_menu():
                    self.root.deiconify()
                    try:
                        self.root.attributes("-fullscreen", True)
                    except:
                        pass
                    self.idx = prev_idx
                    self.update_vis()
                    self.ensure_visible()
                    try:
                        self.root.lift()
                        self.root.focus_force()
                    except:
                        pass

                self.root.after(0, reopen_menu)

            threading.Thread(target=waiter, daemon=True).start()
            return


        if res == "hide":
            self.root.withdraw()
            return

        if res == "exit":
            self.root.destroy()
            return

        if isinstance(res, list):
            tag = card.data.get("tag")

            def on_done_ui():
                if tag:
                    self.refresh_all_cards()

            run_threaded_action(res, on_finish=lambda: self.root.after(0, on_done_ui))

    def update_clock(self):
        self.clock.config(text=time.strftime("%H:%M"))
        self.root.after(1000, self.update_clock)

    # ✅ FIX DEFINITIVO: SIN WRAP (no salta arriba/abajo)
    def move_sel(self, d):
        if not self.cards:
            return

        n = len(self.cards)
        prev = self.idx

        if WRAP_AROUND:
            self.idx = (self.idx + d) % n
        else:
            # clamp
            self.idx = max(0, min(n - 1, self.idx + d))

        if self.idx == prev:
            return  # no cambió, no hacer nada

        self.update_vis()
        self.ensure_visible()

    def ensure_visible(self):
        if not self.cards:
            return
        card = self.cards[self.idx]

        self._sync_scrollregion()
        canvas_h = self.canvas.winfo_height()
        inner_h = self.scroll_inner.winfo_height()
        if inner_h <= canvas_h:
            return

        card_y = card.winfo_y()
        card_h = card.winfo_height()

        target_center = card_y + (card_h / 2)
        view_top = target_center - (canvas_h / 2)

        max_scroll = inner_h - canvas_h
        if view_top < 0:
            view_top = 0
        if view_top > max_scroll:
            view_top = max_scroll

        fraction = 0.0 if max_scroll <= 0 else (view_top / max_scroll)
        self.canvas.yview_moveto(max(0.0, min(1.0, fraction)))

    def update_vis(self):
        for i, c in enumerate(self.cards):
            c.set_highlight(i == self.idx)

    def trigger(self):
        self.cards[self.idx].execute()

    def _start_socket(self):
        p = "/tmp/mos_overlay.sock"
        if os.path.exists(p):
            try:
                os.unlink(p)
            except:
                pass

        def srv():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(p)
            s.listen(1)
            try:
                os.chmod(p, 0o666)
            except:
                pass

            while True:
                try:
                    c, _ = s.accept()
                    msg = c.recv(1024).decode(errors="ignore")
                    if "toggle" in msg:
                        def do_toggle():
                            if self.root.state() == "withdrawn":
                                self.root.deiconify()
                                self.root.attributes("-fullscreen", True)
                                self.root.after(80, self.initial_position)
                            else:
                                self.root.withdraw()
                        self.root.after(0, do_toggle)
                    c.close()
                except:
                    pass

        threading.Thread(target=srv, daemon=True).start()

if __name__ == "__main__":
    if "--toggle" in sys.argv:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect("/tmp/mos_overlay.sock")
            s.sendall(b"toggle")
            s.close()
        except:
            pass
        sys.exit()

    OverlayApp().root.mainloop()

