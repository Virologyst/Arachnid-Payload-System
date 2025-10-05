import lgpio
import time

chip = lgpio.gpiochip_open(0)
pin = 24  # backlight
lgpio.gpio_claim_output(chip, pin)
lgpio.gpio_write(chip, pin, 1)
time.sleep(5)
lgpio.gpio_write(chip, pin, 0)
lgpio.gpiochip_close(chip)
