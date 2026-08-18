int m1_EL_Start_Stop_D = 7; // EL 
int m1_Signal_D = 6;        // Signal
int m1_ZF_Direction_D = 5;  // Z/F
int m1_VR_speed_D = 4;      // VR

int m1_EL_Start_Stop_I = 11; // EL 
int m1_Signal_I = 10;        // Signal
int m1_ZF_Direction_I = 9;  // Z/F
int m1_VR_speed_I = 8;      // VR

int l_speed = 0;
int a_speed = 0;

void start()
{
  digitalWrite(m1_EL_Start_Stop_D, HIGH);
  digitalWrite(m1_EL_Start_Stop_I, HIGH);
  Serial.println("Motores iniciados");

}

void stop()
{
  digitalWrite(m1_EL_Start_Stop_D, LOW);
  digitalWrite(m1_EL_Start_Stop_I, LOW);
  Serial.println("Motores detenidos");
}

void set_speed(int speed)
{
  l_speed = speed;
  a_speed = speed;
  String msg = "Velocidades ajustadas -> Lineal: " + (String)l_speed + "  |  Angular: " + (String)a_speed;
  Serial.println(msg);
}

void set_L_speed(int speed)
{
  l_speed = speed;
  String msg = "Velocidad linal ajustada -> Lineal: " + (String)l_speed + "  |  Angular: " + (String)a_speed;
  Serial.println(msg);
}

void set_A_speed(int speed)
{
  a_speed = speed;
  String msg = "Velocidad angular ajustada -> Lineal: " + (String)l_speed + "  |  Angular: " + (String)a_speed;
  Serial.println(msg);
}

void forward()
{
  analogWrite(m1_VR_speed_D, l_speed);
  analogWrite(m1_VR_speed_I, l_speed);
  digitalWrite(m1_ZF_Direction_D, HIGH);
  digitalWrite(m1_ZF_Direction_I, LOW);
  Serial.println("Dirección adelante");
}

void backward()
{
  analogWrite(m1_VR_speed_D, l_speed);
  analogWrite(m1_VR_speed_I, l_speed);
  digitalWrite(m1_ZF_Direction_D, LOW);
  digitalWrite(m1_ZF_Direction_I, HIGH);
  Serial.println("Dirección atrás");
}

void turn_right()
{
  analogWrite(m1_VR_speed_D, a_speed);
  analogWrite(m1_VR_speed_I, a_speed);
  digitalWrite(m1_ZF_Direction_D, LOW);
  digitalWrite(m1_ZF_Direction_I, LOW);
  Serial.println("Giro derecha");
}

void turn_left()
{
  analogWrite(m1_VR_speed_D, a_speed);
  analogWrite(m1_VR_speed_I, a_speed);
  digitalWrite(m1_ZF_Direction_D, HIGH);
  digitalWrite(m1_ZF_Direction_I, HIGH);
  Serial.println("Giro izquierda");
}


void setup() {
  Serial.begin(115200);
  
  pinMode(m1_EL_Start_Stop_D, OUTPUT); // Control de encendido/apagado
  pinMode(m1_Signal_D, OUTPUT);        // Control de la señal
  pinMode(m1_ZF_Direction_D, OUTPUT);  // Control de dirección
  pinMode(m1_VR_speed_D, OUTPUT);      // Control de velocidad
  
  pinMode(m1_EL_Start_Stop_I, OUTPUT); // Control de encendido/apagado
  pinMode(m1_Signal_I, OUTPUT);        // Control de la señal
  pinMode(m1_ZF_Direction_I, OUTPUT);  // Control de dirección
  pinMode(m1_VR_speed_I, OUTPUT);      // Control de velocidad
  
  digitalWrite(m1_EL_Start_Stop_D, LOW); // Apagar motor inicialmente
  digitalWrite(m1_EL_Start_Stop_I, LOW); // Apagar motor inicialmente
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "START") {
      start();
    } else if (command == "STOP") {
      stop();
    } else if (command.startsWith("SPEED:")) {
      int speed = command.substring(6).toInt();
      if (speed >= 0 && speed <= 255) {
        set_speed(speed);
      } else {
        Serial.println("Velocidad fuera de rango");
      }
    } else if (command.startsWith("SPEED_L:")) {
      int speed = command.substring(8).toInt();
      if (speed >= 0 && speed <= 255) {
        set_L_speed(speed);
      } else {
        Serial.println("Velocidad fuera de rango");
      }
    } else if (command.startsWith("SPEED_A:")) {
      int speed = command.substring(8).toInt();
      if (speed >= 0 && speed <= 255) {
        set_A_speed(speed);
      } else {
        Serial.println("Velocidad fuera de rango");
      }
    } else if (command.startsWith("DIRECTION:")) {
      String direction = command.substring(10);
      if (direction == "FORWARD") {
        forward();
      } else if (direction == "BACKWARD") {
        backward();
      } else if (direction == "TURN_RIGHT") {
        turn_right();
      } else if (direction == "TURN_LEFT") {
        turn_left();
      } else {
        Serial.println("Dirección no válida");
      }
    } else {
      Serial.println("Comando no reconocido");
    }
  }
}
