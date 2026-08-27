# Control de servomotores Dynamixel con Python

Esta aplicación crea una ventana en Python para controlar servomotores Dynamixel usando:

- Slider de ángulo por servo.
- Perilla/knob circular que gira.
- Incrementadores numéricos de ángulo.
- Slider e incrementador de velocidad `Profile Velocity`.
- Botón `+ Añadir servo` para agregar más tarjetas de control.
- Engranaje `⚙` por servo para cambiar ID, ángulo mínimo, ángulo máximo, valor DXL mínimo, valor DXL máximo y velocidad inicial.
- Ping por servo para verificar si está conectado.
- Escaneo de IDs del 1 al 30.
- Torque ON/OFF por servo y para todos.
- Trabajo en segundo plano para evitar que la ventana se congele cuando un servo no responde.

## Instalación

```bash
pip install -r requirements.txt
```

En Linux puede ser necesario dar permiso al puerto:

```bash
sudo usermod -a -G dialout $USER
```

Luego cerrar sesión e ingresar nuevamente.

## Ejecución

```bash
python app.py
```

## Configuración recomendada

Para servos Dynamixel con protocolo 2.0:

- Baudrate: `57600`
- Protocolo: `2.0`
- Puerto Windows común: `COM7`
- Puerto Linux común: `/dev/ttyUSB0`

## Uso básico

1. Conecta el U2D2 o adaptador Dynamixel.
2. Selecciona el puerto.
3. Presiona `Conectar`.
4. Presiona `Ping` en el servo ID 1 o `Escanear IDs 1-30`.
5. Activa `Torque ON`.
6. Mueve el slider, el knob o el número del ángulo.
7. Ajusta la velocidad desde el slider lateral de velocidad.

