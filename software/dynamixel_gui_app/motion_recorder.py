"""
motion_recorder.py

Grabador de acciones y posiciones para servomotores Dynamixel.

Nueva lógica:

- Acción:
    Es un conjunto de posiciones.
    Ejemplo: "Saludar", "Levantar brazo", "Girar cabeza".

- Posición:
    Es una captura de los ángulos reales actuales de todos los servos.
    Cada posición guarda:
        - ángulo de cada servo
        - valor DXL leído de cada servo
        - velocidad común para reproducir esa posición
        - delay posterior antes de pasar a la siguiente posición

Flujo de uso:

1. Crear una acción, por ejemplo: "Saludar".
2. Mover los servos desde la interfaz principal.
3. Presionar "+" para agregar una posición.
4. Mover nuevamente los servos.
5. Presionar "+" para agregar otra posición.
6. Seleccionar una posición si se desea modificar.
7. Presionar "Actualizar posición seleccionada" para chancar/sobrescribir esa posición.
8. Reproducir una posición o reproducir toda la acción.

Este archivo usa las funciones ya existentes del proyecto:

- app.controller.read_position(cfg)
- app.controller.move_to_angle(cfg, angle, velocity)
- app.worker.submit(...)
- app.servo_cards
- app.configs
- app.log(...)
"""

from __future__ import annotations

import json
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional


APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Archivo donde se guardan acciones y posiciones.
ACTIONS_FILE = os.path.join(APP_DIR, "acciones_guardadas.json")


class MotionRecorderPanel(ttk.Frame):
    """
    Panel visual para crear acciones, agregar posiciones,
    modificar posiciones y reproducir movimientos.
    """

    def __init__(self, app):
        """
        app:
            Es la instancia principal de DynamixelApp, definida en app.py.
        """
        super().__init__(app, padding=10, style="Card.TFrame")

        self.app = app

        # Lista de acciones cargadas desde acciones_guardadas.json.
        self.actions: List[dict] = []

        # Índice de la acción seleccionada actualmente.
        self.current_action_index: Optional[int] = None

        # Índice de la posición seleccionada actualmente.
        self.current_position_index: Optional[int] = None

        # Control de reproducción.
        self.is_playing = False
        self.stop_requested = False
        # Bandera para evitar que Tkinter borre la selección
        # cuando refrescamos las listas manualmente.
        self.refreshing_ui = False

        # Variables visuales.
        self.action_name_var = tk.StringVar(value="Saludar")
        self.position_velocity_var = tk.IntVar(value=120)
        self.position_delay_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="Crea o selecciona una acción.")

        self._build_ui()
        self.load_actions()
        self.refresh_actions_list()

    # ---------------------------------------------------------------------
    # Construcción de interfaz
    # ---------------------------------------------------------------------

    def _build_ui(self):
        """
        Construye toda la interfaz del grabador.
        """

        title = ttk.Label(
            self,
            text="Grabador de acciones y posiciones",
            style="Title.TLabel",
        )
        title.grid(row=0, column=0, columnspan=10, sticky="w", pady=(0, 8))

        # -----------------------------------------------------------------
        # Zona para crear/guardar acciones
        # -----------------------------------------------------------------

        ttk.Label(
            self,
            text="Acción:",
            style="Small.TLabel",
        ).grid(row=1, column=0, sticky="w")

        self.action_entry = ttk.Entry(
            self,
            textvariable=self.action_name_var,
            width=24,
        )
        self.action_entry.grid(row=1, column=1, sticky="ew", padx=(4, 8))

        self.new_action_button = ttk.Button(
            self,
            text="Crear / guardar acción",
            style="Accent.TButton",
            command=self.create_or_update_action,
        )
        self.new_action_button.grid(row=1, column=2, sticky="ew", padx=(0, 8))

        self.delete_action_button = ttk.Button(
            self,
            text="Eliminar acción",
            command=self.delete_selected_action,
        )
        self.delete_action_button.grid(row=1, column=3, sticky="ew", padx=(0, 8))

        self.reload_button = ttk.Button(
            self,
            text="Recargar JSON",
            command=self.reload_from_file,
        )
        self.reload_button.grid(row=1, column=4, sticky="ew", padx=(0, 8))

        # -----------------------------------------------------------------
        # Parámetros de cada posición
        # -----------------------------------------------------------------

        ttk.Label(
            self,
            text="Velocidad:",
            style="Small.TLabel",
        ).grid(row=1, column=5, sticky="w")

        self.velocity_spin = ttk.Spinbox(
            self,
            from_=1,
            to=1023,
            increment=5,
            textvariable=self.position_velocity_var,
            width=8,
        )
        self.velocity_spin.grid(row=1, column=6, sticky="w", padx=(4, 8))

        ttk.Label(
            self,
            text="Delay después ms:",
            style="Small.TLabel",
        ).grid(row=1, column=7, sticky="w")

        self.delay_spin = ttk.Spinbox(
            self,
            from_=0,
            to=30000,
            increment=100,
            textvariable=self.position_delay_var,
            width=8,
        )
        self.delay_spin.grid(row=1, column=8, sticky="w", padx=(4, 8))

        self.add_position_button = ttk.Button(
            self,
            text="+",
            style="Accent.TButton",
            width=4,
            command=self.add_position,
        )
        self.add_position_button.grid(row=1, column=9, sticky="ew")

        # -----------------------------------------------------------------
        # Listas: acciones y posiciones
        # -----------------------------------------------------------------

        ttk.Label(
            self,
            text="Acciones",
            style="Small.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 2))

        ttk.Label(
            self,
            text="Posiciones de la acción seleccionada",
            style="Small.TLabel",
        ).grid(row=2, column=3, columnspan=4, sticky="w", pady=(10, 2))

        ttk.Label(
            self,
            text="Detalle",
            style="Small.TLabel",
        ).grid(row=2, column=7, columnspan=3, sticky="w", pady=(10, 2))

        self.actions_listbox = tk.Listbox(
            self,
            height=6,
            bg="#020617",
            fg="#e5e7eb",
            selectbackground="#2563eb",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
            activestyle="none",
        )
        self.actions_listbox.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="nsew",
            padx=(0, 8),
        )
        self.actions_listbox.bind("<<ListboxSelect>>", self.on_action_selected)

        self.positions_listbox = tk.Listbox(
            self,
            height=6,
            bg="#020617",
            fg="#e5e7eb",
            selectbackground="#16a34a",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
            activestyle="none",
        )
        self.positions_listbox.grid(
            row=3,
            column=3,
            columnspan=4,
            sticky="nsew",
            padx=(0, 8),
        )
        self.positions_listbox.bind("<<ListboxSelect>>", self.on_position_selected)

        self.detail_text = tk.Text(
            self,
            height=6,
            bg="#020617",
            fg="#cbd5e1",
            insertbackground="#e5e7eb",
            relief="flat",
            wrap="word",
        )
        self.detail_text.grid(
            row=3,
            column=7,
            columnspan=3,
            sticky="nsew",
        )

        # -----------------------------------------------------------------
        # Botones de reproducción y modificación
        # -----------------------------------------------------------------

        self.update_position_button = ttk.Button(
            self,
            text="Actualizar posición seleccionada",
            command=self.update_selected_position,
        )
        self.update_position_button.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
            padx=(0, 6),
        )

        self.delete_position_button = ttk.Button(
            self,
            text="Eliminar posición",
            command=self.delete_selected_position,
        )
        self.delete_position_button.grid(
            row=4,
            column=2,
            sticky="ew",
            pady=(8, 0),
            padx=(0, 6),
        )

        self.play_position_button = ttk.Button(
            self,
            text="▶ Reproducir posición",
            command=self.play_selected_position,
        )
        self.play_position_button.grid(
            row=4,
            column=3,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
            padx=(0, 6),
        )

        self.play_action_button = ttk.Button(
            self,
            text="▶▶ Reproducir acción",
            style="Accent.TButton",
            command=self.play_selected_action,
        )
        self.play_action_button.grid(
            row=4,
            column=5,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
            padx=(0, 6),
        )

        self.stop_button = ttk.Button(
            self,
            text="Detener secuencia",
            command=self.stop_playback,
        )
        self.stop_button.grid(
            row=4,
            column=7,
            sticky="ew",
            pady=(8, 0),
            padx=(0, 6),
        )

        ttk.Label(
            self,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(
            row=4,
            column=8,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

        # Ajuste de columnas.
        self.columnconfigure(1, weight=1)
        self.columnconfigure(3, weight=1)
        self.columnconfigure(7, weight=1)
        self.rowconfigure(3, weight=1)

    # ---------------------------------------------------------------------
    # Carga y guardado JSON
    # ---------------------------------------------------------------------

    def load_actions(self):
        """
        Carga acciones desde acciones_guardadas.json.

        Formato usado:

        {
          "version": 2,
          "updated_at": "...",
          "actions": [
            {
              "name": "Saludar",
              "created_at": "...",
              "positions": [
                {
                  "name": "Posición 1",
                  "velocity": 120,
                  "delay_ms": 0,
                  "servos": {
                    "1": {"angle": 40, "dxl_position": 455},
                    "2": {"angle": 130, "dxl_position": 1479}
                  }
                }
              ]
            }
          ]
        }
        """

        if not os.path.exists(ACTIONS_FILE):
            self.actions = []
            self.status_var.set("No hay acciones guardadas todavía.")
            return

        try:
            with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_actions = data.get("actions", [])

            if not isinstance(raw_actions, list):
                raw_actions = []

            self.actions = raw_actions
            self.status_var.set(f"Acciones cargadas: {len(self.actions)}")

        except Exception as exc:
            self.actions = []
            self.status_var.set("Error al cargar acciones.")
            messagebox.showerror(
                "Error",
                f"No se pudo cargar acciones_guardadas.json:\n\n{exc}",
            )

    def save_actions(self):
        """
        Guarda todas las acciones en acciones_guardadas.json.
        """

        data = {
            "version": 2,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "actions": self.actions,
        }

        try:
            with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.status_var.set("Acciones guardadas.")
            self.app.log(f"✅ Acciones guardadas en {ACTIONS_FILE}")

        except Exception as exc:
            self.status_var.set("Error al guardar acciones.")
            messagebox.showerror(
                "Error",
                f"No se pudo guardar acciones_guardadas.json:\n\n{exc}",
            )

    def reload_from_file(self):
        """
        Recarga acciones desde el JSON.
        """
        self.load_actions()
        self.current_action_index = None
        self.current_position_index = None
        self.refresh_actions_list()
        self.refresh_positions_list()
        self.clear_detail()
        self.app.log("Archivo de acciones recargado.")

    # ---------------------------------------------------------------------
    # Manejo visual de listas
    # ---------------------------------------------------------------------

    def refresh_actions_list(self):
        """
        Actualiza la lista visual de acciones sin perder la selección actual.
        """

        self.refreshing_ui = True

        try:
            selected_index = self.current_action_index

            self.actions_listbox.delete(0, "end")

            for i, action in enumerate(self.actions):
                name = action.get("name", f"Acción {i + 1}")
                positions = action.get("positions", [])
                self.actions_listbox.insert(
                    "end",
                    f"{i + 1}. {name} | {len(positions)} posición(es)",
                )

            # Restaurar selección de acción si todavía existe.
            if selected_index is not None and 0 <= selected_index < len(self.actions):
                self.actions_listbox.selection_clear(0, "end")
                self.actions_listbox.selection_set(selected_index)
                self.actions_listbox.activate(selected_index)
                self.actions_listbox.see(selected_index)

        finally:
            self.refreshing_ui = False

    def refresh_positions_list(self):
        """
        Actualiza la lista de posiciones de la acción seleccionada
        sin perder la posición seleccionada.
        """

        self.refreshing_ui = True

        try:
            selected_position_index = self.current_position_index

            self.positions_listbox.delete(0, "end")

            action = self.get_current_action()
            if action is None:
                return

            positions = action.get("positions", [])

            for i, position in enumerate(positions):
                name = position.get("name", f"Posición {i + 1}")
                velocity = position.get("velocity", 120)
                delay_ms = position.get("delay_ms", 0)
                servos = position.get("servos", {})
                self.positions_listbox.insert(
                    "end",
                    f"{i + 1}. {name} | vel {velocity} | delay {delay_ms} ms | {len(servos)} servos",
                )

            # Restaurar selección de posición si todavía existe.
            if (
                selected_position_index is not None
                and 0 <= selected_position_index < len(positions)
            ):
                self.positions_listbox.selection_clear(0, "end")
                self.positions_listbox.selection_set(selected_position_index)
                self.positions_listbox.activate(selected_position_index)
                self.positions_listbox.see(selected_position_index)

        finally:
            self.refreshing_ui = False

    def clear_detail(self):
        """
        Limpia el cuadro de detalle.
        """
        self.detail_text.delete("1.0", "end")

    def show_position_detail(self, position: dict):
        """
        Muestra el detalle de una posición seleccionada.
        """
        self.clear_detail()

        name = position.get("name", "Posición")
        velocity = position.get("velocity", 120)
        delay_ms = position.get("delay_ms", 0)
        servos = position.get("servos", {})

        lines = []
        lines.append(f"Nombre: {name}")
        lines.append(f"Velocidad: {velocity}")
        lines.append(f"Delay después: {delay_ms} ms")
        lines.append("")
        lines.append("Servos:")

        for servo_id_str, data in sorted(servos.items(), key=lambda item: int(item[0])):
            angle = data.get("angle")
            dxl_position = data.get("dxl_position")
            lines.append(
                f"  ID {servo_id_str}: {angle}° | DXL {dxl_position}"
            )

        self.detail_text.insert("end", "\n".join(lines))

    # ---------------------------------------------------------------------
    # Selección de acción y posición
    # ---------------------------------------------------------------------

    def on_action_selected(self, _event=None):
        """
        Se ejecuta cuando el usuario selecciona una acción.

        Importante:
        Tkinter también dispara este evento cuando se refresca el Listbox.
        Por eso usamos self.refreshing_ui para no borrar la selección por accidente.
        """

        # Si el programa está actualizando visualmente la lista,
        # ignoramos este evento automático.
        if self.refreshing_ui:
            return

        selection = self.actions_listbox.curselection()

        # Si no hay selección real, no borramos todo inmediatamente.
        # Esto evita que se pierda la acción seleccionada cuando se refresca la interfaz.
        if not selection:
            return

        self.current_action_index = int(selection[0])
        self.current_position_index = None

        action = self.get_current_action()

        if action is not None:
            self.action_name_var.set(action.get("name", "Acción"))
            self.status_var.set(f"Acción seleccionada: {action.get('name', '')}")

        self.refresh_positions_list()
        self.clear_detail()

    def on_position_selected(self, _event=None):
        """
        Se ejecuta cuando el usuario selecciona una posición.

        Importante:
        Igual que con las acciones, este evento también puede dispararse
        automáticamente cuando refrescamos la lista de posiciones.
        """

        # Si estamos actualizando la interfaz, ignoramos el evento automático.
        if self.refreshing_ui:
            return

        selection = self.positions_listbox.curselection()

        # Si no hay selección real, no hacemos nada.
        # Así no se pierde current_action_index ni current_position_index.
        if not selection:
            return

        self.current_position_index = int(selection[0])

        position = self.get_current_position()

        if position is None:
            return

        self.position_velocity_var.set(int(position.get("velocity", 120)))
        self.position_delay_var.set(int(position.get("delay_ms", 0)))

        self.show_position_detail(position)

        # Carga los ángulos guardados en los sliders de la interfaz,
        # pero NO mueve los servos.
        self.load_position_angles_to_ui(position)

    def load_position_angles_to_ui(self, position: dict):
        """
        Carga los ángulos guardados en los sliders de la interfaz principal,
        sin enviar movimiento a los servos.

        Esto no mueve físicamente los motores.
        Solo cambia la posición visual de los controles.
        """
        servos = position.get("servos", {})

        for card in self.app.servo_cards:
            servo_id_str = str(card.cfg.servo_id)

            if servo_id_str in servos:
                angle = servos[servo_id_str].get("angle")
                if angle is not None:
                    card.set_angle(int(angle), send=False)

    # ---------------------------------------------------------------------
    # Acciones
    # ---------------------------------------------------------------------

    def create_or_update_action(self):
        """
        Crea una nueva acción o actualiza el nombre de la acción seleccionada.

        Si hay una acción seleccionada:
            cambia su nombre.

        Si no hay acción seleccionada:
            crea una acción nueva.
        """

        name = self.action_name_var.get().strip()

        if not name:
            messagebox.showwarning(
                "Nombre vacío",
                "Escribe un nombre para la acción.",
            )
            return

        # Si hay una acción seleccionada, se actualiza su nombre.
        if self.current_action_index is not None:
            action = self.get_current_action()

            if action is not None:
                action["name"] = name
                self.save_actions()
                self.refresh_actions_list()
                self.actions_listbox.selection_clear(0, "end")
                self.actions_listbox.selection_set(self.current_action_index)
                self.actions_listbox.see(self.current_action_index)
                self.status_var.set(f"Acción actualizada: {name}")
                self.app.log(f"✅ Acción actualizada: {name}")
                return

        # Si no hay acción seleccionada, se crea una nueva.
        new_action = {
            "name": name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "positions": [],
        }

        self.actions.append(new_action)
        self.current_action_index = len(self.actions) - 1
        self.current_position_index = None

        self.save_actions()
        self.refresh_actions_list()

        self.actions_listbox.selection_clear(0, "end")
        self.actions_listbox.selection_set(self.current_action_index)
        self.actions_listbox.see(self.current_action_index)

        self.refresh_positions_list()
        self.clear_detail()

        self.status_var.set(f"Acción creada: {name}")
        self.app.log(f"✅ Acción creada: {name}")

    def delete_selected_action(self):
        """
        Elimina la acción seleccionada.
        """
        action = self.get_current_action()

        if action is None:
            messagebox.showinfo(
                "Sin acción",
                "Selecciona una acción para eliminar.",
            )
            return

        name = action.get("name", "Acción")

        confirm = messagebox.askyesno(
            "Eliminar acción",
            f"¿Seguro que deseas eliminar la acción '{name}' y todas sus posiciones?",
        )

        if not confirm:
            return

        self.actions.pop(self.current_action_index)

        self.current_action_index = None
        self.current_position_index = None

        self.save_actions()
        self.refresh_actions_list()
        self.refresh_positions_list()
        self.clear_detail()

        self.status_var.set(f"Acción eliminada: {name}")
        self.app.log(f"🗑 Acción eliminada: {name}")

    # ---------------------------------------------------------------------
    # Posiciones
    # ---------------------------------------------------------------------

    def add_position(self):
        """
        Agrega una nueva posición a la acción seleccionada.

        Esta función:
        - Lee la posición real de cada servo.
        - Usa la velocidad escrita en el campo "Velocidad".
        - Usa el delay escrito en el campo "Delay después ms".
        - Crea una nueva posición al final de la acción.

        Mientras no se presione este botón "+", los cambios de posición
        NO quedan guardados.
        """

        action = self.get_current_action()

        if action is None:
            messagebox.showwarning(
                "Primero crea una acción",
                "Antes de agregar posiciones, crea o selecciona una acción.",
            )
            return

        position_number = len(action.get("positions", [])) + 1
        position_name = f"Posición {position_number}"

        self.capture_position(
            mode="add",
            position_name=position_name,
        )

    def update_selected_position(self):
        """
        Sobrescribe/chanca la posición seleccionada.

        Flujo:
        1. Seleccionas una posición.
        2. Mueves los servos o cambias sliders.
        3. Presionas este botón.
        4. Se vuelve a leer la posición real de los servos.
        5. Se reemplaza la posición seleccionada.
        """

        if self.get_current_action() is None:
            messagebox.showwarning(
                "Sin acción",
                "Selecciona una acción.",
            )
            return

        if self.get_current_position() is None:
            messagebox.showwarning(
                "Sin posición",
                "Selecciona una posición para actualizar.",
            )
            return

        position = self.get_current_position()
        position_name = position.get(
            "name",
            f"Posición {self.current_position_index + 1}",
        )

        self.capture_position(
            mode="update",
            position_name=position_name,
        )

    def capture_position(self, mode: str, position_name: str):
        """
        Lee las posiciones reales actuales de todos los servos.

        mode:
            "add"    -> agrega una posición nueva.
            "update" -> reemplaza la posición seleccionada.

        position_name:
            Nombre que tendrá la posición.
        """

        if not self.app.configs:
            messagebox.showinfo(
                "Sin servos",
                "No hay servos configurados.",
            )
            return

        if not self.app.controller.connected:
            messagebox.showwarning(
                "No conectado",
                "Primero conecta el puerto Dynamixel.",
            )
            return

        try:
            velocity = int(float(self.position_velocity_var.get()))
        except Exception:
            velocity = 120
            self.position_velocity_var.set(velocity)

        try:
            delay_ms = int(float(self.position_delay_var.get()))
        except Exception:
            delay_ms = 0
            self.position_delay_var.set(delay_ms)

        if velocity < 1:
            velocity = 1
            self.position_velocity_var.set(velocity)

        if delay_ms < 0:
            delay_ms = 0
            self.position_delay_var.set(delay_ms)

        self.set_buttons_state("disabled")
        self.status_var.set("Capturando posición real de los servos...")
        self.app.log(f"📌 Capturando {position_name}")

        captured_servos: Dict[str, dict] = {}

        total = len(self.app.configs)
        pending = {"count": total}

        def finish_if_done():
            """
            Cuando todos los servos fueron leídos,
            guarda o actualiza la posición.
            """
            pending["count"] -= 1

            if pending["count"] > 0:
                return

            self.set_buttons_state("normal")

            if not captured_servos:
                messagebox.showwarning(
                    "No se pudo capturar",
                    "No se pudo leer ningún servo. Revisa conexión, ID, protocolo y alimentación.",
                )
                self.status_var.set("No se pudo capturar posición.")
                return

            new_position = {
                "name": position_name,
                "velocity": int(velocity),
                "delay_ms": int(delay_ms),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "servos": captured_servos,
            }

            action = self.get_current_action()

            if action is None:
                self.status_var.set("No hay acción seleccionada.")
                return

            if "positions" not in action or not isinstance(action["positions"], list):
                action["positions"] = []

            if mode == "add":
                action["positions"].append(new_position)
                self.current_position_index = len(action["positions"]) - 1
                self.status_var.set(f"Posición agregada: {position_name}")
                self.app.log(f"✅ Posición agregada: {position_name}")

            elif mode == "update":
                if self.current_position_index is None:
                    self.status_var.set("No hay posición seleccionada.")
                    return

                if self.current_position_index < 0 or self.current_position_index >= len(action["positions"]):
                    self.status_var.set("Índice de posición inválido.")
                    return

                new_position["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                action["positions"][self.current_position_index] = new_position
                self.status_var.set(f"Posición actualizada: {position_name}")
                self.app.log(f"✅ Posición actualizada: {position_name}")

            self.save_actions()
            self.refresh_positions_list()
            self.refresh_actions_list()

            self.save_actions()

            # Refrescamos primero acciones y luego posiciones.
            # Las funciones refresh ahora ya restauran la selección automáticamente.
            self.refresh_actions_list()
            self.refresh_positions_list()

            # Volvemos a mostrar el detalle de la posición actual.
            position = self.get_current_position()
            if position is not None:
                self.show_position_detail(position)

        def make_callback(cfg):
            """
            Crea un callback para cada servo.
            """

            def callback(result):
                ok, msg, dxl_position, angle = result

                if ok and angle is not None:
                    servo_id_str = str(cfg.servo_id)

                    captured_servos[servo_id_str] = {
                        "angle": int(angle),
                        "dxl_position": int(dxl_position),
                    }

                    self.update_servo_card_angle(cfg.servo_id, angle)

                    self.app.log(
                        f"✅ Capturado ID {cfg.servo_id}: {angle}° | DXL {dxl_position}"
                    )
                else:
                    self.app.log(
                        f"⚠️ No se pudo leer ID {cfg.servo_id}: {msg}"
                    )

                finish_if_done()

            return callback

        for cfg in list(self.app.configs):
            self.app.worker.submit(
                f"capture-position-{cfg.servo_id}",
                lambda cfg=cfg: self.app.controller.read_position(cfg),
                make_callback(cfg),
            )

    def delete_selected_position(self):
        """
        Elimina la posición seleccionada.
        """
        action = self.get_current_action()

        if action is None:
            messagebox.showinfo(
                "Sin acción",
                "Selecciona una acción.",
            )
            return

        position = self.get_current_position()

        if position is None:
            messagebox.showinfo(
                "Sin posición",
                "Selecciona una posición para eliminar.",
            )
            return

        name = position.get("name", "Posición")

        confirm = messagebox.askyesno(
            "Eliminar posición",
            f"¿Seguro que deseas eliminar '{name}'?",
        )

        if not confirm:
            return

        deleted_index = self.current_position_index

        action["positions"].pop(deleted_index)

        # Después de eliminar, intentamos seleccionar una posición cercana.
        positions = action.get("positions", [])

        if not positions:
            self.current_position_index = None
        else:
            # Si eliminamos la última, seleccionamos la nueva última.
            # Si eliminamos una del medio, seleccionamos la que quedó en ese lugar.
            self.current_position_index = min(deleted_index, len(positions) - 1)

        self.save_actions()
        self.refresh_actions_list()
        self.refresh_positions_list()

        position = self.get_current_position()
        if position is not None:
            self.show_position_detail(position)
        else:
            self.clear_detail()

        self.status_var.set(f"Posición eliminada: {name}")
        self.app.log(f"🗑 Posición eliminada: {name}")

    # ---------------------------------------------------------------------
    # Reproducción
    # ---------------------------------------------------------------------

    def play_selected_position(self):
        """
        Reproduce solo la posición seleccionada.
        """
        position = self.get_current_position()

        if position is None:
            messagebox.showinfo(
                "Sin posición",
                "Selecciona una posición para reproducir.",
            )
            return

        self.start_playback([position], label="posición seleccionada")

    def play_selected_action(self):
        """
        Reproduce todas las posiciones de la acción seleccionada.
        """
        action = self.get_current_action()

        if action is None:
            messagebox.showinfo(
                "Sin acción",
                "Selecciona una acción para reproducir.",
            )
            return

        positions = action.get("positions", [])

        if not positions:
            messagebox.showinfo(
                "Acción vacía",
                "La acción seleccionada no tiene posiciones guardadas.",
            )
            return

        self.start_playback(positions, label=action.get("name", "Acción"))

    def start_playback(self, positions: List[dict], label: str):
        """
        Inicia la reproducción de una lista de posiciones.
        """

        if self.is_playing:
            messagebox.showinfo(
                "Reproducción activa",
                "Ya hay una reproducción en curso.",
            )
            return

        if not self.app.controller.connected:
            messagebox.showwarning(
                "No conectado",
                "Primero conecta el puerto Dynamixel.",
            )
            return

        self.is_playing = True
        self.stop_requested = False
        self.set_buttons_state("disabled")

        self.status_var.set(f"Reproduciendo {label}...")
        self.app.log(f"▶ Reproduciendo {label}")

        self._play_next_position(positions, index=0)

    def _play_next_position(self, positions: List[dict], index: int):
        """
        Reproduce una posición y, cuando realmente termina,
        recién pasa a la siguiente.
        """

        if self.stop_requested:
            self.finish_playback("Reproducción detenida.")
            return

        if index >= len(positions):
            self.finish_playback("Reproducción terminada.")
            return

        position = positions[index]
        name = position.get("name", f"Posición {index + 1}")
        delay_ms = int(position.get("delay_ms", 0))

        self.status_var.set(f"Reproduciendo {name}...")
        self.app.log(f"▶ Posición {index + 1}/{len(positions)}: {name}")

        # Todo el movimiento y la espera de llegada se ejecutan
        # en el worker para no congelar la interfaz.
        self.app.worker.submit(
            f"play-position-{index + 1}",
            lambda position=position: self.execute_position_and_wait(position),
            lambda result, positions=positions, index=index, delay_ms=delay_ms: self.after_position_finished(
                result,
                positions,
                index,
                delay_ms,
            ),
        )

    def execute_position_and_wait(self, position: dict):
        """
        Ejecuta una posición completa y espera a que los servos lleguen.

        Importante:
        - No pasa a la siguiente posición apenas se envía el comando.
        - Primero envía los objetivos.
        - Luego lee repetidamente la posición real.
        - Cuando todos los servos están cerca del objetivo, termina.
        """

        servos = position.get("servos", {})
        velocity = int(position.get("velocity", 120))

        if not servos:
            return False, "La posición no tiene servos guardados."

        # Margen de tolerancia en grados.
        # Si el servo queda a 1 o 2 grados del objetivo, se considera que llegó.
        tolerance_deg = 2

        # Tiempo máximo de espera para evitar bucles infinitos.
        # Si un servo no llega por bloqueo mecánico o falta de torque,
        # el programa no se queda esperando para siempre.
        timeout_sec = 15.0

        targets: Dict[int, int] = {}

        # -------------------------------------------------------------
        # 1. Enviar movimiento a todos los servos de la posición.
        # -------------------------------------------------------------

        for servo_id_str, servo_data in servos.items():
            try:
                servo_id = int(servo_id_str)
                target_angle = int(servo_data.get("angle", 0))
            except Exception:
                return False, f"Datos inválidos en servo {servo_id_str}."

            cfg = self.find_config_by_servo_id(servo_id)

            if cfg is None:
                return False, f"El servo ID {servo_id} no está configurado actualmente."

            targets[servo_id] = target_angle

            ok, msg = self.app.controller.move_to_angle(
                cfg,
                target_angle,
                velocity,
            )

            if not ok:
                return False, msg

        # -------------------------------------------------------------
        # 2. Esperar a que todos los servos lleguen físicamente.
        # -------------------------------------------------------------

        start_time = time.time()

        while True:
            all_reached = True
            last_error_text = ""

            for servo_id, target_angle in targets.items():
                cfg = self.find_config_by_servo_id(servo_id)

                if cfg is None:
                    return False, f"Servo ID {servo_id} no configurado durante espera."

                ok, msg, _dxl_position, current_angle = self.app.controller.read_position(cfg)

                if not ok or current_angle is None:
                    all_reached = False
                    last_error_text = msg
                    continue

                error = abs(int(current_angle) - int(target_angle))

                if error > tolerance_deg:
                    all_reached = False
                    last_error_text = (
                        f"ID {servo_id}: actual {current_angle}°, "
                        f"objetivo {target_angle}°, error {error}°"
                    )

            if all_reached:
                return True, "Posición alcanzada."

            if time.time() - start_time > timeout_sec:
                return False, f"Tiempo de espera agotado. Último estado: {last_error_text}"

            time.sleep(0.05)

    def after_position_finished(self, result, positions: List[dict], index: int, delay_ms: int):
        """
        Callback cuando terminó una posición.

        Si terminó correctamente:
            espera el delay y pasa a la siguiente.

        Si hubo error:
            detiene la reproducción.
        """

        ok, msg = result

        if ok:
            self.app.log(f"✅ {msg}")
        else:
            self.app.log(f"⚠️ {msg}")
            self.finish_playback("Reproducción detenida por error.")
            return

        if self.stop_requested:
            self.finish_playback("Reproducción detenida.")
            return

        # Si delay_ms es 0, pasa inmediatamente a la siguiente posición.
        # Si delay_ms es mayor a 0, espera ese tiempo.
        if delay_ms <= 0:
            self._play_next_position(positions, index + 1)
        else:
            self.status_var.set(f"Esperando delay: {delay_ms} ms")
            self.app.after(
                delay_ms,
                lambda: self._play_next_position(positions, index + 1),
            )

    def finish_playback(self, text: str):
        """
        Finaliza una reproducción.
        """
        self.is_playing = False
        self.stop_requested = False
        self.set_buttons_state("normal")
        self.status_var.set(text)
        self.app.log(text)

    def stop_playback(self):
        """
        Solicita detener la reproducción.

        No corta violentamente el movimiento que ya fue enviado al servo.
        Evita que se mande la siguiente posición.
        """
        if self.is_playing:
            self.stop_requested = True
            self.status_var.set("Deteniendo al finalizar la posición actual...")
            self.app.log("⏹ Se solicitó detener la secuencia.")
        else:
            self.status_var.set("No hay reproducción activa.")

    # ---------------------------------------------------------------------
    # Utilidades
    # ---------------------------------------------------------------------

    def get_current_action(self) -> Optional[dict]:
        """
        Devuelve la acción seleccionada.
        """
        if self.current_action_index is None:
            return None

        if self.current_action_index < 0 or self.current_action_index >= len(self.actions):
            return None

        return self.actions[self.current_action_index]

    def get_current_position(self) -> Optional[dict]:
        """
        Devuelve la posición seleccionada.
        """
        action = self.get_current_action()

        if action is None:
            return None

        positions = action.get("positions", [])

        if self.current_position_index is None:
            return None

        if self.current_position_index < 0 or self.current_position_index >= len(positions):
            return None

        return positions[self.current_position_index]

    def find_config_by_servo_id(self, servo_id: int):
        """
        Busca la configuración de un servo por ID.
        """
        for cfg in self.app.configs:
            if int(cfg.servo_id) == int(servo_id):
                return cfg
        return None

    def update_servo_card_angle(self, servo_id: int, angle: int):
        """
        Actualiza visualmente la tarjeta del servo.

        No mueve el servo.
        """
        for card in self.app.servo_cards:
            if int(card.cfg.servo_id) == int(servo_id):
                card.set_angle(int(angle), send=False)
                break

    def set_buttons_state(self, state: str):
        """
        Habilita o deshabilita botones principales.
        """
        for button in [
            self.new_action_button,
            self.delete_action_button,
            self.reload_button,
            self.add_position_button,
            self.update_position_button,
            self.delete_position_button,
            self.play_position_button,
            self.play_action_button,
        ]:
            button.configure(state=state)