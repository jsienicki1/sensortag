"""Bluez peripheral example using dbus-next and asyncio"""
import asyncio
import curses
import struct
from typing import Optional
from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType

from ble_adapter import Adapter
from ble_device import Device

class Screen:
    """Screen management class"""

    def __init__(self, height: int):
        self.height = height
        self.lines: list[str] = []
        self.telemetry_win = curses.newwin(height, 40, 0, 0)
        self.telemetry_win.clear()
        divider = curses.newpad(1, curses.COLS)
        divider.clear()
        divider.addstr(0, 0, "="*(curses.COLS-1))
        divider.refresh(0, 0, height, 0, height, curses.COLS-1)
        self.output_win = curses.newpad(curses.LINES-(height+1), 120)
        self.output_win.clear()

    def log(self, line: str) -> None:
        """Curses print function"""
        self.lines.append(line + "\n")
        if len(self.lines) > (curses.LINES-(self.height+2)):
            self.lines = self.lines[1:]
        for idx, entry in enumerate(self.lines):
            self.output_win.addstr(idx, 0, entry)
        self.output_win.refresh(0, 0, self.height+1, 0, curses.LINES-1, curses.COLS-1)

    def telemetry(self, row: int, column: int, line: str) -> None:
        """Curses telemetry output function"""
        self.telemetry_win.addstr(row, column, line)
        self.telemetry_win.refresh()

class Controller:
    """Controller class"""

    def __init__(self, adapter_name: str):
        self.bus: Optional[MessageBus] = None
        self.done = False
        self.adapter_name = adapter_name
        self.adapter: Optional[Adapter] = None
        self.device: Optional[Device] = None
        self.is_discovering = False
        self.screen = Screen(11)

    def log(self, line: str) -> None:
        """Log to screen output window"""
        self.screen.log(line)

    def telemetry(self, row: int, column: int, line: str) -> None:
        """Output to telemetry window"""
        self.screen.telemetry(row, column, line)

    async def device_added_handler(self, path: str, props: dict[str, Variant]) -> None:
        """Check for a SensorTag device"""
        if 'UUIDs' not in props:
            return
        if '0000aa80-0000-1000-8000-00805f9b34fb' not in props['UUIDs'].value:
            return
        self.log("Found a SensorTag")
        if self.bus is None:
            self.log("No message bus!")
            return
        if self.adapter is None:
            self.log("No adapter!")
            return
        # Device found, so create a new device instance
        self.device = Device(self.log, self.bus, path, props)
        self.device.set_services_resolved_listener(self.services_resolved_handler)
        await self.device.initialize()

        self.log("Stopping discovery")
        if self.is_discovering:
            await self.adapter.get_iface().call_stop_discovery()
            self.is_discovering = False
        await self.device.connect()

    async def services_resolved_handler(self) -> None:
        """Services resolved handler (should be overridden)"""
        self.log("Services resolved")

        if self.device is None:
            self.log("No device!")
            return

        self.log("Writing optical period")
        await asyncio.sleep(1)
        char = self.device.get_characteristic("f000aa73-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([100]), {})
        self.log("Writing optical enable")
        char = self.device.get_characteristic("f000aa72-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([1]), {})
        self.log("Starting optical notifications")
        char = self.device.get_characteristic("f000aa71-0451-4000-b000-000000000000")
        char.get_props_iface().on_properties_changed(self.light_changed)
        await char.get_iface().call_start_notify()

        self.log("Writing humidity period")
        char = self.device.get_characteristic("f000aa23-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([100]), {})
        self.log("Writing humidity enable")
        char = self.device.get_characteristic("f000aa22-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([1]), {})
        self.log("Starting humidity notifications")
        char = self.device.get_characteristic("f000aa21-0451-4000-b000-000000000000")
        char.get_props_iface().on_properties_changed(self.humidity_changed)
        await char.get_iface().call_start_notify()

        self.log("Writing barometric pressure period")
        char = self.device.get_characteristic("f000aa44-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([100]), {})
        self.log("Writing barometric pressure enable")
        char = self.device.get_characteristic("f000aa42-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([1]), {})
        self.log("Starting barometric pressure notifications")
        char = self.device.get_characteristic("f000aa41-0451-4000-b000-000000000000")
        char.get_props_iface().on_properties_changed(self.barometric_changed)
        await char.get_iface().call_start_notify()

        self.log("Writing movement period")
        char = self.device.get_characteristic("f000aa83-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([100]), {})
        self.log("Writing movement enable")
        char = self.device.get_characteristic("f000aa82-0451-4000-b000-000000000000")
        await char.get_iface().call_write_value(bytes([255, 1]), {})
        self.log("Starting movement notifications")
        char = self.device.get_characteristic("f000aa81-0451-4000-b000-000000000000")
        char.get_props_iface().on_properties_changed(self.movement_changed)
        await char.get_iface().call_start_notify()

    def light_changed(self,
                      _iface_name: str,
                      changed: dict[str, Variant],
                      _invalidated: list[str]) -> None:
        """Handle light changes"""
        if 'Value' in changed:
            barray = changed['Value'].value
            value = struct.unpack('H', barray)[0]
            m = value & 0x0FFF
            e = (value & 0xF000) >> 12
            if e == 0:
                e = 1
            else:
                e = 2 << (e - 1)
            l = m + (0.01 * e)
            self.telemetry(0, 0, f"Light is {l:4.0f}")

    def humidity_changed(self,
                         _iface_name: str,
                         changed: dict[str, Variant],
                         _invalidated: list[str]) -> None:
        """Handle humidity changes"""
        if 'Value' in changed:
            barray = changed['Value'].value[0:2]
            value = struct.unpack('H', barray)[0]
            value = ((value * 165.0) / 65536 - 40) * 1.8 + 32
            self.telemetry(1, 0, f"Temperature is {value:4.1f}")
            barray = changed['Value'].value[2:4]
            value = struct.unpack('H', barray)[0]
            value &= ~0x0003
            value = (value * 100.0) / 65536
            self.telemetry(2, 0, f"Humidity is {value:4.1f}")

    def barometric_changed(self,
                           _iface_name: str,
                           changed: dict[str, Variant],
                           _invalidated: list[str]) -> None:
        """Handle barometric pressure changes"""
        if 'Value' in changed:
            barray = changed['Value'].value[0:3] + bytes([0])
            value = struct.unpack('I', barray)[0]
            value = (value * 1.8) / 100 + 32
            self.telemetry(3, 0, f"Temperature is {value:4.1f}")
            if int(changed['Value'].value[5]):
                barray = changed['Value'].value[3:6] + bytes([0])
                value = struct.unpack('I', barray)[0]
                value = value / 3386.4
                self.telemetry(4, 0, f"Biometric Pressure is {value:4.1f}")

    def movement_changed(self,
                         _iface_name: str,
                         changed: dict[str, Variant],
                         _invalidated: list[str]) -> None:
        """Handle movement changes"""
        if 'Value' in changed:
            barray = changed['Value'].value[0:2]
            value = struct.unpack('h', barray)[0]
            value = (value * 1.0) / (65536.0 / 500.0)
            self.telemetry(5, 0, f"GyroX is {value:4.1f}")
            barray = changed['Value'].value[2:4]
            value = struct.unpack('h', barray)[0]
            value = (value * 1.0) / (65536.0 / 500.0)
            self.telemetry(6, 0, f"GyroY is {value:4.1f}")
            barray = changed['Value'].value[4:6]
            value = struct.unpack('h', barray)[0]
            value = (value * 1.0) / (65536.0 / 500.0)
            self.telemetry(7, 0, f"GyroZ is {value:4.1f}")
            barray = changed['Value'].value[6:8]
            value = struct.unpack('h', barray)[0]
            value = (value * 1.0) / (32768.0 / 4.0)
            self.telemetry(8, 0, f"AccX is {value:4.1f}")
            barray = changed['Value'].value[8:10]
            value = struct.unpack('h', barray)[0]
            value = (value * 1.0) / (32768.0 / 4.0)
            self.telemetry(9, 0, f"AccY is {value:4.1f}")
            barray = changed['Value'].value[10:12]
            value = struct.unpack('h', barray)[0]
            value = (value * 1.0) / (32768.0 / 4.0)
            self.telemetry(10, 0, f"AccZ is {value:4.1f}")

    async def main(self) -> None:
        """Main program loop"""
        # Connect to the system message bus
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        if self.bus is None:
            self.log("Unable to get message bus!")
            return
        # Create an instance of the specified adapter
        self.adapter = Adapter(self.log, self.bus, self.adapter_name)
        if self.adapter is None:
            self.log(f"Unable to get adapter {self.adapter_name}!")
            return
        self.adapter.set_device_added_listener(self.device_added_handler)
        await self.adapter.initialize()
        # Check for previously discovered devices
        await self.adapter.get_devices()
        await asyncio.sleep(1)
        # Enter the polling loop, turning discovery on/off until the SensorTag is discovered
        while True:
            if self.device is None:
                await self.adapter.get_iface().call_start_discovery()
                self.is_discovering = True
            await asyncio.sleep(5)
            if self.device is None:
                await self.adapter.get_iface().call_stop_discovery()
                self.is_discovering = False
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Create the controller instance and run the main function
    # until the user quites the program
    stdscr = curses.initscr()
    # Set curses options
    stdscr.clear()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)
    loop = asyncio.new_event_loop()
    controller = Controller("hci0")
    try:
        loop.run_until_complete(controller.main())
    except KeyboardInterrupt:
        if controller.device:
            loop.run_until_complete(
                controller.device.get_iface().call_disconnect())
    # Set display options back to normal
    curses.curs_set(1)
    curses.endwin()
