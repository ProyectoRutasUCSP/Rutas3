import os
import re
import time
import argparse
import serial.tools.list_ports

from dynamixel_sdk import *
import map_dxl_angle as d2a


# ============================================================
# CONSTANTES DYNAMIXEL - PROTOCOL 2.0
# ============================================================

ADDR_TORQUE_ENABLE          = 64
ADDR_PROFILE_VELOCITY       = 112
ADDR_GOAL_POSITION          = 116
ADDR_PRESENT_POSITION       = 132

LEN_GOAL_POSITION           = 4
LEN_PRESENT_POSITION        = 4

DXL_MINIMUM_POSITION_VALUE  = 0
DXL_MAXIMUM_POSITION_VALUE  = 4095

BAUDRATE                    = 57600
PROTOCOL_VERSION            = 2.0

DXL_ID                      = [1, 2, 3, 4, 5, 6]

TORQUE_ENABLE               = 1
TORQUE_DISABLE              = 0

DXL_MOVING_STATUS_THRESHOLD = 20
GOAL_VELOCITY               = 50

MIN_ANGLE                   = 0
MAX_ANGLE                   = 360

MIN_PROFILE_VELOCITY        = 1
MAX_PROFILE_VELOCITY        = 32767

PROFILE_VELOCITY_RPM_UNIT   = 0.229


# ============================================================
# OBJETOS GLOBALES DEL SDK
# ============================================================

DEVICE_PORT = None
portHandler = None
packetHandler = None
groupBulkWrite = None
groupBulkRead = None


# ============================================================
# PUERTO / SISTEMA OPERATIVO
# ============================================================

def get_default_port():
    if os.name == "nt":
        return "COM7"
    return "/dev/ttyUSB0"


def list_available_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


def is_port_available(port):
    return port in list_available_ports()


def show_available_ports():
    ports = list_available_ports()

    print("Puertos disponibles:")

    if ports:
        for p in ports:
            print(f" - {p}")
    else:
        print("No se detectaron puertos seriales.")


# ============================================================
# CONEXIÓN
# ============================================================

def connect_to_port(port=None, baudrate=BAUDRATE, protocol=PROTOCOL_VERSION):
    global DEVICE_PORT
    global BAUDRATE
    global PROTOCOL_VERSION
    global portHandler
    global packetHandler
    global groupBulkWrite
    global groupBulkRead

    if port is None:
        port = get_default_port()

    DEVICE_PORT = port
    BAUDRATE = baudrate
    PROTOCOL_VERSION = protocol

    print(f"Sistema detectado: {'Windows' if os.name == 'nt' else 'Linux/Unix'}")
    print(f"Puerto seleccionado: {DEVICE_PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Protocolo: {PROTOCOL_VERSION}")

    if not is_port_available(DEVICE_PORT):
        print(f"El puerto {DEVICE_PORT} no está disponible.")
        show_available_ports()
        return False

    portHandler = PortHandler(DEVICE_PORT)
    packetHandler = PacketHandler(PROTOCOL_VERSION)
    groupBulkWrite = GroupBulkWrite(portHandler, packetHandler)
    groupBulkRead = GroupBulkRead(portHandler, packetHandler)

    if not portHandler.openPort():
        print(f"No se pudo abrir el puerto {DEVICE_PORT}.")
        return False

    print(f"Puerto abierto correctamente: {DEVICE_PORT}")

    if not portHandler.setBaudRate(BAUDRATE):
        print(f"No se pudo configurar el baudrate {BAUDRATE}.")
        portHandler.closePort()
        return False

    print(f"Baudrate configurado correctamente: {BAUDRATE}")

    return True


def disconnect_to_port():
    global portHandler

    if portHandler is not None:
        try:
            portHandler.closePort()
            print(f"Puerto cerrado correctamente: {DEVICE_PORT}")
        except Exception as e:
            print(f"Error al cerrar el puerto {DEVICE_PORT}: {e}")


def check_connection_ready():
    if portHandler is None or packetHandler is None:
        print("Error: primero debes llamar a connect_to_port().")
        return False

    return True


# ============================================================
# VALIDACIONES
# ============================================================

def is_valid_angle(angle):
    return MIN_ANGLE <= angle <= MAX_ANGLE


def is_valid_velocity(velocity):
    return MIN_PROFILE_VELOCITY <= velocity <= MAX_PROFILE_VELOCITY


def is_valid_time_ms(tiempo):
    return tiempo is not None and tiempo > 0


# ============================================================
# PING / ESCANEO
# ============================================================

def ping_servo(servo_id):
    if not check_connection_ready():
        return False

    model_number, dxl_comm_result, dxl_error = packetHandler.ping(
        portHandler,
        servo_id
    )

    if dxl_comm_result == COMM_SUCCESS:
        print(f"Servo encontrado | ID: {servo_id} | Modelo: {model_number}")
        return True

    if dxl_error != 0:
        print(f"ID {servo_id}: error Dynamixel -> {packetHandler.getRxPacketError(dxl_error)}")
    else:
        print(f"Servo ID {servo_id} no conectado o sin respuesta.")

    return False


def get_connected_ids(ids):
    connected = []

    for servo_id in ids:
        if ping_servo(servo_id):
            connected.append(servo_id)

    return connected


def scan_ids(id_min=1, id_max=30):
    if not check_connection_ready():
        return []

    encontrados = []

    print(f"Escaneando IDs desde {id_min} hasta {id_max}...")

    for servo_id in range(id_min, id_max + 1):
        model_number, dxl_comm_result, dxl_error = packetHandler.ping(
            portHandler,
            servo_id
        )

        if dxl_comm_result == COMM_SUCCESS:
            print(f"Servo encontrado | ID: {servo_id} | Modelo: {model_number}")
            encontrados.append(servo_id)

    if encontrados:
        print(f"IDs encontrados: {encontrados}")
    else:
        print("No se encontró ningún servo.")

    return encontrados


# ============================================================
# TORQUE
# ============================================================

def enable_torque(IDs=DXL_ID):
    if not check_connection_ready():
        return False

    ok = True

    for servo_id in IDs:
        dxl_comm_result, dxl_error = packetHandler.write1ByteTxRx(
            portHandler,
            servo_id,
            ADDR_TORQUE_ENABLE,
            TORQUE_ENABLE
        )

        if dxl_comm_result != COMM_SUCCESS:
            print(f"[ID:{servo_id:03d}] Error torque ON: {packetHandler.getTxRxResult(dxl_comm_result)}")
            ok = False
        elif dxl_error != 0:
            print(f"[ID:{servo_id:03d}] Error Dynamixel: {packetHandler.getRxPacketError(dxl_error)}")
            ok = False
        else:
            print(f"[ID:{servo_id:03d}] Torque habilitado.")

    return ok


def disable_torque(IDs=DXL_ID):
    if not check_connection_ready():
        return False

    ok = True

    for servo_id in IDs:
        dxl_comm_result, dxl_error = packetHandler.write1ByteTxRx(
            portHandler,
            servo_id,
            ADDR_TORQUE_ENABLE,
            TORQUE_DISABLE
        )

        if dxl_comm_result != COMM_SUCCESS:
            print(f"[ID:{servo_id:03d}] Error torque OFF: {packetHandler.getTxRxResult(dxl_comm_result)}")
            ok = False
        elif dxl_error != 0:
            print(f"[ID:{servo_id:03d}] Error Dynamixel: {packetHandler.getRxPacketError(dxl_error)}")
            ok = False
        else:
            print(f"[ID:{servo_id:03d}] Torque deshabilitado.")

    return ok


# ============================================================
# LECTURA DE POSICIÓN
# ============================================================

def read_current_position(servo_id):
    if not check_connection_ready():
        return None

    dxl_present_position, dxl_comm_result, dxl_error = packetHandler.read4ByteTxRx(
        portHandler,
        servo_id,
        ADDR_PRESENT_POSITION
    )

    if dxl_comm_result != COMM_SUCCESS:
        print(f"[ID:{servo_id:03d}] Error leyendo posición: {packetHandler.getTxRxResult(dxl_comm_result)}")
        return None

    if dxl_error != 0:
        print(f"[ID:{servo_id:03d}] Error Dynamixel: {packetHandler.getRxPacketError(dxl_error)}")
        return None

    return dxl_present_position


def read_current_angle(servo_id):
    position = read_current_position(servo_id)

    if position is None:
        return None

    return d2a.dxl2degrees(position)


def read_positions(IDs=DXL_ID):
    if not check_connection_ready():
        return

    for servo_id in IDs:
        position = read_current_position(servo_id)

        if position is not None:
            degree = d2a.dxl2degrees(position)

            print(
                f"[ID:{servo_id:03d}] "
                f"Posición actual: {position} | "
                f"Ángulo aprox: {degree}°"
            )


# ============================================================
# CÁLCULO DE VELOCIDAD POR TIEMPO
# ============================================================

def calculate_velocity_by_time(current_angle, target_angle, time_ms):
    if not is_valid_time_ms(time_ms):
        print("El tiempo debe ser mayor que 0 ms.")
        return MIN_PROFILE_VELOCITY

    angle_difference = abs(target_angle - current_angle)

    if angle_difference == 0:
        return MIN_PROFILE_VELOCITY

    revolutions = angle_difference / 360.0
    minutes = time_ms / 60000.0

    rpm_needed = revolutions / minutes
    profile_velocity = rpm_needed / PROFILE_VELOCITY_RPM_UNIT

    profile_velocity = int(round(profile_velocity))

    if profile_velocity < MIN_PROFILE_VELOCITY:
        profile_velocity = MIN_PROFILE_VELOCITY

    if profile_velocity > MAX_PROFILE_VELOCITY:
        profile_velocity = MAX_PROFILE_VELOCITY

    return profile_velocity


def build_final_velocities(degrees, velocities=None, tiempos=None, default_velocity=GOAL_VELOCITY):
    """
    Construye la velocidad final de cada servo.

    Prioridad:
    1. Si el servo tiene tiempo individual, calcula velocidad por tiempo.
    2. Si no tiene tiempo, usa velocidad individual.
    3. Si no tiene velocidad individual, usa velocidad general.
    """

    if velocities is None:
        velocities = {}

    if tiempos is None:
        tiempos = {}

    final_velocities = {}

    for servo_id, target_angle in degrees.items():

        if servo_id in tiempos and tiempos[servo_id] is not None:
            current_angle = read_current_angle(servo_id)

            if current_angle is None:
                print(f"[ID:{servo_id:03d}] No se pudo leer el ángulo actual. Se omitirá.")
                continue

            velocity = calculate_velocity_by_time(
                current_angle=current_angle,
                target_angle=target_angle,
                time_ms=tiempos[servo_id]
            )

            print(
                f"[ID:{servo_id:03d}] "
                f"Actual: {current_angle}° | "
                f"Objetivo: {target_angle}° | "
                f"Tiempo: {tiempos[servo_id]} ms | "
                f"Velocidad calculada: {velocity}"
            )

        else:
            velocity = velocities.get(servo_id, default_velocity)

        if not is_valid_velocity(velocity):
            print(
                f"[ID:{servo_id:03d}] Velocidad inválida: {velocity}. "
                f"Debe estar entre {MIN_PROFILE_VELOCITY} y {MAX_PROFILE_VELOCITY}."
            )
            continue

        final_velocities[servo_id] = int(velocity)

    return final_velocities


# ============================================================
# MOVIMIENTO
# ============================================================

def write_profile_velocity(servo_id, velocity):
    dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(
        portHandler,
        servo_id,
        ADDR_PROFILE_VELOCITY,
        int(velocity)
    )

    if dxl_comm_result != COMM_SUCCESS:
        print(f"[ID:{servo_id:03d}] Error configurando velocidad: {packetHandler.getTxRxResult(dxl_comm_result)}")
        return False

    if dxl_error != 0:
        print(f"[ID:{servo_id:03d}] Error Dynamixel en velocidad: {packetHandler.getRxPacketError(dxl_error)}")
        return False

    return True


def add_goal_position_to_bulk(servo_id, goal_position):
    param_goal_position = [
        DXL_LOBYTE(DXL_LOWORD(goal_position)),
        DXL_HIBYTE(DXL_LOWORD(goal_position)),
        DXL_LOBYTE(DXL_HIWORD(goal_position)),
        DXL_HIBYTE(DXL_HIWORD(goal_position))
    ]

    result = groupBulkWrite.addParam(
        servo_id,
        ADDR_GOAL_POSITION,
        LEN_GOAL_POSITION,
        param_goal_position
    )

    if not result:
        print(f"[ID:{servo_id:03d}] Error agregando parámetro a GroupBulkWrite.")
        return False

    return True


def is_servo_moving(degrees):
    if not check_connection_ready():
        return False

    moving = False

    for servo_id, degree in degrees.items():
        goal_position = d2a.degrees2dxl(degree)
        current_position = read_current_position(servo_id)

        if current_position is None:
            continue

        diff = abs(current_position - goal_position)

        print(
            f"[ID:{servo_id:03d}] "
            f"Actual: {current_position} | "
            f"Meta: {goal_position} | "
            f"Diferencia: {diff}"
        )

        if diff > DXL_MOVING_STATUS_THRESHOLD:
            moving = True

    return moving


def move_servos(
    degrees,
    velocities=None,
    tiempos=None,
    velocity=GOAL_VELOCITY,
    wait=True,
    check_ids=True
):
    """
    Mueve varios servos.

    degrees:
        {ID: ANGULO}

    velocities:
        {ID: VELOCIDAD}

    tiempos:
        {ID: TIEMPO_MS}

    Prioridad:
        tiempo individual > velocidad individual > velocidad general

    Ejemplo:
        move_servos({1: 90, 2: 180}, velocities={1: 20, 2: 70})
        move_servos({1: 90, 2: 180}, tiempos={1: 1000, 2: 1500})
        move_servos({1: 90, 2: 180}, velocities={1: 20}, tiempos={2: 1500})
    """

    if not check_connection_ready():
        return False

    if not degrees:
        print("No hay servos para mover.")
        return False

    if velocities is None:
        velocities = {}

    if tiempos is None:
        tiempos = {}

    if check_ids:
        connected_ids = get_connected_ids(list(degrees.keys()))

        degrees = {
            servo_id: degrees[servo_id]
            for servo_id in connected_ids
        }

        velocities = {
            servo_id: velocities[servo_id]
            for servo_id in connected_ids
            if servo_id in velocities
        }

        tiempos = {
            servo_id: tiempos[servo_id]
            for servo_id in connected_ids
            if servo_id in tiempos
        }

        if not degrees:
            print("Ninguno de los servos solicitados está conectado.")
            return False

    valid_degrees = {}

    for servo_id, angle in degrees.items():
        if not is_valid_angle(angle):
            print(f"[ID:{servo_id:03d}] Ángulo inválido: {angle}. Debe estar entre {MIN_ANGLE} y {MAX_ANGLE}.")
            continue

        valid_degrees[servo_id] = angle

    if not valid_degrees:
        print("No hay ángulos válidos para mover.")
        return False

    final_velocities = build_final_velocities(
        degrees=valid_degrees,
        velocities=velocities,
        tiempos=tiempos,
        default_velocity=velocity
    )

    if not final_velocities:
        print("No hay velocidades válidas para mover.")
        return False

    valid_degrees = {
        servo_id: valid_degrees[servo_id]
        for servo_id in final_velocities.keys()
    }

    groupBulkWrite.clearParam()

    params_added = 0

    for servo_id, angle in valid_degrees.items():
        goal_position = d2a.degrees2dxl(angle)
        servo_velocity = final_velocities[servo_id]

        if not write_profile_velocity(servo_id, servo_velocity):
            continue

        if not add_goal_position_to_bulk(servo_id, goal_position):
            continue

        params_added += 1

        tiempo_txt = ""
        if servo_id in tiempos:
            tiempo_txt = f" | Tiempo: {tiempos[servo_id]} ms"

        print(
            f"[ID:{servo_id:03d}] "
            f"Ángulo: {angle}° | "
            f"Posición DXL: {goal_position} | "
            f"Velocidad: {servo_velocity}"
            f"{tiempo_txt}"
        )

    if params_added == 0:
        print("No se agregó ningún servo válido al paquete de movimiento.")
        groupBulkWrite.clearParam()
        return False

    dxl_comm_result = groupBulkWrite.txPacket()

    if dxl_comm_result != COMM_SUCCESS:
        print(f"Error en GroupBulkWrite: {packetHandler.getTxRxResult(dxl_comm_result)}")
        groupBulkWrite.clearParam()
        return False

    groupBulkWrite.clearParam()

    if wait:
        time.sleep(0.2)

        while is_servo_moving(valid_degrees):
            time.sleep(0.1)

        print("Movimiento completado.")

    return True


def move_servo(
    servo_id,
    angle,
    velocity=None,
    tiempo=None,
    wait=True,
    check_ids=True
):
    """
    Mueve un solo servo.

    Ejemplos:
        move_servo(2, 180)
        move_servo(2, 180, velocity=70)
        move_servo(2, 180, tiempo=1000)
    """

    velocities = {}
    tiempos = {}

    if velocity is not None:
        velocities[servo_id] = velocity

    if tiempo is not None:
        tiempos[servo_id] = tiempo

    return move_servos(
        degrees={servo_id: angle},
        velocities=velocities,
        tiempos=tiempos,
        velocity=GOAL_VELOCITY,
        wait=wait,
        check_ids=check_ids
    )


def move_servos_by_time(degrees, tiempos=None, tiempo=None, wait=True, check_ids=True):
    """
    Compatibilidad para mover por tiempo.

    Puede recibir:
        tiempos={1: 1000, 2: 1500}

    O un tiempo general:
        tiempo=1000
    """

    if tiempos is None:
        tiempos = {}

    if tiempo is not None:
        tiempos = {
            servo_id: tiempos.get(servo_id, tiempo)
            for servo_id in degrees.keys()
        }

    return move_servos(
        degrees=degrees,
        tiempos=tiempos,
        wait=wait,
        check_ids=check_ids
    )


# ============================================================
# PARSER DE CONSOLA
# ============================================================

def parse_number(value, as_int=False):
    value = value.strip()

    if as_int:
        return int(float(value))

    number = float(value)

    if number.is_integer():
        return int(number)

    return number


def parse_extra_token(token):
    """
    Interpreta tokens adicionales:

    50          -> velocidad 50
    v50         -> velocidad 50
    v=50        -> velocidad 50
    vel50       -> velocidad 50
    t1000       -> tiempo 1000 ms
    t=1000      -> tiempo 1000 ms
    tiempo1000  -> tiempo 1000 ms
    """

    token = token.strip().lower().replace(" ", "")

    if not token:
        return None, None

    if token.startswith(("t=", "time=", "tiempo=")):
        value = token.split("=", 1)[1]
        return "tiempo", parse_number(value, as_int=True)

    if token.startswith(("v=", "vel=", "velocity=")):
        value = token.split("=", 1)[1]
        return "velocity", parse_number(value, as_int=True)

    if token.startswith("tiempo"):
        value = token.replace("tiempo", "", 1)
        return "tiempo", parse_number(value, as_int=True)

    if token.startswith("time"):
        value = token.replace("time", "", 1)
        return "tiempo", parse_number(value, as_int=True)

    if token.startswith("t"):
        value = token.replace("t", "", 1)
        return "tiempo", parse_number(value, as_int=True)

    if token.startswith("velocity"):
        value = token.replace("velocity", "", 1)
        return "velocity", parse_number(value, as_int=True)

    if token.startswith("vel"):
        value = token.replace("vel", "", 1)
        return "velocity", parse_number(value, as_int=True)

    if token.startswith("v"):
        value = token.replace("v", "", 1)
        return "velocity", parse_number(value, as_int=True)

    if re.match(r"^\d+(\.\d+)?$", token):
        return "velocity", parse_number(token, as_int=True)

    raise ValueError(f"Token inválido: '{token}'")


def parse_servo_list(text):
    """
    Convierte texto de consola en tres diccionarios:

    Entrada:
        "[1:30, 2:160:50, 3:90:t1000, 4:120:v70:t1500]"

    Salida:
        degrees    = {1: 30, 2: 160, 3: 90, 4: 120}
        velocities = {2: 50, 4: 70}
        tiempos    = {3: 1000, 4: 1500}

    Formatos aceptados:
        ID:ANGULO
        ID:ANGULO:VELOCIDAD
        ID:ANGULO:vVELOCIDAD
        ID:ANGULO:tTIEMPO
        ID:ANGULO:vVELOCIDAD:tTIEMPO
    """

    if text is None:
        return {}, {}, {}

    text = text.strip()

    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]

    degrees = {}
    velocities = {}
    tiempos = {}

    if not text.strip():
        return degrees, velocities, tiempos

    parts = text.split(",")

    for part in parts:
        part = part.strip()

        if not part:
            continue

        tokens = [token.strip() for token in part.split(":")]

        if len(tokens) < 2:
            raise ValueError(
                f"Formato inválido en '{part}'. "
                "Usa ID:ANGULO, por ejemplo 2:90"
            )

        servo_id = parse_number(tokens[0], as_int=True)
        angle = parse_number(tokens[1], as_int=False)

        degrees[servo_id] = angle

        for extra_token in tokens[2:]:
            key, value = parse_extra_token(extra_token)

            if key == "velocity":
                velocities[servo_id] = value
            elif key == "tiempo":
                tiempos[servo_id] = value

    return degrees, velocities, tiempos


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Mover servomotores Dynamixel desde consola o usar como librería."
    )

    parser.add_argument(
        "-l",
        "--list",
        dest="servo_list",
        type=str,
        help='Ejemplo: "[1:30, 2:160:v50, 3:90:t1000]"'
    )

    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=str,
        default=None,
        help="Puerto serial. Windows: COM7. Linux: /dev/ttyUSB0."
    )

    parser.add_argument(
        "-b",
        "--baudrate",
        dest="baudrate",
        type=int,
        default=BAUDRATE,
        help="Baudrate. Por defecto: 57600."
    )

    parser.add_argument(
        "--protocol",
        dest="protocol",
        type=float,
        default=PROTOCOL_VERSION,
        help="Protocolo Dynamixel. Por defecto: 2.0."
    )

    parser.add_argument(
        "-v",
        "--velocity",
        dest="velocity",
        type=int,
        default=GOAL_VELOCITY,
        help="Velocidad general si un servo no tiene velocidad ni tiempo. Por defecto: 50."
    )

    parser.add_argument(
        "-t",
        "--tiempo",
        dest="tiempo",
        type=int,
        default=None,
        help="Tiempo general en ms para servos sin tiempo individual. Ejemplo: --tiempo 1500"
    )

    parser.add_argument(
        "--no-wait",
        dest="no_wait",
        action="store_true",
        help="No esperar a que los servos lleguen a la posición."
    )

    parser.add_argument(
        "--scan",
        dest="scan",
        action="store_true",
        help="Escanear IDs en lugar de mover servos."
    )

    parser.add_argument(
        "--id-min",
        dest="id_min",
        type=int,
        default=1,
        help="ID mínimo para escaneo. Por defecto: 1."
    )

    parser.add_argument(
        "--id-max",
        dest="id_max",
        type=int,
        default=30,
        help="ID máximo para escaneo. Por defecto: 30."
    )

    args = parser.parse_args()

    if not connect_to_port(
        port=args.port,
        baudrate=args.baudrate,
        protocol=args.protocol
    ):
        return

    try:
        if args.scan:
            scan_ids(args.id_min, args.id_max)
            return

        if not args.servo_list:
            print("No se indicó lista de servos.")
            print('Ejemplo: python mover_servos.py -l "[1:30, 2:160:v50, 3:90:t1000]"')
            return

        try:
            degrees, velocities, tiempos = parse_servo_list(args.servo_list)
        except ValueError as e:
            print(e)
            return

        ids = list(degrees.keys())

        print(f"Servos IDs: {ids}")
        print(f"Ángulos: {degrees}")
        print(f"Velocidades individuales: {velocities if velocities else 'No indicadas'}")
        print(f"Tiempos individuales: {tiempos if tiempos else 'No indicados'}")

        connected_ids = get_connected_ids(ids)

        if not connected_ids:
            print("No se encontró ningún servo solicitado. No se moverá nada.")
            return

        valid_degrees = {
            servo_id: degrees[servo_id]
            for servo_id in connected_ids
        }

        valid_velocities = {
            servo_id: velocities[servo_id]
            for servo_id in connected_ids
            if servo_id in velocities
        }

        valid_tiempos = {
            servo_id: tiempos[servo_id]
            for servo_id in connected_ids
            if servo_id in tiempos
        }

        if args.tiempo is not None:
            for servo_id in connected_ids:
                if servo_id not in valid_tiempos:
                    valid_tiempos[servo_id] = args.tiempo

        print(f"Velocidad general: {args.velocity}")
        print(f"Tiempos finales: {valid_tiempos if valid_tiempos else 'No se usará control por tiempo'}")

        enable_torque(connected_ids)

        move_servos(
            degrees=valid_degrees,
            velocities=valid_velocities,
            tiempos=valid_tiempos,
            velocity=args.velocity,
            wait=not args.no_wait,
            check_ids=False
        )

        disable_torque(connected_ids)

    finally:
        disconnect_to_port()


if __name__ == "__main__":
    main()