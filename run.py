#!/usr/bin/env python3
import asyncio
import sys

from observer import MultipleDeviceObserver
from publisher import MQTTPublisher


async def main():
	async with MQTTPublisher.create(sys.argv[1], "coap_devices") as publisher:
		with MultipleDeviceObserver.create(sys.argv[2], publisher) as devices:
			await devices.observe_all()


if __name__ == "__main__":
	asyncio.run(main())