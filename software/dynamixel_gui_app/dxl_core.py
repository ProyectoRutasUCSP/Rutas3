from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import serial.tools.list_ports
    from dynamixel_sdk import (
        PortHandler,
        PacketHandler,
        COMM_SUCCESS,
    )
except Exception as exc:  # permite que la interfaz avise sin cerrarse brutalmente
    serial = None
    PortHandler = None
    PacketHandler = None
    COMM_SUCCESS = 0
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


ADDR_TORQUE_ENABLE = 64
ADDR_PROFILE_VELOCITY = 112
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132

TORQUE_ENABLE = 1
TORQUE_DISABLE = 0

DEFAULT_BAUDRATE = 57600
DEFAULT_PROTOCOL = 2.0
MIN_PROFILE_VELOCITY = 1
MAX_PROFILE_VELOCITY = 32767


@dataclass
class ServoConfig:
    servo_id: int = 1
    min_angle: int = 0
    max_angle: int = 360
    dxl_min: int = 0
    dxl_max: int = 4095
    velocity: int = 80

    def clamp_angle(self, angle: float) -> int:
        return int(max(self.min_angle, min(self.max_angle, round(angle))))

    def clamp_velocity(self, velocity: float) -> int:
        return int(max(MIN_PROFILE_VELOCITY, min(MAX_PROFILE_VELOCITY, round(velocity))))

    def angle_to_dxl(self, angle: float) -> int:
        angle = self.clamp_angle(angle)
        if self.max_angle == self.min_angle:
            return self.dxl_min
        value = (angle - self.min_angle) * (self.dxl_max - self.dxl_min) / (self.max_angle - self.min_angle) + self.dxl_min
        return int(round(max(min(value, self.dxl_max), self.dxl_min)))

    def dxl_to_angle(self, position: int) -> int:
        if self.dxl_max == self.dxl_min:
            return self.min_angle
        value = (position - self.dxl_min) * (self.max_angle - self.min_angle) / (self.dxl_max - self.dxl_min) + self.min_angle
        return self.clamp_angle(value)


class DynamixelController:
    def __init__(self) -> None:
        self.port_name: Optional[str] = None
        self.baudrate: int = DEFAULT_BAUDRATE
        self.protocol: float = DEFAULT_PROTOCOL
        self.port_handler = None
        self.packet_handler = None
        self.lock = threading.RLock()
        self.connected = False
        # Cache para no reescribir Profile Velocity en cada pequeño movimiento
        # si la velocidad no cambió. Esto mejora la respuesta al arrastrar sliders.
        self._last_velocity_by_id = {}

    @staticmethod
    def default_port() -> str:
        return "COM7" if os.name == "nt" else "/dev/ttyUSB0"

    @staticmethod
    def available_ports() -> List[str]:
        if _IMPORT_ERROR is not None:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port_name: Optional[str] = None, baudrate: int = DEFAULT_BAUDRATE, protocol: float = DEFAULT_PROTOCOL) -> Tuple[bool, str]:
        if _IMPORT_ERROR is not None:
            return False, f"No se pudo importar dynamixel_sdk/pyserial: {_IMPORT_ERROR}"

        with self.lock:
            self.disconnect()
            self.port_name = port_name or self.default_port()
            self.baudrate = int(baudrate)
            self.protocol = float(protocol)

            ports = self.available_ports()
            if ports and self.port_name not in ports:
                return False, f"El puerto {self.port_name} no está disponible. Puertos detectados: {', '.join(ports)}"

            try:
                self.port_handler = PortHandler(self.port_name)
                self.packet_handler = PacketHandler(self.protocol)

                if not self.port_handler.openPort():
                    self.port_handler = None
                    self.packet_handler = None
                    return False, f"No se pudo abrir el puerto {self.port_name}."

                if not self.port_handler.setBaudRate(self.baudrate):
                    self.port_handler.closePort()
                    self.port_handler = None
                    self.packet_handler = None
                    return False, f"No se pudo configurar el baudrate {self.baudrate}."

                self.connected = True
                return True, f"Conectado en {self.port_name} a {self.baudrate} baudios."
            except Exception as exc:
                self.connected = False
                return False, f"Error conectando: {exc}"

    def disconnect(self) -> None:
        with self.lock:
            if self.port_handler is not None:
                try:
                    self.port_handler.closePort()
                except Exception:
                    pass
            self.port_handler = None
            self.packet_handler = None
            self.connected = False
            self._last_velocity_by_id.clear()

    def _ready(self) -> Tuple[bool, str]:
        if not self.connected or self.port_handler is None or self.packet_handler is None:
            return False, "Primero conecta el puerto Dynamixel."
        return True, "OK"

    def ping(self, servo_id: int) -> Tuple[bool, str, Optional[int]]:
        with self.lock:
            ready, msg = self._ready()
            if not ready:
                return False, msg, None
            try:
                model_number, comm_result, dxl_error = self.packet_handler.ping(self.port_handler, int(servo_id))
                if comm_result == COMM_SUCCESS:
                    return True, f"Servo ID {servo_id} conectado. Modelo: {model_number}", model_number
                if dxl_error != 0:
                    return False, f"ID {servo_id}: {self.packet_handler.getRxPacketError(dxl_error)}", None
                return False, f"Servo ID {servo_id} no responde. Verifica ID, cableado, torque/alimentación y protocolo.", None
            except Exception as exc:
                return False, f"Error haciendo ping a ID {servo_id}: {exc}", None

    def scan(self, id_min: int = 1, id_max: int = 30) -> Tuple[List[int], str]:
        found: List[int] = []
        with self.lock:
            ready, msg = self._ready()
            if not ready:
                return found, msg
            for servo_id in range(int(id_min), int(id_max) + 1):
                try:
                    model_number, comm_result, _dxl_error = self.packet_handler.ping(self.port_handler, servo_id)
                    if comm_result == COMM_SUCCESS:
                        found.append(servo_id)
                except Exception:
                    continue
        if found:
            return found, f"IDs encontrados: {found}"
        return found, "No se encontró ningún servo en el rango indicado."

    def enable_torque(self, servo_id: int, enable: bool = True) -> Tuple[bool, str]:
        with self.lock:
            ready, msg = self._ready()
            if not ready:
                return False, msg
            try:
                value = TORQUE_ENABLE if enable else TORQUE_DISABLE
                comm_result, dxl_error = self.packet_handler.write1ByteTxRx(
                    self.port_handler, int(servo_id), ADDR_TORQUE_ENABLE, value
                )
                if comm_result != COMM_SUCCESS:
                    return False, f"ID {servo_id}: {self.packet_handler.getTxRxResult(comm_result)}"
                if dxl_error != 0:
                    return False, f"ID {servo_id}: {self.packet_handler.getRxPacketError(dxl_error)}"
                return True, f"Torque {'habilitado' if enable else 'deshabilitado'} en ID {servo_id}."
            except Exception as exc:
                return False, f"Error cambiando torque en ID {servo_id}: {exc}"

    def read_position(self, cfg: ServoConfig) -> Tuple[bool, str, Optional[int], Optional[int]]:
        with self.lock:
            ready, msg = self._ready()
            if not ready:
                return False, msg, None, None
            try:
                position, comm_result, dxl_error = self.packet_handler.read4ByteTxRx(
                    self.port_handler, int(cfg.servo_id), ADDR_PRESENT_POSITION
                )
                if comm_result != COMM_SUCCESS:
                    return False, f"ID {cfg.servo_id}: {self.packet_handler.getTxRxResult(comm_result)}", None, None
                if dxl_error != 0:
                    return False, f"ID {cfg.servo_id}: {self.packet_handler.getRxPacketError(dxl_error)}", None, None
                return True, f"ID {cfg.servo_id}: posición {position}", position, cfg.dxl_to_angle(position)
            except Exception as exc:
                return False, f"Error leyendo posición en ID {cfg.servo_id}: {exc}", None, None

    def set_velocity(self, cfg: ServoConfig, velocity: int) -> Tuple[bool, str]:
        velocity = cfg.clamp_velocity(velocity)
        with self.lock:
            ready, msg = self._ready()
            if not ready:
                return False, msg
            try:
                comm_result, dxl_error = self.packet_handler.write4ByteTxRx(
                    self.port_handler, int(cfg.servo_id), ADDR_PROFILE_VELOCITY, int(velocity)
                )
                if comm_result != COMM_SUCCESS:
                    return False, f"ID {cfg.servo_id}: error velocidad: {self.packet_handler.getTxRxResult(comm_result)}"
                if dxl_error != 0:
                    return False, f"ID {cfg.servo_id}: error Dynamixel velocidad: {self.packet_handler.getRxPacketError(dxl_error)}"
                return True, f"ID {cfg.servo_id}: velocidad {velocity}."
            except Exception as exc:
                return False, f"Error configurando velocidad en ID {cfg.servo_id}: {exc}"

    def move_to_angle(self, cfg: ServoConfig, angle: int, velocity: int) -> Tuple[bool, str]:
        angle = cfg.clamp_angle(angle)
        velocity = cfg.clamp_velocity(velocity)
        goal_position = cfg.angle_to_dxl(angle)

        with self.lock:
            ready, msg = self._ready()
            if not ready:
                return False, msg
            try:
                # Solo actualiza Profile Velocity cuando cambió. En un arrastre continuo
                # del slider, escribir velocidad + posición en cada punto duplica el tráfico.
                if self._last_velocity_by_id.get(int(cfg.servo_id)) != int(velocity):
                    ok, msg = self.set_velocity(cfg, velocity)
                    if not ok:
                        return False, msg
                    self._last_velocity_by_id[int(cfg.servo_id)] = int(velocity)

                comm_result, dxl_error = self.packet_handler.write4ByteTxRx(
                    self.port_handler, int(cfg.servo_id), ADDR_GOAL_POSITION, int(goal_position)
                )
                if comm_result != COMM_SUCCESS:
                    return False, f"ID {cfg.servo_id}: error posición: {self.packet_handler.getTxRxResult(comm_result)}"
                if dxl_error != 0:
                    return False, f"ID {cfg.servo_id}: error Dynamixel posición: {self.packet_handler.getRxPacketError(dxl_error)}"
                return True, f"ID {cfg.servo_id}: {angle}° → DXL {goal_position}, velocidad {velocity}."
            except Exception as exc:
                return False, f"Error moviendo ID {cfg.servo_id}: {exc}"
