"""Bluez adapter class"""

from asyncio import get_running_loop
from typing import Any, Callable, Coroutine, Optional
from dbus_next import Variant
from dbus_next.aio import MessageBus, ProxyInterface
from ble_interface import Interface
from ble_defines import (
    BLUEZ_BUS_NAME,
    BLUEZ_PATH,
    BLUEZ_ADAPTER1_IFACE,
    BLUEZ_DEVICE1_IFACE,
    OBJ_MGR_IFACE
)

#import pprint
#pp = pprint.PrettyPrinter(indent=3)

DeviceAddedType = Callable[[str, dict[str, Variant]], Coroutine[Any, Any, None]]
DeviceRemovedType = Callable[[str], Coroutine[Any, Any, None]]

class Adapter(Interface):
    """Bluez Adapter1 class"""

    def __init__(self,
                 log: Callable[[str], None],
                 bus: MessageBus,
                 name: str) -> None:
        super().__init__(bus, BLUEZ_PATH + "/" + name, BLUEZ_ADAPTER1_IFACE)
        self.log = log
        self.name = name
        self.obj_mgr_iface: Optional[ProxyInterface] = None
        self.device_added_listener: Optional[DeviceAddedType] = None
        self.device_removed_listener: Optional[DeviceRemovedType] = None

    async def initialize(self) -> None:
        """Initializes the adapter interfaces"""
        await super().initialize()
        info = await self.bus.introspect(BLUEZ_BUS_NAME, "/")
        proxy_obj = self.bus.get_proxy_object(BLUEZ_BUS_NAME, "/", info)
        self.obj_mgr_iface = proxy_obj.get_interface(OBJ_MGR_IFACE)
        self.obj_mgr_iface.on_interfaces_added(self.interfaces_added)
        self.obj_mgr_iface.on_interfaces_removed(self.interfaces_removed)

    def set_device_added_listener(self, func: Optional[DeviceAddedType] = None) -> None:
        """Sets the device added listener"""
        self.device_added_listener = func

    def set_device_removed_listener(self, func: Optional[DeviceRemovedType] = None) -> None:
        """Sets the device removed listener"""
        self.device_removed_listener = func

    def interfaces_added(self, path: str, params: dict[str, dict[str, Variant]]) -> None:
        """Interfaces added handler"""
        path_elems = path.split('/')
        dev_adapter_name = path_elems[-2]
        if self.name != dev_adapter_name:
            return
        self.log(f"InterfacesAdded: {path}")
        if BLUEZ_DEVICE1_IFACE in params:
            if self.device_added_listener:
                loop = get_running_loop()
                loop.create_task(self.device_added_listener(path, params[BLUEZ_DEVICE1_IFACE]))

    def interfaces_removed(self, path: str, interfaces: list[str]) -> None:
        """Interfaces removed handler"""
        path_elems = path.split('/')
        dev_adapter_name = path_elems[-2]
        if self.name != dev_adapter_name:
            return
        self.log(f"InterfacesRemoved: {path}")
        if BLUEZ_DEVICE1_IFACE in interfaces:
            if self.device_removed_listener:
                loop = get_running_loop()
                loop.create_task(self.device_removed_listener(path))

    async def get_devices(self) -> None:
        """Parses discovered devices"""
        if not self.obj_mgr_iface:
            return
        objs = await self.obj_mgr_iface.call_get_managed_objects()
        for key, obj in objs.items():
            self.interfaces_added(key, obj)
