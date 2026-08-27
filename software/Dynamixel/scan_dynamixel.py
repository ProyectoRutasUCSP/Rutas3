from dynamixel_sdk import *
import serial.tools.list_ports
import os

# =========================
# CONFIGURACIÓN AUTOMÁTICA
# =========================
def get_default_port():
    if os.name == "nt":          # Windows
        return "COM7"
    else:                        # Linux
        return "/dev/ttyUSB0"

PORT_NAME = get_default_port()
BAUDRATE = 57600
PROTOCOL_VERSION = 2.0

ID_MIN = 1
ID_MAX = 30   # Puedes subirlo hasta 252 si quieres buscar todos

ADDR_MODEL_NUMBER = 0

# =========================
# MOSTRAR PUERTOS DISPONIBLES
# =========================
print("Puertos detectados:")
for p in serial.tools.list_ports.comports():
    print(" -", p.device)

print("\nUsando puerto:", PORT_NAME)

# =========================
# INICIALIZAR COMUNICACIÓN
# =========================
portHandler = PortHandler(PORT_NAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)

if not portHandler.openPort():
    print("No se pudo abrir el puerto.")
    exit()

if not portHandler.setBaudRate(BAUDRATE):
    print("No se pudo configurar el baudrate.")
    portHandler.closePort()
    exit()

print("\nEscaneando servos Dynamixel...")
print("--------------------------------")

ids_encontrados = []

for dxl_id in range(ID_MIN, ID_MAX + 1):
    model_number, dxl_comm_result, dxl_error = packetHandler.ping(portHandler, dxl_id)

    if dxl_comm_result == COMM_SUCCESS:
        print(f"Servo encontrado | ID: {dxl_id} | Modelo: {model_number}")
        ids_encontrados.append(dxl_id)

    elif dxl_error != 0:
        print(f"ID {dxl_id}: Error Dynamixel -> {packetHandler.getRxPacketError(dxl_error)}")

print("--------------------------------")

if ids_encontrados:
    print("IDs encontrados:", ids_encontrados)
else:
    print("No se encontró ningún servo.")

portHandler.closePort()