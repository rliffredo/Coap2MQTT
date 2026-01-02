import asyncio
import logging
import time
import typing
from contextlib import asynccontextmanager
from typing import Callable, Coroutine, TypeVar

from aioairctrl import CoAPClient
from aiocoap import protocol

import devices

logger = logging.getLogger(__name__)


if typing.TYPE_CHECKING:
    import mqtt


class DeviceBridge:
    def __init__(self, host: str, device_name: str):
        self.host = host
        self.client: CoAPClient | None = None
        self.last_update = time.monotonic()
        self.state = devices.create(device_name)
        self.was_online = True
        self.running = True
        self.client_connection_lock = asyncio.Lock()

    async def _connect(self) -> bool:
        async with self.client_connection_lock:
            if self.client:
                logger.info("Client already connected")
                return True
    
            logger.info(f"Starting new COAP connection to {self.host}")
            try:
                self.client = await asyncio.wait_for(CoAPClient.create(host=self.host), timeout=120)
                logger.info(f"Established new COAP connection to {self.host}")
                return True
            except asyncio.TimeoutError:
                # TODO: after a timeout, we usually enter in a "NetworkError" -- most probably, the
                #       cancellation left some unwanted state. We should clean up better, or at least
                #       restart everything?
                logger.error(f"Timeout while trying to establish connection to {self.host}")
                return False
            except protocol.error.NetworkError as e:
                logger.error(f"Error while trying to establish connection to {self.host}: {e}")
                await asyncio.sleep(10)
                return False

    async def _disconnect(self):
        async with self.client_connection_lock:
            if not self.client:
                return
            await self.client.shutdown()
            self.client = None

    async def _start_watchdog(self, publisher) -> None:
        logger.info("Starting watchdog loop for %s", self.host)
        while self.running:
            if self.was_online and not self.is_online:
                logger.warning(f"No updates for {self.host} in the last 60 seconds: setting to offline")
                await self.signal_offline(publisher)
            await asyncio.sleep(60)

    async def shutdown(self) -> None:
        self.running = False
        await self._disconnect()

    async def observe(self, publisher: 'mqtt.Connection'):
        logger.info("Observing device %s", self.host)
        await self.signal_offline(publisher)
        watchdog_task = asyncio.create_task(self._start_watchdog(publisher))
        while self.running:
            await self.ensure_connected_client()
            assert self.client is not None, "Client is connected now"
            await self.signal_online(publisher)
            try:
                async for status in self.client.observe_status():
                    await self.signal_state(status, publisher)
            except ValueError:
                logger.warning("Skipping current status update of device %s because of validation error", self.host)
                await self._disconnect()
                await self.signal_offline(publisher)

        await watchdog_task  # do we really need to wait for it to complete?

    async def ensure_connected_client(self):
        while not self.client:
            await self._connect()

    @property
    def is_online(self) -> CoAPClient | None | bool:
        return self.client and time.monotonic() - self.last_update < 60

    async def signal_state(self, status, publisher):
        self.last_update = time.monotonic()
        self.state.update(status)
        await self.signal_online(publisher)
        await publisher.publish_state(self.host, self.state)

    async def signal_online(self, publisher):
        if self.was_online:
            return
        self.was_online = True
        logger.info("Device %s is now ONLINE", self.host)
        await publisher.publish_online(self.host)

    async def signal_offline(self, publisher):
        if not self.was_online:
            return
        self.was_online = False
        logger.info("Device %s is now OFFLINE", self.host)
        await publisher.publish_offline(self.host)

    async def send_update(self, property_name, new_value: str):
        logger.debug("Got update for %s -> %s to %s", property_name, new_value, self.host)
        if property_name not in self.state.properties():
            logger.warning("Update failed, property %s not found for %s", property_name, self.host)
            return
        setattr(self.state, property_name, new_value)
        commands = self.state.get_commands()
        if not commands:
            logger.warning("Update failed, no commands to send for %s", self.host)
            return
        await self.ensure_connected_client()
        assert self.client is not None, "Client is connected now"
        try:
            logger.debug("Sending command %s to %s", commands, self.host)
            for command in commands:
                await self.client.set_control_values(data=command)
        except ValueError as e:
            logger.warning("Skipping sending command [%s] to device %s: %s", commands, self.host, e)


class MultipleDeviceBridge:
    T = TypeVar('T')

    def __init__(self, hosts: list[tuple[str, str]]):
        self.clients = {host: DeviceBridge(host, device_name) for host, device_name in hosts}

    async def send_update(self, device: str, property_name: str, new_value: str):
        await self.clients[device].send_update(property_name, new_value)

    async def observe(self, publisher: 'mqtt.Connection') -> None:
        logger.info("Started to observe status")
        await MultipleDeviceBridge._execute_many(lambda client: client.observe(publisher), self.clients.values())

    async def shutdown(self):
        await MultipleDeviceBridge._execute_many(lambda client: client.shutdown(), self.clients.values())

    @staticmethod
    async def _execute_many(f: Callable[[T], Coroutine], cont: typing.Iterable[T]):
        async with asyncio.TaskGroup() as task_group:
            coap_tasks = [task_group.create_task(f(c)) for c in cont]
        return [task.result() for task in coap_tasks]

    @staticmethod
    @asynccontextmanager
    async def create(hosts: list[tuple[str, str]]):
        client = MultipleDeviceBridge(hosts)
        yield client
        await client.shutdown()
