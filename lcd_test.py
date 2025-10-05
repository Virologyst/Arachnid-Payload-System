from st7735 import ST7735   # this is correct even for pimoroni-st7735
from PIL import Image, ImageDraw, ImageFont
import subprocess, time

disp = ST7735(
    port=0,
    cs=0,
    dc=25,          # free pin, not owned by SPI
    backlight=24,
    rotation=90,
    spi_speed_hz=4000000,
    bgr=True
)
disp.begin()

# Try to wake controller manually
import spidev
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 4000000

def cmd(c, data=None):
    spi.xfer2([0x00 | c]) if data is None else spi.xfer2([c] + data)

# 1. Sleep out
spi.xfer2([0x11])
time.sleep(0.12)
# 2. Display on
spi.xfer2([0x29])
# 3. Memory write test (fill white)
spi.xfer2([0x2C])
for i in range(160 * 80):
    spi.xfer2([0xFF, 0xFF])

ip = subprocess.getoutput("hostname -I").split()[0]

# img = Image.new("RGB", (160, 80), color=(0, 0, 0))
img = Image.new("RGB", (160, 80), color=(255, 0, 0))  # pure red
draw = ImageDraw.Draw(img)
font = ImageFont.load_default()
draw.text((10, 30), f"IP: {ip}", fill=(255, 255, 255), font=font)

disp.display(img)
print("Buffer displayed — waiting")
time.sleep(5)
print("Displayed:", ip)
time.sleep(2)

spi.close()

