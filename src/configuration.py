"""
Load configuration from file

Actual file name is taken from environment and can be overridden

Example content:

```yaml
version: 1

coap:
	devices:
	  - ["192.168.1.101", "philips_hu15xx"]
	  - ["192.168.1.102", "philips_hu15xx"]
	  - ["192.168.1.103", "philips_hu15xx"]
	connection_timeout: 120
	status_timeout: 120

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
class CoapConfig:
	devices: list[tuple[str, str]]
	status_timeout: int = 120
	connection_timeout: int = 120

@dataclass
class MqttConfig:
	host: str
	root: str
	port: int = 1883

@dataclass
class Config:
	mqtt: MqttConfig
	coap: CoapConfig


def get_config() -> Config | None:
	try:
		config_file = os.getenv('CONFIG_FILE', 'config.loc.yaml')
		with open(config_file) as f_config:
			config_dict = yaml.load(f_config, Loader=yaml.FullLoader)
		mqtt_config = MqttConfig(**config_dict['mqtt'])
		coap_config = CoapConfig(**config_dict['coap'])
		configuration = Config(coap=coap_config, mqtt=mqtt_config)
		logger.info(f"Loaded configuration: {configuration}")
		return configuration
	except (FileNotFoundError, ValueError) as ex:
		logger.fatal(f"Could not load configuration: {ex}", exc_info=ex)
		return None
