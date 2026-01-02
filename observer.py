import asyncio
import logging
import time
import typing
from contextlib import contextmanager
from typing import Callable, Coroutine, TypeVar

from aioairctrl import CoAPClient
from aiocoap import protocol

import philips

logger = logging.getLogger(__name__)


if typing.TYPE_CHECKING:
    from publisher import MQTTPublisher


class DeviceObserver:
    def __init__(self, host: str):
        self.host = host
        self.client: CoAPClient | None = None
        self.last_update = time.monotonic()
        self.state = philips.Hu1508({})
        self.was_online = True
        self.running = True

    async def _connect(self) -> bool:
        # TODO: better synchronization!
        if self.client:
            logger.info("Client already connected")
            return True

        logger.info(f"Starting new COAP connection to {self.host}")
        try:
            self.client = await asyncio.wait_for(CoAPClient.create(host=self.host), timeout=120)
            logger.info(f"Established new COAP connection to {self.host}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout while trying to establish connection to {self.host}")
            await self._shutdown()
            return False
        except protocol.error.NetworkError as e:
            logger.error(f"Error while trying to establish connection to {self.host}: {e}")
            await self._shutdown()
            await asyncio.sleep(10)
            return False

    async def _shutdown(self):
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

    async def stop(self) -> None:
        self.running = False
        await self._shutdown()

    async def observe(self, publisher: 'MQTTPublisher'):
        logger.info("Observing device %s", self.host)
        await self.signal_offline(publisher)
        watchdog_task = asyncio.create_task(self._start_watchdog(publisher))
        while self.running:
            await self.ensure_connected_client()
            await self.signal_online(publisher)
            try:
                async for status in self.client.observe_status():
                    await self.signal_state(status, publisher)
            except ValueError:
                logger.warning(f"Skipping status of device %s because of validation error", self.host)
                await self._shutdown()
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
        self.state = philips.Hu1508(status)
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
        logger.debug("Got update for %s to %s", property_name, self.host)
        setattr(self.state, property_name, new_value)
        commands = self.state.get_commands()
        await self.ensure_connected_client()
        try:
            logger.debug("Sending command %s to %s", commands, self.host)
            for command in commands:
                await self.client.set_control_values(data=command)
        except ValueError as e:
            logger.warning(f"Skipping sending command [%s] to device %s: %s", commands, self.host, e)


T = TypeVar('T')


class MultipleDeviceObserver:
    def __init__(self, hosts: list[str]):
        self.clients = [DeviceObserver(host) for host in hosts]
        self.clients_ = {host: DeviceObserver(host) for host in hosts}

    async def send_update(self, device: str, property_name: str, new_value: str):
        await self.clients_[device].send_update(property_name, new_value)

    async def observe(self, publisher: 'MQTTPublisher') -> None:
        logger.info("Started to observe status")
        await MultipleDeviceObserver._execute_many(lambda client: client.observe(publisher), self.clients)

    async def shutdown(self):
        await MultipleDeviceObserver._execute_many(lambda client: client.stop(), self.clients)

    @staticmethod
    async def _execute_many(f: Callable[[T], Coroutine], cont: list[T], timeout: int = 0):
        async with asyncio.TaskGroup() as task_group:
            if timeout:
                coap_tasks = [
                    task_group.create_task(asyncio.wait_for(f(c), timeout=timeout))
                    for c in cont
                ]
            else:
                coap_tasks = [task_group.create_task(f(c)) for c in cont]

        return [task.result() for task in coap_tasks]

    @staticmethod
    @contextmanager
    def create(hosts) -> typing.Generator[MultipleDeviceObserver]:
        client = MultipleDeviceObserver(hosts)
        yield client
        client.shutdown()
