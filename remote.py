import array
import asyncio
from collections import namedtuple

import adafruit_irremote
import board
import pulseio

RemoteData = namedtuple("RemoteData", ("raw", "decoded"))


class RemoteOMatic:
    """
    IR Remote setup
    """

    # TODO these items should be configurable via settings.toml
    output_pin = board.SCL1
    output_freq = 38000
    duty_cycle = 2 ** 15

    input_pin = board.SDA1

    # IR receiver setup
    ir_receiver = pulseio.PulseIn(input_pin, maxlen=120, idle_state=True)
    decoder = adafruit_irremote.GenericDecode()

    # Create a 'PulseOut' to send infrared signals on the IR transmitter @ 38KHz
    pulseout = pulseio.PulseOut(
        output_pin, frequency=output_freq, duty_cycle=duty_cycle
    )
    # Create an encoder that will take numbers and turn them into NEC IR pulses with common
    # header, etc.
    encoder = adafruit_irremote.GenericTransmit(
        header=[9000, 4500], one=[560, 1700], zero=[560, 560], trail=0
    )

    @staticmethod
    def pretty_print(prefix, data):
        hex_code = "".join(["%02X " % x for x in data])
        print(f"{prefix} {hex_code}")

    async def remote_read(self, should_stop: bool) -> RemoteData:
        while not should_stop:
            pulses = self.decoder.read_pulses(self.ir_receiver, blocking=False)
            if pulses:
                self.pretty_print("pulses", pulses)
                try:
                    # Attempt to decode the received pulses
                    received_code = self.decoder.decode_bits(pulses)
                    if received_code:
                        self.pretty_print("received", received_code)
                        return RemoteData(pulses, received_code)
                except (
                        adafruit_irremote.IRNECRepeatException
                ):  # Signal was repeated, ignore
                    pass
                except adafruit_irremote.IRDecodeException:  # Failed to decode signal
                    print("Error decoding")
                finally:
                    self.ir_receiver.clear()  # Clear the receiver buffer
                    await asyncio.sleep(1)  # Delay to allow the receiver to settle
            await asyncio.sleep(0.001)

    async def remote_send(self, data: RemoteData):
        try:
            # prefer decoded data: ensure it's an array and send through the encoder
            if data.decoded is not None:
                send_this = array.array("H", data.decoded)
                self.pretty_print("sedning", send_this)
                self.encoder.transmit(self.pulseout, send_this)
            # otherwise assume it's raw bytes and just spit it out
            else:
                send_this = array.array("H", data.raw)
                self.pretty_print("sedning", send_this)
                self.pulseout.send(send_this)
        except Exception:
            print("Error sending")
