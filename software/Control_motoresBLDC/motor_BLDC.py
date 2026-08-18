import serial
import time

# Configuración del puerto serial
#arduino_port = "/dev/ttyACM0"  # Puerto donde está conectado el Arduino
arduino_port = "COM10"  # Puerto donde está conectado el Arduino
baud_rate = 115200            # Velocidad de comunicación serial
timeout = 1                   # Tiempo de espera para respuesta serial

# Inicializar conexión serial
try:
    arduino = serial.Serial(arduino_port, baud_rate, timeout=timeout)
    print(f"Conectado al Arduino en {arduino_port}")
    time.sleep(2)  # Esperar a que Arduino inicialice
except Exception as e:
    print(f"No se pudo conectar al Arduino: {e}")
    exit()

# Función para enviar comandos al Arduino
def send_command(command):
    """
    Envía un comando al Arduino para controlar el motor.
    """
    try:
        arduino.write(f"{command}\n".encode())
        response = arduino.readline().decode().strip()  # Leer respuesta del Arduino
        return response
    except Exception as e:
        print(f"Error enviando comando: {e}")
        return None

# Comandos disponibles
def motor_start():
    print("Iniciando motor...")
    response = send_command("START")
    print(f"Respuesta: {response}")

def motor_stop():
    print("Deteniendo motor...")
    response = send_command("STOP")
    print(f"Respuesta: {response}")

def motor_set_speed(speed):
    """
    Configura la velocidad del motor.
    :param speed: Velocidad en rango de 0 a 255.
    """
    if 0 <= speed <= 255:
        print(f"Configurando velocidad a {speed}...")
        response = send_command(f"SPEED:{speed}")
        print(f"Respuesta: {response}")
    else:
        print("Velocidad fuera de rango (0-255).")

def motor_set_speed_l(speed):
    """
    Configura la velocidad del motor.
    :param speed: Velocidad en rango de 0 a 255.
    """
    if 0 <= speed <= 255:
        print(f"Configurando velocidad lineal a {speed}...")
        response = send_command(f"SPEED_L:{speed}")
        print(f"Respuesta: {response}")
    else:
        print("Velocidad fuera de rango (0-255).")

def motor_set_speed_a(speed):
    """
    Configura la velocidad del motor.
    :param speed: Velocidad en rango de 0 a 255.
    """
    if 0 <= speed <= 255:
        print(f"Configurando velocidad angular a {speed}...")
        response = send_command(f"SPEED_A:{speed}")
        print(f"Respuesta: {response}")
    else:
        print("Velocidad fuera de rango (0-255).")

def motor_set_direction(direction):
    """
    Configura la dirección del motor.
    :param direction: 'FORWARD' para avanzar, 'BACKWARD' para retroceder,
    'TURN_RIGHT' para girar derecha o 'TURN_LEFT' para girar izquierda.
    """
    if direction.upper() in ["FORWARD", "BACKWARD", "TURN_RIGHT", "TURN_LEFT"]:
        print(f"Configurando dirección a {direction}...")
        response = send_command(f"DIRECTION:{direction}")
        print(f"Respuesta: {response}")
    else:
        print("Dirección no válida. Use 'FORWARD' o 'BACKWARD'.")

# Ejemplo de uso
if __name__ == "__main__":
    try:
        
        motor_stop()
        motor_set_speed_l(250)
        motor_set_speed_a(150)
        
        motor_start()
        motor_set_direction("BACKWARD")
        time.sleep(1)  # Esperar 5 segundos con el motor en marcha
        motor_stop()
        time.sleep(1)

        motor_start()
        motor_set_direction("FORWARD")
        time.sleep(1)  # Esperar 5 segundos con el motor en marcha
        motor_stop()
        time.sleep(1)

        motor_start()
        motor_set_direction("TURN_RIGHT")
        time.sleep(1)  # Esperar 5 segundos con el motor en marcha
        motor_stop()
        time.sleep(1)
        
        motor_start()
        motor_set_direction("TURN_LEFT")
        time.sleep(1)  # Esperar 5 segundos con el motor en marcha
        motor_stop()
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("Programa interrumpido por el usuario.")
        motor_stop()
    finally:
        arduino.close()
        print("Conexión cerrada.")
