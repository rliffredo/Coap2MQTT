import asyncio
import datetime
import json
import logging
import re
import typing
from contextlib import asynccontextmanager

import aiomqtt
from aiomqtt import MqttCodeError

from devices import CoapDevice
from configuration import MqttConfig

if typing.TYPE_CHECKING:
	from coap_bridge import MultipleDeviceBridge


logger = logging.getLogger(__name__)

class Connection:
	def __init__(self, config: MqttConfig):
		self.reconnecting = False
		self.connected = False
		self.client = aiomqtt.Client(config.host, config.port)
		self.server = config.host
		self.port = config.port
		self.root = config.root
		self.last_states: dict[str, dict[str, str | int | float | bool | None]] = {}
		self.connection_lock = asyncio.Lock()

	async def _connect(self):
		async with self.connection_lock:
			if self.connected:
				return
			logger.info("Connecting to %s...", self.server)
			await self.client.__aenter__()
			self.connected = True

	async def _disconnect(self):
		async with self.connection_lock:
			if not self.connected:
				return
			logger.info("Disconnecting from %s...", self.server)
			try:
				await self.client.__aexit__(None, None, None)
			except MqttCodeError as e:
				logger.warning("Could not disconnect, marking it as disconnected anyways. Error: %s", e)
			self.connected = False
	
	async def _publish(self, host: str, key: str, payload: int | float | str | bool | None):
		await self._connect()
		try:
			await self.client.publish(f"{self.root}/{host}/{key}", payload=payload, retain=False)
		except (MqttCodeError, TypeError) as e:
			logger.error("Could not publish payload [%s]: [%s]", payload, e)
			await self._disconnect()

	async def observe(self, publisher: 'MultipleDeviceBridge') -> None:
		while True:
			await self._connect()
			try:
				await self.client.subscribe(f"{self.root}/+/set/#")
				async for message in self.client.messages:
					if not message.payload:
						continue
					try:
						matches = re.fullmatch(f"{self.root}/(.+)/set/(.+)", message.topic.value)
						assert matches
						target_device = matches[1]
						target_property = matches[2]
						assert isinstance(message.payload, bytes)
						value = message.payload.decode()
					except (IndexError, ValueError) as e:
						logger.error("Could not parse MQTT message topic: [%s]: [%s]", message.topic, e)
						continue
					await publisher.send_update(target_device, target_property, value)
			except (MqttCodeError, TypeError) as e:
				logger.error("Error while observing topics: [%s]", e, exc_info=e)
				await self._disconnect()

	async def publish_state(self, host, state: CoapDevice) -> None:
		raw_json = json.dumps(state.raw)
		logger.debug("Publishing state for %s: %s", host, raw_json)
		await self._publish(host, "last_update", datetime.datetime.now().isoformat())
		await self._publish(host, "raw_state", raw_json)
		last_state = self.last_states.get(host, {})
		pretty_state = state.as_dict()
		for key, value in pretty_state.items():
			if value == last_state.get(key, None):
				continue
			logger.debug("Publishing attribute %s/%s: %s", host, key, value)
			await self._publish(host, key, value)
		self.last_states[host] = pretty_state

	async def publish_online(self, host) -> None:
		await self._publish(host, "status", "ONLINE")

	async def publish_offline(self, host) -> None:
		await self._publish(host, "status", "OFFLINE")

	@staticmethod
	@asynccontextmanager
	async def create(config: MqttConfig):
		publisher = Connection(config)
		yield publisher
		await publisher._disconnect()
