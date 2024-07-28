# hair-mqtt

A "learning" IR remote using CircuitPython, MQTT, and HomeAssistant.

The target development platform:
> Adafruit CircuitPython 9.1.0 on 2024-07-10

Hardware:

- Adafruit QT Py ESP32-S3 4MB Flash 2MB PSRAM with ESP32S3
- Adafruit Infrared IR Remote Transceiver breakout board

## Packages Used

- adafruit_pixelbuf==2.0.4
- neopixel==6.3.11
- adafruit_connection_manager==3.1.1
- adafruit_ticks==1.0.13
- adafruit_irremote==5.0.1
- adafruit_logging==5.4.0
- adafruit_minimqtt==7.10.0
- asyncio==1.3.2

This is also using the very beta version of my [HA MiniMQTT](EAGrahamJr/ha-minimqtt) library for the selector and
neopixel control.
