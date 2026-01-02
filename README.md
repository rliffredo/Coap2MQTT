# Coap2MQTT Bridge

A bridge to connect CoAP-based devices (tested only on Philips Air Purifiers, but it should be possible to extend
fairly easily) to an MQTT broker.

Developed on Python 3.14, but there should not be any hard requirements against any other recent Python version.

## Local Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd Coap2MQTT
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure the application:**
   Create a `config.loc.yaml` file in the root directory (see [Configuration](#configuration) below).

4. **Run the application:**
   ```bash
   uv run src/run.py
   ```

## Docker Deployment

The simplest way to run the bridge is using Docker Compose.

1. **Configure the application:**
   Create a `config.loc.yaml` file in the root directory (see [Configuration](#configuration) below).

2. **Build and start:**
   ```bash
   docker compose up -d
   ```

3. **Check logs:**
   ```bash
   docker compose logs -f
   ```

## Configuration

### Main Configuration (`config.yaml`)
The configuration is required, and there is no default.
The actual configuration file can be specified with the environment variable `CONFIG_FILE`; by default, it is
`config.prod.yaml`.

It defines the definition of devices to connect, as well as the MQTT broker configuration.

Example file:
```yaml
devices:
  - ["192.168.1.101", "philips_hu15xx"]
  - ["192.168.1.102", "philips_hu15xx"]

mqtt:
  host: "your-mqtt-broker-ip"
  port: 1883
  root: "coap_devices"
```

Note that at the moment, only Philips HU15xx devices are supported/implemented.

### Log configuration
There is already a default log configuration, but it can be overridden by using the environment variable
`LOG_CONFIG_FILE`.

## Development

### Adding new devices

New devices can be added by creating a new class in the `devices` directory, extending the `Device` class.

Each attribute is implemented through properties, using the `@property`  and the `@<attribute_name>.setter` decorators.
Setters must also use the `@ensure_setter_type` decorator, which ensures casting in the correct type. Also, the setter
must define the type annotation for the value.

Typically, the getter will return the correct field from the status dictionary, as stored in the `_status` attribute.
Field types can be Enum, Literal, or any basic type.

Setters will also need to register the updated field, using the `_add_command` method.

Example:
```python
class MyDevice(Device):
   
   class OnOff(Enum):
      OFF = 0
      ON = 1

   @property
   def power_status(self) -> MyDevice.OnOff:
      return MyDevice.OnOff(self._state.get("POWER_FIELD_CODE", 0))

   @power_status.setter
   @ensure_setter_type
   def power_status(self, value: 'MyDevice.OnOff'):
      if self.power_status == value:
         return
      self._state[POWER_FIELD_CODE] = value.value
      self._add_command(POWER_FIELD_CODE)
```

# Acknowledgments

This work is based on the existing work from existing projects:
- [philips-airpurifier-coapMqtt](https://github.com/balu-/philips-airpurifier-coapMqtt), from which I learnt how to use CoAP to connect to Philips devices.
- [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap), an integration for Philips devices for HA, and that gave a lot of information about the fields used by the humidifier.
