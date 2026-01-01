#!/usr/bin/env python3

# Logging should be loaded and initialized before any other import!
from log import setup_logging
setup_logging()

import asyncio

from configuration import get_config
from observer import MultipleDeviceObserver
from publisher import MQTTPublisher


async def main():
	if not (config := get_config()):
		return

	async with MQTTPublisher.create(config.mqtt_host, config.mqtt_root, config.mqtt_port) as publisher:
		with MultipleDeviceObserver.create(config.devices, publisher) as devices:
			await devices.observe_all()


if __name__ == "__main__":
	asyncio.run(main())