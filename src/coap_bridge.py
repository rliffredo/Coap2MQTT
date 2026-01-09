import asyncio
import logging
import time
import typing
from asyncio import Future
from contextlib import asynccontextmanager
from typing import Callable, Coroutine, TypeVar

from aioairctrl import CoAPClient
from aioairctrl.coap.encryption import DigestMismatchException
from aiocoap import protocol
from aiocoap.error import LibraryShutdown

import devices
from configuration import CoapConfig
from devices.coap_device import CoapStatus
from mqtt import Connection

logger = logging.getLogger(__name__)


if typing.TYPE_CHECKING:
    import mqtt


class DeviceBridge:
    def __init__(self, host: str, device_name: str, connection_timeout, status_timeout):
        self.observe_wait: Future | None = None
        self.cycle_time = 30
        self.host = host
        self.client: CoAPClient | None = None
        self.last_update = time.monotonic()
        self.state = devices.create(device_name)
        self.was_online = True
        self.running = True
        self.client_connection_lock = asyncio.Lock()
        self.request_in_progress = False
        self.connection_timeout = connection_timeout
        self.status_timeout = status_timeout

    async def _connect(self) -> bool:
        if self.client:
            logger.info("Client already connected")
            return True

        async with self.client_connection_lock:    
            logger.info(f"Starting new COAP connection to {self.host}")
            try:
                if self.connection_timeout > 0:
                    self.client = await asyncio.wait_for(CoAPClient.create(host=self.host), timeout=self.connection_timeout)
                else:
                    self.client = await CoAPClient.create(host=self.host)
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

    async def _request_watchdog(self, publisher) -> None:
        await asyncio.sleep(self.status_timeout )
        # No one cancelled the task, so we should set to offline
        logger.warning(f"No updates for {self.host} in the last 60 seconds: setting to offline")
        await self.signal_offline(publisher)
        await self._disconnect()

    async def shutdown(self) -> None:
        self.running = False
        await self._disconnect()

    async def _cycle_sleep(self):
        async def sleep():
            try:
                await asyncio.sleep(self.cycle_time)
            except asyncio.CancelledError:
                pass
        self.observe_wait = asyncio.create_task(sleep())
        await self.observe_wait

    async def observe(self, publisher: 'mqtt.Connection'):
        logger.info("Observing device %s", self.host)
        await self.signal_offline(publisher)
        while True:
            await self.update_status_from_device(publisher)
            await self._cycle_sleep()

    async def update_status_from_device(self, publisher: Connection) -> None:
        if self.request_in_progress:
            return
        self.request_in_progress = True
        logger.debug("Requesting status for %s", self.host)
        status, max_age = await self._get_status(publisher)
        logger.debug("Got status for %s: %s...", self.host, str(status)[:60])
        await self.signal_state(status, publisher)
        self.cycle_time = max(10, max_age-10)
        self.request_in_progress = False

    async def ensure_connected_client(self):
        while not self.client:
            await self._connect()

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
        try:
            logger.debug("Got update for %s -> %s to %s", property_name, new_value, self.host)
            if property_name not in self.state.properties():
                logger.warning("Cannot update, property %s not found for %s", property_name, self.host)
                return
            setattr(self.state, property_name, new_value)
            commands = self.state.get_commands()
            if not commands:
                logger.warning("Update failed, no commands to send for %s", self.host)
                return
            try:
                logger.debug("Sending command %s to %s", commands, self.host)
                for command in commands:
                    await self._set_control_values(command)
                # await self.update_status_from_device()
                if self.observe_wait:
                    self.observe_wait.cancel()
            except (ValueError, LibraryShutdown) as e:
                logger.warning("Skipping sending command [%s] to device %s: %s", commands, self.host, e)
        except Exception as e:
            logger.exception("Error while sending command to device %s: %s", self.host, e, exc_info=e)

    async def _get_status(self, publisher) -> tuple[CoapStatus, int]:
        try:
            watchdog = asyncio.create_task(self._request_watchdog(publisher))
            await self.ensure_connected_client()
            assert self.client is not None, "Client is connected now"
            values = await self.client.get_status()
            watchdog.cancel()
            return values
        except LibraryShutdown:
            logger.warning("Shutdown in progress on %s, try to reconnect again", self.host)
            return {}, 0
        except (ValueError, DigestMismatchException):
            logger.warning("Skipping current status update of device %s because of validation error", self.host)
            await self._disconnect()
            await self.signal_offline(publisher)
            return {}, 0

    async def _set_control_values(self, command):
        await self.ensure_connected_client()
        assert self.client is not None, "Client is connected now"
        await self.client.set_control_values(data=command)


class MultipleDeviceBridge:
    T = TypeVar('T')

    def __init__(self, config: CoapConfig):
        self.clients = {
            host: DeviceBridge(host, device_name, config.connection_timeout, config.status_timeout)
            for host, device_name in config.devices
        }

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
    async def create(config: CoapConfig):
        client = MultipleDeviceBridge(config)
        yield client
        await client.shutdown()
