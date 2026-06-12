"""Bluez device class"""

from typing import Any, Callable, Coroutine, Optional
from dbus_next import Variant
from dbus_next.aio import MessageBus
from ble_interface import Interface
from ble_gatt import Service, Characteristic, Descriptor
from ble_defines import (
    BLUEZ_BUS_NAME,
    BLUEZ_DEVICE1_IFACE,
    BLUEZ_SERVICE1_IFACE,
    BLUEZ_CHARACTERISTIC1_IFACE,
    BLUEZ_DESCRIPTOR1_IFACE,
    PROPERTIES_IFACE,
    OBJ_MGR_IFACE
)

#import pprint
#pp = pprint.PrettyPrinter(indent=3)

ConnectedType = Callable[[bool], Coroutine[Any, Any, None]]
ServicesResolvedType = Callable[[], Coroutine[Any, Any, None]]

class Device(Interface):
    """Bluez Device1 class"""

    def __init__(self,
                 log: Callable[[str], None],
                 bus: MessageBus,
                 path: str,
                 props: dict[str, Variant]):
        super().__init__(bus, path, BLUEZ_DEVICE1_IFACE)
        self.log = log
        is_connected_prop = props.get("Connected", None)
        self.is_connected = is_connected_prop.value if is_connected_prop else False
        self.log(f"is_connected: {self.is_connected}")
        services_resolved_prop = props.get("ServicesResolved", None)
        self.services_resolved = services_resolved_prop.value if services_resolved_prop else False
        self.log(f"services_resolved: {self.services_resolved}")
        self.connected_listener: Optional[ConnectedType] = None
        self.services_resolved_listener: Optional[ServicesResolvedType] = None
        self.services: dict[str, Service] = {}
        self.characteristics: dict[str, Characteristic] = {}
        self.descriptors: dict[str, Descriptor] = {}
        self.set_props_listener(self.properties_changed_handler)

    def get_service(self, uuid: str) -> Service:
        """Returns the requested service"""
        return self.services[uuid]

    def get_characteristic(self, uuid: str) -> Characteristic:
        """Returns the requested characteristic"""
        return self.characteristics[uuid]

    def get_descriptor(self, uuid: str) -> Descriptor:
        """Returns the requested descriptor"""
        return self.descriptors[uuid]

    def set_connected_listener(self, func: Optional[ConnectedType] = None) -> None:
        """Sets the connected/disconnected listener"""
        self.connected_listener = func

    def set_services_resolved_listener(self, func: Optional[ServicesResolvedType] = None) -> None:
        """Sets the services resolved listener"""
        self.services_resolved_listener = func

    async def connect(self, profile: Optional[str] = None) -> None:
        """Connects the device"""
        if not self.iface:
            return
        if not self.is_connected:
            self.log("Connecting")
            if profile:
                await self.iface.call_connect_profile(profile)
            else:
                await self.iface.call_connect()
        else:
            if self.connected_listener:
                self.log(f"Connected: {self.is_connected}")
                await self.connected_listener(True)
            if self.services_resolved:
                await self.parse_services()

    async def disconnect(self) -> None:
        """Disconnects the device"""
        if not self.iface:
            return
        if self.is_connected:
            await self.iface.call_disconnect()

    async def parse_services(self) -> None:
        """Parses resolved services"""
        self.log("Parsing services")
        info = await self.bus.introspect(BLUEZ_BUS_NAME, "/")
        proxy_obj = self.bus.get_proxy_object(BLUEZ_BUS_NAME, "/", info)
        obj_mgr_iface = proxy_obj.get_interface(OBJ_MGR_IFACE)
        objs = await obj_mgr_iface.call_get_managed_objects()
        for key, obj in objs.items():
            if key.startswith(self.path):
                info = await self.bus.introspect(BLUEZ_BUS_NAME, key)
                proxy_obj = self.bus.get_proxy_object(BLUEZ_BUS_NAME,
                                                      key, info)
                props_iface = proxy_obj.get_interface(PROPERTIES_IFACE)
                if BLUEZ_SERVICE1_IFACE in obj:
                    props = await props_iface.call_get_all(BLUEZ_SERVICE1_IFACE)
                    uuid = props['UUID'].value
                    service = Service(self.bus, key)
                    await service.initialize()
                    self.services[uuid] = service
                    self.log(f"Added service {key}")
                    self.log(f"  {uuid}")
                if BLUEZ_CHARACTERISTIC1_IFACE in obj:
                    props = await props_iface.call_get_all(BLUEZ_CHARACTERISTIC1_IFACE)
                    uuid = props['UUID'].value
                    char = Characteristic(self.bus, key)
                    await char.initialize()
                    self.characteristics[uuid] = char
                    self.log(f"Added characteristic {key}")
                    self.log(f"  {uuid}")
                if BLUEZ_DESCRIPTOR1_IFACE in obj:
                    props = await props_iface.call_get_all(BLUEZ_DESCRIPTOR1_IFACE)
                    uuid = props['UUID'].value
                    desc = Descriptor(self.bus, key)
                    await desc.initialize()
                    self.descriptors[uuid] = desc
                    self.log(f"Added descriptor {key}")
                    self.log(f"  {uuid}")
        if self.services_resolved_listener:
            await self.services_resolved_listener()

    async def properties_changed_handler(self,
                                         iface_name: str,
                                         changed: dict[str, Variant],
                                         _invalidated: list[str]) -> None:
        """Handles property value changes"""
        self.log(f"PropertiesChanged: {iface_name}")
        #self.log(f"   {pp.pformat(changed).replace('\n', '\n   ')}")
        #self.log(f"   {invalidated}")
        is_connected = changed.get("Connected", None)
        if is_connected and is_connected.value != self.is_connected:
            self.is_connected = is_connected.value
            if self.connected_listener:
                await self.connected_listener(self.is_connected)
        services_resolved = changed.get("ServicesResolved", None)
        if services_resolved and services_resolved.value != self.services_resolved:
            self.services_resolved = services_resolved.value
            if self.is_connected and self.services_resolved:
                await self.parse_services()
