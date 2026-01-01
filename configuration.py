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
  
mqtt_host: "mqttbroker"
mqtt_port: 1883
mqtt_root: "coap_devices"
```
"""

import logging
import os
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Config:
	devices: list[str]
	mqtt_host: str
	mqtt_port: int
	mqtt_root: str


def get_config() -> Config | None:
	try:
		config_file = os.getenv('CONFIG_FILE', 'config.loc.yaml')
		config_dict = yaml.load(open(config_file).read(), Loader=yaml.FullLoader)
		checked_config = {k: v for k, v in config_dict.items() if k in Config.__annotations__}
		configuration = Config(**checked_config)
		logger.info(f"Loaded configuration: {configuration}")
		return configuration
	except (FileNotFoundError, ValueError) as ex:
		logger.fatal(f"Could not load configuration: {ex}", exc_info=ex)
		return None
