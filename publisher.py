import asyncio
import datetime
import json
import logging
from contextlib import asynccontextmanager

import aiomqtt
from aiomqtt import MqttCodeError

from configuration import MqttConfig
from philips import Hu1508

logger = logging.getLogger(__name__)

class MQTTPublisher:
	def __init__(self, config: MqttConfig):
		self.reconnecting = False
		self.connected = False
		self.client = aiomqtt.Client(config.host, config.port)
		self.server = config.host
		self.port = config.port
		self.root = config.root
		self.last_states = {}
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
	
	async def _publish(self, host: str, key: str, payload: int | float | str):
		await self._connect()
		try:
			await self.client.publish(f"{self.root}/{host}/{key}", payload=payload)
		except (MqttCodeError, TypeError) as e:
			logger.error("Could not publish payload [%s]: [%s]", payload, e)
			await self._disconnect()

	async def publish_state(self, host, state) -> None:
		raw_state = json.dumps(state)
		logger.debug("Publishing state for %s: %s", host, raw_state)
		await self._publish(host, "last_update", datetime.datetime.now().isoformat())
		await self._publish(host, "raw_state", raw_state)
		pretty_state = Hu1508(state).as_dict()
		last_state = self.last_states.get(host, {})
		for key, value in pretty_state.items():
			if value == last_state.get(key, None):
				continue
			await self._publish(host, key, value)
		self.last_states[host] = pretty_state

	async def publish_online(self, host) -> None:
		await self._publish(host, "status", "ONLINE")

	async def publish_offline(self, host) -> None:
		await self._publish(host, "status", "OFFLINE")

	@staticmethod
	@asynccontextmanager
	async def create(config: MqttConfig):
		publisher = MQTTPublisher(config)
		yield publisher
		await publisher._disconnect()
