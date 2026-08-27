import time
import mover_servos

port = mover_servos.get_default_port()

servo_IDs = [1, 2, 3, 4, 5, 6]

right_IDs = [2, 4, 6]
left_IDs = [1, 3, 5]
goal_degrees = {1:180, 2:180, 3:180}

# Velocidades fijas por servo
SERVO_VELOCITIES = {
    1: 20,
    2: 20,
    3: 40,
    4: 40,
    5: 70,
    6: 70
}

# Posiciones iniciales
left_initial_degrees = {
    1: 94,
    3: 90,
    5: 90
}

right_initial_degrees = {
    2: 90,
    4: 90,
    6: 90
}

initial_degrees = dict(sorted({
    **left_initial_degrees,
    **right_initial_degrees
}.items()))



'''
mover_servos.connect_to_port("COM4")

print("1 -------------------------------------------------------------------")

mover_servos.read_positions(left_IDs)

print("2 -------------------------------------------------------------------")

mover_servos.enable_torque(left_IDs)
mover_servos.move_servos(left_initial_degrees)
#servos.disable_torque()

time.sleep(2.0)

print("3 -------------------------------------------------------------------")

#servos.enable_torque()
mover_servos.groupBulkWrite.clearParam()
mover_servos.move_servos(left_degrees)
mover_servos.disable_torque(left_IDs)

mover_servos.disconnect_to_port()

'''

def connect():
    """
    Conecta al puerto Dynamixel.
    """
    return mover_servos.connect_to_port(port)


def disconnect():
    """
    Cierra el puerto Dynamixel.
    """
    mover_servos.disconnect_to_port()


def leer_velocidades(degrees):
    return {
        servo_id: SERVO_VELOCITIES.get(servo_id, 40)
        for servo_id in degrees.keys()
    }

def leer_posiciones(IDs = servo_IDs):
    if not connect():
        return

    try:
        mover_servos.read_positions(IDs)
    finally:
        disconnect()

def mover_grupo(degrees, wait=True):
    """
    Mueve un grupo de servos usando la velocidad fija definida para cada ID.

    Ejemplo:
        mover_grupo({1: 90, 2: 120, 3: 150})
    """

    ids = list(degrees.keys())
    velocities = leer_velocidades(degrees)

    mover_servos.enable_torque(ids)

    mover_servos.move_servos(
        degrees=degrees,
        velocities=velocities,
        wait=wait,
        check_ids=True
    )

    mover_servos.disable_torque(ids)

def pos_inicial():
    print("----------------- Posición Inicial -------------------")

    movimientos = [
        initial_degrees,

        {
            1: 94,
            2: 90,
            3: 90,
            4: 90,
            5: 120,
            6: 120
        },

        {
            1: 94,
            2: 90,
            3: 120,
            4: 120,
            5: 120,
            6: 120
        },

        {
            1: 104,
            2: 100,
            3: 120,
            4: 120,
            5: 120,
            6: 120
        },

        initial_degrees
    ]

    if not mover_servos.connect_to_port(port):
        return

    try:
        for movimiento in movimientos:
            mover_grupo(movimiento, wait=True)
            time.sleep(0.1)

    finally:
        mover_servos.disconnect_to_port()

    print("------------- Posición Inicial Completada ---------------")


def saludar():
    print("----------------- Iniciar saludo -------------------")

    movimientos = [
        right_initial_degrees,

        {
            2: 94,
            4: 175,
            6: 175
        },

        {
            2: 73,
            4: 175,
            6: 175
        },

        {
            2: 115,
            4: 175,
            6: 175
        },

        {
            2: 73,
            4: 175,
            6: 175
        },

        {
            2: 115,
            4: 175,
            6: 175
        },

        right_initial_degrees
    ]

    if not mover_servos.connect_to_port(port):
        return

    try:
        for movimiento in movimientos:
            mover_grupo(movimiento, wait=True)
            time.sleep(0.1)

    finally:
        mover_servos.disconnect_to_port()

    print("----------------- Saludo completado -------------------")


if __name__ == "__main__":

    pos_inicial()

    time.sleep(2.0)

    saludar()