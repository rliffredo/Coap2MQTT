#!/usr/bin/env python3

# Logging should be loaded and initialized before any other import!
from log import setup_logging
setup_logging()

import asyncio
from logging import getLogger

from configuration import get_config
from coap_bridge import MultipleDeviceBridge
import mqtt

logger = getLogger(__name__)


async def main():
	if not (config := get_config()):
		return

	try:
		async with mqtt.Connection.create(config.mqtt) as mqtt_connection:
			async with MultipleDeviceBridge.create(config.devices) as devices_bridge:
				asyncio.create_task(mqtt_connection.observe(publisher=devices_bridge))
				await devices_bridge.observe(publisher=mqtt_connection)
	except asyncio.CancelledError:
		# This is expected during shutdown
		logger.info("Main loop cancelled, shutting down...")


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		# Gracefully exit on Ctrl+C without showing a traceback
		logger.info("Service stopped by user.")
