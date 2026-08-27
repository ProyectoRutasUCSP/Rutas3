"""
Aplicación gráfica para controlar servomotores Dynamixel.
Ejecutar:
    python app.py
"""

from __future__ import annotations

import json
import math
import os
import queue
import threading
import time
import tkinter as tk
from dataclasses import asdict
from tkinter import messagebox, ttk
from typing import Callable, Dict, Optional
from motion_recorder import MotionRecorderPanel

from dxl_core import (
    DEFAULT_BAUDRATE,
    DEFAULT_PROTOCOL,
    MAX_PROFILE_VELOCITY,
    MIN_PROFILE_VELOCITY,
    DynamixelController,
    ServoConfig,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "servos_config.json")


class DxlWorker:
    """Ejecuta comandos Dynamixel en segundo plano para que Tkinter no se congele."""

    def __init__(self, app: "DynamixelApp") -> None:
        self.app = app
        self.jobs: "queue.Queue[tuple]" = queue.Queue()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def submit(self, label: str, func: Callable, callback: Optional[Callable] = None) -> None:
        self.jobs.put((label, func, callback))

    def _loop(self) -> None:
        while True:
            label, func, callback = self.jobs.get()
            try:
                result = func()
            except Exception as exc:
                result = (False, f"Error en '{label}': {exc}")
            self.app.after(0, self._finish, label, result, callback)

    def _finish(self, label: str, result, callback: Optional[Callable]) -> None:
        if callback:
            callback(result)
        else:
            self.app.log(str(result))


class RotaryKnob(tk.Canvas):
    def __init__(self, master, min_value=0, max_value=360, value=0, command=None, **kwargs):
        super().__init__(master, width=94, height=94, highlightthickness=0, bg=kwargs.pop("bg", "#111827"))
        self.min_value = min_value
        self.max_value = max_value
        self.value = value
        self.command = command
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.draw()

    def set_range(self, min_value, max_value):
        self.min_value = int(min_value)
        self.max_value = int(max_value)
        self.set_value(self.value, trigger=False)

    def set_value(self, value, trigger=False):
        self.value = int(max(self.min_value, min(self.max_value, round(value))))
        self.draw()
        if trigger and self.command:
            self.command(self.value)

    def _drag(self, event):
        cx, cy = 47, 47
        dx, dy = event.x - cx, cy - event.y
        angle = math.degrees(math.atan2(dy, dx))
        # Convierte el giro a un rango intuitivo 0-360 empezando desde abajo-izquierda aproximadamente.
        norm = (135 - angle) % 360
        if norm > 270:
            norm = 270
        value = self.min_value + (norm / 270.0) * (self.max_value - self.min_value)
        self.set_value(value, trigger=True)

    def draw(self):
        self.delete("all")
        self.create_oval(8, 8, 86, 86, fill="#1f2937", outline="#4b5563", width=2)
        self.create_oval(19, 19, 75, 75, fill="#111827", outline="#374151")
        self.create_text(47, 51, text=f"{self.value}°", fill="#e5e7eb", font=("Segoe UI", 11, "bold"))
        span = max(1, self.max_value - self.min_value)
        ratio = (self.value - self.min_value) / span
        theta = math.radians(135 - ratio * 270)
        x2 = 47 + 31 * math.cos(theta)
        y2 = 47 - 31 * math.sin(theta)
        self.create_line(47, 47, x2, y2, fill="#38bdf8", width=4, capstyle=tk.ROUND)
        self.create_oval(41, 41, 53, 53, fill="#38bdf8", outline="")


class ServoCard(ttk.Frame):
    def __init__(self, app: "DynamixelApp", parent, cfg: ServoConfig, index: int):
        super().__init__(parent, style="Card.TFrame", padding=12)
        self.app = app
        self.cfg = cfg
        self.index = index
        self._debounce_after = None
        # Evita recursión: en Tkinter, cambiar un Scale con .set()
        # puede disparar de nuevo su command/callback.
        self._updating_ui = False
        # Movimiento fluido: no acumulamos todos los puntos del slider.
        # Si el usuario arrastra rápido, guardamos solo el último objetivo
        # y lo enviamos cuando el bus quede libre.
        self._move_in_progress = False
        self._pending_move = False
        self._last_sent_angle = None
        self._last_sent_velocity = None
        self.angle_var = tk.IntVar(value=cfg.min_angle)
        self.velocity_var = tk.IntVar(value=cfg.velocity)
        self.status_var = tk.StringVar(value="Sin verificar")
        self._build()

    def _build(self):
        header = ttk.Frame(self, style="Card.TFrame")
        header.grid(row=0, column=0, columnspan=6, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=f"Servo ID {self.cfg.servo_id}", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="⚙", width=3, command=self.open_settings).grid(row=0, column=1, padx=2)
        ttk.Button(header, text="✕", width=3, command=self.remove).grid(row=0, column=2, padx=2)

        self.knob = RotaryKnob(self, self.cfg.min_angle, self.cfg.max_angle, self.angle_var.get(), command=self._from_knob)
        self.knob.grid(row=1, column=0, rowspan=4, padx=(0, 10), pady=8)

        ttk.Label(self, text="Ángulo", style="Small.TLabel").grid(row=1, column=1, sticky="w")
        self.angle_slider = ttk.Scale(
            self,
            from_=self.cfg.min_angle,
            to=self.cfg.max_angle,
            orient="horizontal",
            command=self._from_angle_slider,
        )
        self.angle_slider.set(self.angle_var.get())
        self.angle_slider.grid(row=1, column=2, columnspan=3, sticky="ew", padx=5)

        self.angle_spin = ttk.Spinbox(
            self,
            from_=self.cfg.min_angle,
            to=self.cfg.max_angle,
            textvariable=self.angle_var,
            width=7,
            command=self._from_spinbox,
        )
        self.angle_spin.grid(row=1, column=5, sticky="e")
        self.angle_spin.bind("<Return>", lambda _e: self._from_spinbox())
        self.angle_spin.bind("<FocusOut>", lambda _e: self._from_spinbox())

        ttk.Button(self, text="-10°", command=lambda: self.step(-10)).grid(row=2, column=1, sticky="ew", padx=2)
        ttk.Button(self, text="-1°", command=lambda: self.step(-1)).grid(row=2, column=2, sticky="ew", padx=2)
        ttk.Button(self, text="Centro", command=self.center).grid(row=2, column=3, sticky="ew", padx=2)
        ttk.Button(self, text="+1°", command=lambda: self.step(1)).grid(row=2, column=4, sticky="ew", padx=2)
        ttk.Button(self, text="+10°", command=lambda: self.step(10)).grid(row=2, column=5, sticky="ew", padx=2)

        ttk.Label(self, text="Velocidad", style="Small.TLabel").grid(row=3, column=1, sticky="w", pady=(8, 0))
        self.vel_slider = ttk.Scale(
            self,
            from_=MIN_PROFILE_VELOCITY,
            to=1000,
            orient="horizontal",
            command=self._from_velocity_slider,
        )
        self.vel_slider.set(self.velocity_var.get())
        self.vel_slider.grid(row=3, column=2, columnspan=3, sticky="ew", padx=5, pady=(8, 0))
        self.vel_spin = ttk.Spinbox(
            self,
            from_=MIN_PROFILE_VELOCITY,
            to=MAX_PROFILE_VELOCITY,
            textvariable=self.velocity_var,
            width=7,
            command=self._velocity_changed,
        )
        self.vel_spin.grid(row=3, column=5, sticky="e", pady=(8, 0))
        self.vel_spin.bind("<Return>", lambda _e: self._velocity_changed())
        self.vel_spin.bind("<FocusOut>", lambda _e: self._velocity_changed())

        actions = ttk.Frame(self, style="Card.TFrame")
        actions.grid(row=4, column=1, columnspan=5, sticky="ew", pady=(10, 2))
        for i in range(5):
            actions.columnconfigure(i, weight=1)
        ttk.Button(actions, text="Ping", command=self.ping).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(actions, text="Torque ON", command=lambda: self.torque(True)).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(actions, text="Torque OFF", command=lambda: self.torque(False)).grid(row=0, column=2, sticky="ew", padx=2)
        ttk.Button(actions, text="Leer", command=self.read_position).grid(row=0, column=3, sticky="ew", padx=2)
        ttk.Button(actions, text="Mover", command=lambda: self.send_move(immediate=True)).grid(row=0, column=4, sticky="ew", padx=2)

        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel").grid(row=5, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        for col in range(2, 5):
            self.columnconfigure(col, weight=1)

    def _set_status(self, text: str, ok: Optional[bool] = None):
        self.status_var.set(text)
        self.app.log(text)

    def _from_knob(self, value):
        self.set_angle(value, send=True)

    def _from_angle_slider(self, value):
        if self._updating_ui:
            return
        self.set_angle(float(value), send=True)

    def _from_spinbox(self):
        try:
            value = int(float(self.angle_var.get()))
        except Exception:
            value = self.cfg.min_angle
        self.set_angle(value, send=True)

    def _from_velocity_slider(self, value):
        if self._updating_ui:
            return
        self._updating_ui = True
        try:
            self.velocity_var.set(int(float(value)))
        finally:
            self._updating_ui = False
        self._velocity_changed(save_only=True)

    def _velocity_changed(self, save_only=False):
        if self._updating_ui:
            return
        try:
            value = int(float(self.velocity_var.get()))
        except Exception:
            value = self.cfg.velocity
        self.cfg.velocity = max(MIN_PROFILE_VELOCITY, min(MAX_PROFILE_VELOCITY, value))
        self._updating_ui = True
        try:
            self.velocity_var.set(self.cfg.velocity)
            if self.cfg.velocity <= 1000:
                self.vel_slider.set(self.cfg.velocity)
        finally:
            self._updating_ui = False
        self.app.save_config()

    def set_angle(self, value, send=False):
        value = self.cfg.clamp_angle(value)
        self._updating_ui = True
        try:
            self.angle_var.set(value)
            self.angle_slider.set(value)
            self.knob.set_value(value, trigger=False)
        finally:
            self._updating_ui = False
        if send:
            self.send_move(immediate=False)

    def step(self, delta):
        self.set_angle(self.angle_var.get() + delta, send=True)

    def center(self):
        self.set_angle((self.cfg.min_angle + self.cfg.max_angle) / 2, send=True)

    def send_move(self, immediate=False):
        # Modo fluido: manda objetivos con una pequeña frecuencia máxima.
        # No espera a que el usuario suelte el slider, pero tampoco satura el bus.
        if self._debounce_after is not None:
            self.after_cancel(self._debounce_after)
        delay = 0 if immediate else 25
        self._debounce_after = self.after(delay, self._send_move_now)

    def _send_move_now(self):
        self._debounce_after = None

        # Si hay una escritura serial en curso, no encolamos 20 comandos viejos.
        # Solo marcamos que existe un nuevo objetivo pendiente.
        if self._move_in_progress:
            self._pending_move = True
            return

        angle = self.cfg.clamp_angle(self.angle_var.get())
        velocity = self.cfg.clamp_velocity(self.velocity_var.get())

        # Evita enviar exactamente el mismo objetivo muchas veces.
        if angle == self._last_sent_angle and velocity == self._last_sent_velocity:
            return

        self.cfg.velocity = velocity
        self.app.save_config()
        self._last_sent_angle = angle
        self._last_sent_velocity = velocity
        self._move_in_progress = True
        self._set_status(f"Enviando ID {self.cfg.servo_id}: {angle}°, vel {velocity}...")
        self.app.worker.submit(
            f"move-{self.cfg.servo_id}",
            lambda: self.app.controller.move_to_angle(self.cfg, angle, velocity),
            self._after_move_result,
        )

    def _after_move_result(self, result):
        self._move_in_progress = False
        self._after_bool_result(result)

        if self._pending_move:
            self._pending_move = False
            # Enviar el último punto solicitado casi de inmediato.
            self._debounce_after = self.after(1, self._send_move_now)

    def ping(self):
        self._set_status(f"Verificando ID {self.cfg.servo_id}...")
        self.app.worker.submit(
            f"ping-{self.cfg.servo_id}",
            lambda: self.app.controller.ping(self.cfg.servo_id),
            lambda result: self._after_bool_result((result[0], result[1])),
        )

    def torque(self, enable):
        self.app.worker.submit(
            f"torque-{self.cfg.servo_id}",
            lambda: self.app.controller.enable_torque(self.cfg.servo_id, enable),
            self._after_bool_result,
        )

    def read_position(self):
        self.app.worker.submit(
            f"read-{self.cfg.servo_id}",
            lambda: self.app.controller.read_position(self.cfg),
            self._after_read,
        )

    def _after_bool_result(self, result):
        ok, msg = result[0], result[1]
        self._set_status(("✅ " if ok else "⚠️ ") + msg, ok)

    def _after_read(self, result):
        ok, msg, _pos, angle = result
        if ok and angle is not None:
            self.set_angle(angle, send=False)
        self._after_bool_result((ok, msg if angle is None else f"{msg} | Ángulo aprox: {angle}°"))

    def open_settings(self):
        ServoSettingsDialog(self.app, self)

    def apply_config(self, cfg: ServoConfig):
        self.cfg = cfg
        self.angle_slider.configure(from_=cfg.min_angle, to=cfg.max_angle)
        self.angle_spin.configure(from_=cfg.min_angle, to=cfg.max_angle)
        self.knob.set_range(cfg.min_angle, cfg.max_angle)
        self.set_angle(self.angle_var.get(), send=False)
        self._updating_ui = True
        try:
            self.velocity_var.set(cfg.velocity)
            if cfg.velocity <= 1000:
                self.vel_slider.set(cfg.velocity)
        finally:
            self._updating_ui = False
        self.app.rebuild_cards()
        self.app.save_config()

    def remove(self):
        if len(self.app.servo_cards) <= 1:
            messagebox.showinfo("Servo", "Debe quedar al menos un servo en pantalla.")
            return
        self.app.configs.pop(self.index)
        self.app.rebuild_cards()
        self.app.save_config()


class ServoSettingsDialog(tk.Toplevel):
    def __init__(self, app: "DynamixelApp", card: ServoCard):
        super().__init__(app)
        self.app = app
        self.card = card
        self.title(f"Configurar servo ID {card.cfg.servo_id}")
        self.resizable(False, False)
        self.configure(bg="#111827")
        self.vars: Dict[str, tk.StringVar] = {}
        self._build()
        self.transient(app)
        self.grab_set()
        self.wait_visibility()
        self.focus()

    def _build(self):
        box = ttk.Frame(self, padding=16, style="Card.TFrame")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        fields = [
            ("servo_id", "ID del servo", self.card.cfg.servo_id),
            ("min_angle", "Ángulo mínimo", self.card.cfg.min_angle),
            ("max_angle", "Ángulo máximo", self.card.cfg.max_angle),
            ("dxl_min", "Valor DXL mínimo", self.card.cfg.dxl_min),
            ("dxl_max", "Valor DXL máximo", self.card.cfg.dxl_max),
            ("velocity", "Velocidad inicial", self.card.cfg.velocity),
        ]
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(box, text=label, style="Small.TLabel").grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=str(value))
            self.vars[key] = var
            ttk.Entry(box, textvariable=var, width=14).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Button(box, text="Guardar", command=self.save).grid(row=len(fields), column=0, sticky="ew", pady=(12, 0))
        ttk.Button(box, text="Cancelar", command=self.destroy).grid(row=len(fields), column=1, sticky="ew", padx=(8, 0), pady=(12, 0))

    def save(self):
        try:
            data = {k: int(float(v.get())) for k, v in self.vars.items()}
            if data["servo_id"] < 0 or data["servo_id"] > 252:
                raise ValueError("El ID debe estar entre 0 y 252.")
            if data["max_angle"] <= data["min_angle"]:
                raise ValueError("El ángulo máximo debe ser mayor que el mínimo.")
            if data["dxl_max"] <= data["dxl_min"]:
                raise ValueError("El valor DXL máximo debe ser mayor que el mínimo.")
            cfg = ServoConfig(**data)
        except Exception as exc:
            messagebox.showerror("Configuración inválida", str(exc))
            return
        self.app.configs[self.card.index] = cfg
        self.destroy()
        self.app.rebuild_cards()
        self.app.save_config()


class DynamixelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control fluido de servomotores Dynamixel")
        self.geometry("1180x760")
        self.minsize(900, 620)
        self.configure(bg="#0f172a")
        self.controller = DynamixelController()
        self.worker = DxlWorker(self)
        self.configs = self.load_config()
        self.servo_cards = []
        self.port_var = tk.StringVar(value=self.controller.default_port())
        self.baud_var = tk.StringVar(value=str(DEFAULT_BAUDRATE))
        self.protocol_var = tk.StringVar(value=str(DEFAULT_PROTOCOL))
        self.status_var = tk.StringVar(value="Desconectado")
        self._setup_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#111827", relief="flat")
        style.configure("TLabel", background="#0f172a", foreground="#e5e7eb", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#111827", foreground="#f8fafc", font=("Segoe UI", 14, "bold"))
        style.configure("Small.TLabel", background="#111827", foreground="#cbd5e1", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background="#111827", foreground="#93c5fd", font=("Segoe UI", 9))
        style.configure("Header.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 18, "bold"))
        style.configure("TButton", font=("Segoe UI", 9), padding=5)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=7)
        style.configure("TEntry", padding=4)

    def _build_ui(self):
        top = ttk.Frame(self, padding=(14, 12))
        top.pack(fill="x")
        top.columnconfigure(9, weight=1)

        ttk.Label(top, text="Control Dynamixel", style="Header.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 18))
        ttk.Label(top, text="Puerto").grid(row=0, column=1, padx=(0, 5))
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, values=self.controller.available_ports(), width=14)
        self.port_combo.grid(row=0, column=2, padx=(0, 8))
        ttk.Button(top, text="↻", width=3, command=self.refresh_ports).grid(row=0, column=3, padx=(0, 8))

        ttk.Label(top, text="Baudrate").grid(row=0, column=4, padx=(0, 5))
        ttk.Entry(top, textvariable=self.baud_var, width=9).grid(row=0, column=5, padx=(0, 8))
        ttk.Label(top, text="Protocolo").grid(row=0, column=6, padx=(0, 5))
        ttk.Entry(top, textvariable=self.protocol_var, width=6).grid(row=0, column=7, padx=(0, 8))
        ttk.Button(top, text="Conectar", style="Accent.TButton", command=self.connect).grid(row=0, column=8, padx=(0, 6))
        ttk.Button(top, text="Desconectar", command=self.disconnect).grid(row=0, column=9, sticky="w")
        ttk.Label(top, textvariable=self.status_var).grid(row=0, column=10, sticky="e")

        toolbar = ttk.Frame(self, padding=(14, 0, 14, 10))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="+ Añadir servo", style="Accent.TButton", command=self.add_servo).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Escanear IDs 1-30", command=self.scan_ids).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Torque ON todos", command=lambda: self.torque_all(True)).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Torque OFF todos", command=lambda: self.torque_all(False)).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Guardar configuración", command=self.save_config).pack(side="left", padx=(0, 8))

        # ------------------------------------------------------------------
        # Panel adicional para grabar y reproducir acciones.
        #
        # Este panel permite:
        # - Capturar la posición real actual de todos los servos.
        # - Guardar una acción en acciones_guardadas.json.
        # - Reproducir una acción.
        # - Reproducir todas las acciones en secuencia.
        # ------------------------------------------------------------------
        self.motion_recorder = MotionRecorderPanel(self)
        self.motion_recorder.pack(fill="x", padx=14, pady=(0, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(body, bg="#0f172a", highlightthickness=0)
        self.cards_frame = ttk.Frame(self.canvas)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.cards_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        log_frame = ttk.Frame(self, padding=(14, 0, 14, 12))
        log_frame.pack(fill="x")
        ttk.Label(log_frame, text="Registro de eventos").pack(anchor="w")
        self.log_text = tk.Text(log_frame, height=6, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", relief="flat")
        self.log_text.pack(fill="x", expand=False)

        self.rebuild_cards()

    def _on_frame_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {text}\n")
        self.log_text.see("end")

    def refresh_ports(self):
        ports = self.controller.available_ports()
        self.port_combo.configure(values=ports)
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        self.log(f"Puertos detectados: {ports if ports else 'ninguno'}")

    def connect(self):
        try:
            baudrate = int(float(self.baud_var.get()))
            protocol = float(self.protocol_var.get())
        except Exception:
            messagebox.showerror("Datos inválidos", "Revisa baudrate y protocolo.")
            return
        self.status_var.set("Conectando...")
        self.worker.submit(
            "connect",
            lambda: self.controller.connect(self.port_var.get(), baudrate, protocol),
            self._after_connect,
        )

    def _after_connect(self, result):
        ok, msg = result
        self.status_var.set("Conectado" if ok else "Desconectado")
        self.log(("✅ " if ok else "⚠️ ") + msg)

    def disconnect(self):
        self.controller.disconnect()
        self.status_var.set("Desconectado")
        self.log("Puerto cerrado.")

    def scan_ids(self):
        self.log("Escaneando IDs del 1 al 30...")
        self.worker.submit("scan", lambda: self.controller.scan(1, 30), self._after_scan)

    def _after_scan(self, result):
        found, msg = result
        self.log(msg)
        if found:
            add = messagebox.askyesno("Servos encontrados", f"Se encontraron estos IDs: {found}\n\n¿Deseas añadirlos a la ventana?")
            if add:
                existing = {cfg.servo_id for cfg in self.configs}
                for servo_id in found:
                    if servo_id not in existing:
                        self.configs.append(ServoConfig(servo_id=servo_id))
                self.rebuild_cards()
                self.save_config()

    def torque_all(self, enable):
        for cfg in list(self.configs):
            self.worker.submit(
                f"torque-all-{cfg.servo_id}",
                lambda cfg=cfg: self.controller.enable_torque(cfg.servo_id, enable),
                lambda result: self.log(("✅ " if result[0] else "⚠️ ") + result[1]),
            )

    def add_servo(self):
        existing_ids = {cfg.servo_id for cfg in self.configs}
        new_id = 1
        while new_id in existing_ids:
            new_id += 1
        self.configs.append(ServoConfig(servo_id=new_id))
        self.rebuild_cards()
        self.save_config()

    def rebuild_cards(self):
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self.servo_cards = []
        for idx, cfg in enumerate(self.configs):
            card = ServoCard(self, self.cards_frame, cfg, idx)
            row = idx // 2
            col = idx % 2
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            self.cards_frame.columnconfigure(col, weight=1)
            self.servo_cards.append(card)

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return [ServoConfig(servo_id=1)]
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            configs = [ServoConfig(**item) for item in raw.get("servos", [])]
            return configs or [ServoConfig(servo_id=1)]
        except Exception:
            return [ServoConfig(servo_id=1)]

    def save_config(self):
        try:
            data = {"servos": [asdict(cfg) for cfg in self.configs]}
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.log("Configuración guardada.")
        except Exception as exc:
            self.log(f"No se pudo guardar la configuración: {exc}")

    def on_close(self):
        self.save_config()
        self.controller.disconnect()
        self.destroy()


if __name__ == "__main__":
    app = DynamixelApp()
    app.mainloop()
