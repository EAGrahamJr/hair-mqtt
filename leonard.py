import asyncio

import board
import neopixel

from ha_minimqtt import DeviceIdentifier
from ha_minimqtt._compatibility import List
from ha_minimqtt.cp_device import NeoPixelHandler
from ha_minimqtt.cp_mqtt import HAMMFactory
from ha_minimqtt.lights import LightEntity
from ha_minimqtt.select import SelectHandler, SelectEntity
from remote import RemoteOMatic

###################################################################################################
# Control and data
###################################################################################################


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

ispy_client = HAMMFactory.create_wrapper()
# ispy_client._logger.setLevel(logging.DEBUG)

handler = Selector()
select_entity = SelectEntity("learn_remote", "Learning Remote", ispy_device, handler)
select_entity.set_topic_prefix(MQTT_TOPIC)
# select_entity._logger.setLevel(logging.DEBUG)

pixels = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.5)

pixel_handler = NeoPixelHandler(pixels)
pixel_entity = LightEntity("test_pixel", "Pixie", ispy_device, pixel_handler)
pixel_entity.set_topic_prefix(MQTT_TOPIC)

###################################################################################################
# Showtime
###################################################################################################
remmy = RemoteOMatic()


async def set_color(c: tuple = None):
    if c:
        pixel_handler._set_color(color=c)
    else:
        pixel_handler._set_on(False)
    pixel_entity.send_current_state()


async def clear_selection():
    handler.last_selection = "None"
    select_entity.send_current_state()
    await asyncio.sleep(0.1)


async def main():
    read_counter = 1
    stored_commands = {}
    reading_color = (0x4F, 0x00, 0xFF)
    erase_color = (0, 165, 0)
    send_color = (255, 0, 0)

    await ispy_client.start()
    select_entity.start(ispy_client)
    pixel_entity.start(ispy_client)

    while not handler.stopped:
        state = handler.current_state()

        if state == READ:
            await set_color(reading_color)
            read = await remmy.remote_read(handler.stopped)

            # check to see if this is already a thing (raw bytes)
            if read.raw in stored_commands.values():
                print("Already stored")
            else:
                cmd = f"READ {read_counter}"
                read_counter = read_counter + 1
                # TODO check if writing to disk is allowed and save that way also?
                stored_commands[cmd] = read

                # upload to HA
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
            await remmy.remote_send(stored)
            await set_color()

        else:
            await asyncio.sleep(0.1)

    await clear_selection()


asyncio.run(main())
