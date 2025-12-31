import datetime
import json
from contextlib import asynccontextmanager

import aiomqtt

from philips_hu1508 import parse_state


class MQTTPublisher:
	def __init__(self, client: aiomqtt.Client, root: str):
		self.client = client
		self.root = root
		self.last_states = {}

	async def publish_state(self, host, state) -> None:
		await self.client.publish(f"{self.root}/{host}/last_update", payload=datetime.datetime.now().isoformat())
		await self.client.publish(f"{self.root}/{host}/raw_state", payload=json.dumps(state))
		pretty_state = parse_state(state)
		last_state = self.last_states.get(host, {})
		for key, value in pretty_state.items():
			if value == last_state.get(key, None):
				continue
			await self.client.publish(f"{self.root}/{host}/{key}", payload=value)
		self.last_states[host] = pretty_state

	async def publish_online(self, host) -> None:
		await self.client.publish(f"{self.root}/{host}/status", payload="ONLINE")

	async def publish_offline(self, host) -> None:
		await self.client.publish(f"{self.root}/{host}/status", payload="OFFLINE")

	@staticmethod
	@asynccontextmanager
	async def create(server: str, root: str, port: int = 1883):
		async with aiomqtt.Client(server, port) as client:
			yield MQTTPublisher(client, root)
