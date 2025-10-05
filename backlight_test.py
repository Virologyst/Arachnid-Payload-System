import gpiod
import time

# find which chip owns GPIO 24 (or 18)
chip = gpiod.Chip('/dev/gpiochip4')

# request line 24 for output
request = chip.request_lines(
    consumer="backlight-test",
    config={24: gpiod.LineSettings(direction=gpiod.LineDirection.OUTPUT)}
)

print("Toggling GPIO 24...")
for v in [1, 0, 1]:
    request.set_value(24, gpiod.LineValue(v))
    print(f"Value set to {v}")
    time.sleep(2)

request.release()



