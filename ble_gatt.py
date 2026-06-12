"""Bluez Gatt classes using dbus-next and asyncio"""
from dbus_next.aio import MessageBus
from ble_defines import (
    BLUEZ_SERVICE1_IFACE,
    BLUEZ_CHARACTERISTIC1_IFACE,
    BLUEZ_DESCRIPTOR1_IFACE
)

from ble_interface import Interface

class Service(Interface):
    """Bluez Service1 class"""

    def __init__(self, bus: MessageBus, path: str):
        super().__init__(bus, path, BLUEZ_SERVICE1_IFACE)

class Characteristic(Interface):
    """Bluez Characteristic1 class"""

    def __init__(self, bus: MessageBus, path: str):
        super().__init__(bus, path, BLUEZ_CHARACTERISTIC1_IFACE)

class Descriptor(Interface):
    """Bluez Descriptor1 class"""

    def __init__(self, bus: MessageBus, path: str):
        super().__init__(bus, path, BLUEZ_DESCRIPTOR1_IFACE)
