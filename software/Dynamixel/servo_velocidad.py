from dynamixel_sdk import *  # Biblioteca para controlar Dynamixel

# Configuración del puerto y protocolo
PORT_NAME = 'COM4'  # Cambia esto según tu sistema
BAUDRATE = 57600
PROTOCOL_VERSION = 2.0

# Configuración del servo
DXL_ID = 1  # ID del servomotor
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132
ADDR_PROFILE_VELOCITY = 112
TORQUE_ENABLE = 1
TORQUE_DISABLE = 0
MIN_POSITION = 0       # Posición mínima (0)
MAX_POSITION = 2047    # Posición máxima (2047)

# Conversión de ángulos a valores de posición (MX-64AT tiene rango de 0-2047 para 0-360 grados)
def angle_to_position(angle):
    return int(angle / 360 * MAX_POSITION)

# Crear puerto y paquete
port_handler = PortHandler(PORT_NAME)
packet_handler = PacketHandler(PROTOCOL_VERSION)

# Inicializar comunicación
try:
    if not port_handler.openPort():
        raise IOError("Error al abrir el puerto.")
    if not port_handler.setBaudRate(BAUDRATE):
        raise ValueError("Error al configurar la tasa de baudios.")
except (IOError, ValueError) as e:
    print(e)
    exit()

# Habilitar torque
def enable_torque():
    dxl_comm_result, dxl_error = packet_handler.write1ByteTxRx(port_handler, DXL_ID, ADDR_TORQUE_ENABLE, TORQUE_ENABLE)
    if dxl_comm_result != COMM_SUCCESS:
        print(f"Error: {packet_handler.getTxRxResult(dxl_comm_result)}")
    elif dxl_error != 0:
        print(f"Error: {packet_handler.getRxPacketError(dxl_error)}")
    else:
        print("Torque habilitado correctamente.")

# Deshabilitar torque
def disable_torque():
    dxl_comm_result, dxl_error = packet_handler.write1ByteTxRx(port_handler, DXL_ID, ADDR_TORQUE_ENABLE, TORQUE_DISABLE)
    if dxl_comm_result != COMM_SUCCESS:
        print(f"Error: {packet_handler.getTxRxResult(dxl_comm_result)}")
    elif dxl_error != 0:
        print(f"Error: {packet_handler.getRxPacketError(dxl_error)}")

# Configurar velocidad usando PROFILE_VELOCITY
def set_velocity(speed):
    if speed < 0 or speed > 32767:  # Rango válido para PROFILE_VELOCITY
        print(f"Error: La velocidad {speed} está fuera del rango permitido (0-32767).")
        return
    dxl_comm_result, dxl_error = packet_handler.write4ByteTxRx(port_handler, DXL_ID, ADDR_PROFILE_VELOCITY, speed)
    if dxl_comm_result != COMM_SUCCESS:
        print(f"Error velocity 001: {packet_handler.getTxRxResult(dxl_comm_result)}")
    elif dxl_error != 0:
        print(f"Error velocity 002: {packet_handler.getRxPacketError(dxl_error)}")

# Mover el servomotor
def move_servo(position, speed):
    # Validar entrada de posición y velocidad
    if not (MIN_POSITION <= position <= MAX_POSITION):
        print(f"Error: La posición {position} está fuera del rango permitido ({MIN_POSITION}-{MAX_POSITION}).")
        return
    if speed <= 0 or speed > 32767:
        print(f"Error: La velocidad {speed} debe estar entre 1 y 32767.")
        return

    # Configurar velocidad
    set_velocity(speed)

    # Configurar posición objetivo
    dxl_comm_result, dxl_error = packet_handler.write4ByteTxRx(port_handler, DXL_ID, ADDR_GOAL_POSITION, position)
    if dxl_comm_result != COMM_SUCCESS:
        print(f"Error position 001: {packet_handler.getTxRxResult(dxl_comm_result)}")
    elif dxl_error != 0:
        print(f"Error position 002: {packet_handler.getRxPacketError(dxl_error)}")

try:
    enable_torque()

    # Posiciones objetivo
    pos_45 = angle_to_position(0)
    pos_135 = angle_to_position(270)

    # Velocidades (lento, regular, rápido)
    speed_slow = 20
    speed_regular = 200
    speed_fast = 32000

    # Movimiento lento
    print("Moviendo a 45 grados (lento)...")
    move_servo(pos_45, speed_slow)
    input("Presiona Enter para continuar...")

    print("Moviendo a 135 grados (lento)...")
    move_servo(pos_135, speed_slow)
    input("Presiona Enter para continuar...")

    # Movimiento regular
    print("Moviendo a 45 grados (regular)...")
    move_servo(pos_45, speed_regular)
    input("Presiona Enter para continuar...")

    print("Moviendo a 135 grados (regular)...")
    move_servo(pos_135, speed_regular)
    input("Presiona Enter para continuar...")

    # Movimiento rápido
    print("Moviendo a 45 grados (rápido)...")
    move_servo(pos_45, speed_fast)
    input("Presiona Enter para continuar...")

    print("Moviendo a 135 grados (rápido)...")
    move_servo(pos_135, speed_fast)
    input("Presiona Enter para continuar...")

finally:
    try:
        disable_torque()
    finally:
        port_handler.closePort()
