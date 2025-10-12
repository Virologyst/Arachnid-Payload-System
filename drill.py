# --- Drill service (Nicky) ---
# Import Libraries needed to run code
from gpiozero import AngularServo
from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

while (1):
    # Initialize Servo (GPIO pin 13)
    servo = AngularServo(
        13,
        min_angle=0,
        max_angle=360,
        min_pulse_width=0.0005,
        max_pulse_width=0.0025
    )

    def Drill():
        print("Starting drill sequence...")
        servo.angle = 360
        time.sleep(93)  # 93 which is almost 1.5 minutes
        servo.angle = 0
        time.sleep(93)
        servo.angle = 90
        print("Drill sequence completed.")