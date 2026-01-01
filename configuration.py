"""
Load configuration from file

Actual file name is taken from environment and can be overridden

Example content:

```yaml
version: 1

devices:
  - "192.168.1.101"
  - "192.168.1.102"
  - "192.168.1.103"

mqtt:
	host: "mqttbroker"
	port: 1883
	root: "coap_devices"
```
"""

import logging
import os
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)

@dataclass
class MqttConfig:
	host: str
	root: str
	port: int = 1883

@dataclass
class Config:
	devices: list[str]
	mqtt: MqttConfig


def get_config() -> Config | None:
	try:
		config_file = os.getenv('CONFIG_FILE', 'config.loc.yaml')
		config_dict = yaml.load(open(config_file).read(), Loader=yaml.FullLoader)
		mqtt_config = MqttConfig(**config_dict['mqtt'])
		configuration = Config(devices=config_dict['devices'], mqtt=mqtt_config)
		logger.info(f"Loaded configuration: {configuration}")
		return configuration
	except (FileNotFoundError, ValueError) as ex:
		logger.fatal(f"Could not load configuration: {ex}", exc_info=ex)
		return None
