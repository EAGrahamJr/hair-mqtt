import array
import asyncio
import time
from collections import namedtuple

import adafruit_irremote
import board
import neopixel
import pulseio

from ha_minimqtt import DeviceIdentifier
from ha_minimqtt._compatibility import List
from ha_minimqtt.cp_device import NeoPixelHandler
from ha_minimqtt.cp_mqtt import HAMMFactory
from ha_minimqtt.lights import LightEntity
from ha_minimqtt.select import SelectHandler, SelectEntity

###################################################################################################
# IR Remote setup
###################################################################################################

# TODO these items should be configurable via settings.toml
output_pin = board.SCL1
output_freq = 38000
duty_cycle = 2 ** 15

input_pin = board.SDA1

# IR receiver setup
ir_receiver = pulseio.PulseIn(input_pin, maxlen=120, idle_state=True)
decoder = adafruit_irremote.GenericDecode()

# Create a 'PulseOut' to send infrared signals on the IR transmitter @ 38KHz
pulseout = pulseio.PulseOut(output_pin, frequency=output_freq, duty_cycle=duty_cycle)
# Create an encoder that will take numbers and turn them into NEC IR pulses with common
# header, etc.
encoder = adafruit_irremote.GenericTransmit(header=[9000, 4500],
                                            one=[560, 1700],
                                            zero=[560, 560],
                                            trail=0)


def pretty_print(prefix, data):
    hex_code = ''.join(["%02X " % x for x in data])
    print(f"{prefix} {hex_code}")


###################################################################################################
# Control and data
###################################################################################################

RemoteData = namedtuple("RemoteData", ("raw", "decoded"))

STOP = "STOP"
READ = "READ"
ERASE = "ERASE"
OG_OPTIONS = [STOP, READ, ERASE]


class Selector(SelectHandler):
    last_selection = ""
    option_list = OG_OPTIONS

    @property
    def options(self) -> List[str]:
        return self.option_list

    def handle_command(self, payload: str):
        # TODO invoke remote stuff directly?
        self.last_selection = payload

    def current_state(self) -> str:
        return self.last_selection

    @property
    def stopped(self):
        return self.last_selection == STOP


# topic prefix for MQTT
MQTT_TOPIC = "kobots_ha"

ispy_device = DeviceIdentifier("kobots", "QtPy ESP32 S3", identifier="i-spy")

ispy_wrapper = HAMMFactory.create_wrapper()
# ispy_wrapper._logger.setLevel(logging.DEBUG)

handler = Selector()
select_entity = SelectEntity("learn_remote", "Learning Remote", ispy_device, handler)
select_entity.set_topic_prefix(MQTT_TOPIC)
# select_entity._logger.setLevel(logging.DEBUG)

pixels = neopixel.NeoPixel(board.NEOPIXEL, 1)

pixel_handler = NeoPixelHandler(pixels)
pixel_entity = LightEntity("test_pixel", "Pixie", ispy_device, pixel_handler)
pixel_entity.set_topic_prefix(MQTT_TOPIC)


# pixel_entity._logger.setLevel(logging.DEBUG)

###################################################################################################
# Showtime
###################################################################################################

async def remote_read() -> RemoteData:
    while not handler.stopped:
        pulses = decoder.read_pulses(ir_receiver, blocking=False)
        if pulses:
            pretty_print("pulses", pulses)
            try:
                # Attempt to decode the received pulses
                received_code = decoder.decode_bits(pulses)
                if received_code:
                    pretty_print("received", received_code)
                    return RemoteData(pulses, received_code)
            except adafruit_irremote.IRNECRepeatException:  # Signal was repeated, ignore
                pass
            except adafruit_irremote.IRDecodeException:  # Failed to decode signal
                print("Error decoding")
            finally:
                ir_receiver.clear()  # Clear the receiver buffer
                time.sleep(1)  # Delay to allow the receiver to settle
        await asyncio.sleep(.001)


async def remote_send(data: RemoteData):
    if not handler.stopped:
        try:
            # prefer decoded data: ensure it's an array and send through the encoder
            if data.decoded is not None:
                send_this = array.array('H', data.decoded)
                pretty_print("sedning", send_this)
                encoder.transmit(pulseout, send_this)
            # otherwise assume it's raw bytes and just spit it out
            else:
                send_this = array.array('H', data.raw)
                pretty_print("sedning", send_this)
                pulseout.send(send_this)
        except Exception:
            print("Error sending")


async def set_color(c: tuple = None):
    if c:
        pixel_handler._set_color(color=c)
    else:
        pixel_handler._set_on(False)
    pixel_entity.send_current_state()


async def clear_selection():
    handler.last_selection = "None"
    select_entity.send_current_state()
    await asyncio.sleep(.01)


async def main():
    read_counter = 1
    stored_commands = {}
    reading_color = (0x4F, 0x00, 0xFF)
    erase_color = (0, 165, 0)
    send_color = (255, 0, 0)

    await ispy_wrapper.start()
    select_entity.start(ispy_wrapper)
    pixel_entity.start(ispy_wrapper)

    while not handler.stopped:
        state = handler.current_state()

        if state == READ:
            await set_color(reading_color)
            read = await remote_read()

            # check to see if this is already a thing (raw bytes)
            if read.raw in stored_commands.values():
                print("Already stored")
            else:
                cmd = f"READ {read_counter}"
                read_counter = read_counter + 1
                # TODO check if writing to disk is allowed and save that way also
                stored_commands[cmd] = read
                handler.option_list.append(cmd)
                select_entity.send_discovery()
            await clear_selection()
            await set_color()

        elif state == ERASE:
            await clear_selection()
            await set_color(erase_color)
            handler.option_list = OG_OPTIONS
            select_entity.send_discovery()
            await asyncio.sleep(1)
            await set_color()

        elif state in stored_commands.keys():
            await clear_selection()
            await set_color(send_color)
            stored = stored_commands[state]
            await remote_send(stored)
            await set_color()

        else:
            await asyncio.sleep(.5)


asyncio.run(main())
