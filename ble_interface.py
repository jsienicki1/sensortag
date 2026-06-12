"""BLE interface class"""
from asyncio import get_running_loop
from typing import Any, Callable, Coroutine, Optional
from dbus_next import Variant
from dbus_next.aio import MessageBus, ProxyInterface

from ble_defines import (
    BLUEZ_BUS_NAME,
    PROPERTIES_IFACE
)

class UninitializedInterface(Exception):
    """Exception class for uninitialized interfaces"""

PropsChangedType = Callable[[str, dict[str, Variant], list[str]], Coroutine[Any, Any, None]]

class Interface:
    """Base class for all BLE interface classes"""

    def __init__(self,
                 bus: MessageBus,
                 path: str,
                 iface_name: str):
        self.bus = bus
        self.path = path
        self.iface_name = iface_name
        self.props_listener: Optional[PropsChangedType] = None
        self.iface: Optional[ProxyInterface] = None
        self.props_iface: Optional[ProxyInterface] = None

    def set_props_listener(self, func: Optional[PropsChangedType] = None) -> None:
        """Sets the properties changed listener"""
        self.props_listener = func

    def get_path(self) -> str:
        """Returns the adapter path"""
        return self.path

    def get_iface(self) -> ProxyInterface:
        """Returns the interface"""
        if not self.iface:
            raise UninitializedInterface("Uninitialized interface")
        return self.iface

    def get_props_iface(self) -> ProxyInterface:
        """Returns the properties interface"""
        if not self.props_iface:
            raise UninitializedInterface("Uninitialized properties interface")
        return self.props_iface

    async def initialize(self) -> None:
        """Initializes the adapter interface"""
        info = await self.bus.introspect(BLUEZ_BUS_NAME, self.path)
        proxy_obj = self.bus.get_proxy_object(BLUEZ_BUS_NAME, self.path, info)
        self.iface = proxy_obj.get_interface(self.iface_name)
        self.props_iface = proxy_obj.get_interface(PROPERTIES_IFACE)
        self.props_iface.on_properties_changed(self.properties_changed)

    def properties_changed(self,
                           iface_name: str,
                           changed: dict[str, Variant],
                           invalidated: list[str]) -> None:
        """Properties changed handler"""
        if self.props_listener:
            loop = get_running_loop()
            loop.create_task(self.props_listener(iface_name, changed, invalidated))
