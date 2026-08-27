from dynamixel_sdk import *  # Importar SDK de Dynamixel
import time

# Configuración del puerto
PORT_NAME = 'COM4'  # Cambiar según el puerto asignado
BAUDRATE = 57600    # Velocidad en baudios

# Direcciones de memoria para protocolo 1.0
ADDR_TORQUE_ENABLE = 24
ADDR_GOAL_POSITION = 30
ADDR_PRESENT_POSITION = 36

# Configuración del servo
PROTOCOL_VERSION = 1.0  # Usar protocolo 1.0
DXL_ID = 1              # Cambiar al ID de tu servo
TORQUE_ENABLE = 1
TORQUE_DISABLE = 0

# Conversión de grados a posición en Dynamixel
DEGREES_TO_POSITION = 1023 / 300.0

# Calcular posiciones
POSITION_180 = int(180 * DEGREES_TO_POSITION)  # 180 grados
POSITION_PLUS_90 = int(100 * DEGREES_TO_POSITION)  # +90 grados
POSITION_MINUS_90 = int(-100 * DEGREES_TO_POSITION + 512)  # -90 grados

# Inicializar el puerto y el paquete
port_handler = PortHandler(PORT_NAME)
packet_handler = PacketHandler(PROTOCOL_VERSION)

# Abrir puerto
if not port_handler.openPort():
    print("Error: No se pudo abrir el puerto. Verifica la conexión y el nombre del puerto.")
    quit()

# Configurar velocidad en baudios
if not port_handler.setBaudRate(BAUDRATE):
    print("Error: No se pudo configurar la velocidad en baudios.")
    port_handler.closePort()
    quit()

# Habilitar torque
dxl_comm_result, dxl_error = packet_handler.write1ByteTxRx(port_handler, DXL_ID, ADDR_TORQUE_ENABLE, TORQUE_ENABLE)
if dxl_comm_result != COMM_SUCCESS:
    print(f"Error en comunicación: {packet_handler.getTxRxResult(dxl_comm_result)}")
elif dxl_error != 0:
    print(f"Error en el servo: {packet_handler.getRxPacketError(dxl_error)}")

# Función para mover el servo a una posición
def move_servo(position, delay):
    dxl_comm_result, dxl_error = packet_handler.write2ByteTxRx(port_handler, DXL_ID, ADDR_GOAL_POSITION, position)
    if dxl_comm_result != COMM_SUCCESS:
        print(f"Error en comunicación: {packet_handler.getTxRxResult(dxl_comm_result)}")
    elif dxl_error != 0:
        print(f"Error en el servo: {packet_handler.getRxPacketError(dxl_error)}")
    else:
        print(f"Servo movido a posición: {position}")
    time.sleep(delay)

# Inicialmente mover a 180 grados
print("Posicionando en 180 grados...")
move_servo(POSITION_180, 1.3)
x = [1 , 8 , 9 ]
# Realizar el movimiento 5 veces
for i in range(5):
    print(f"Repetición {i + 1}: Moviendo a +90 grados...")
    move_servo(POSITION_PLUS_90, 1.3)

    print(f"Repetición {i + 1}: Moviendo a -90 grados...")
    move_servo(POSITION_MINUS_90, 1.3)

    print(len(x))
# Deshabilitar torque
dxl_comm_result, dxl_error = packet_handler.write1ByteTxRx(port_handler, DXL_ID, ADDR_TORQUE_ENABLE, TORQUE_DISABLE)
if dxl_comm_result != COMM_SUCCESS:
    print(f"Error en comunicación: {packet_handler.getTxRxResult(dxl_comm_result)}")
elif dxl_error != 0:
    print(f"Error en el servo: {packet_handler.getRxPacketError(dxl_error)}")

# Cerrar puerto
port_handler.closePort()
