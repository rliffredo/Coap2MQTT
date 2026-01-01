import logging
from enum import Enum

from coap_device import Device

logger = logging.getLogger(__name__)

DEVICE_NAME = "D01S03"
POWER_STATUS = "D03102"
WORK_MODE = "D0310C"
HUMIDITY_TARGET = "D03128"  # Humidity target related?
LAMP_MODE = "D03135"
AMBIENT_LIGHT_MODE = "D03137"
BRIGHTNESS = "D03105"
BEEP_STATUS = "D03130"
STANDBY_SENSORS = "D03134"
TEMPERATURE = "D03224"
HUMIDITY = "D03125"
FILTER_TOTAL_TIME = "D05207"
FILTER_REMAINING_TIME = "D0520D"
ERROR_CODE = "D03240"

class Hu1508(Device):
	class OnOff(Enum):
		OFF = 0
		ON = 1

	class WorkMode(Enum):
			Auto = 0
			Sleep = 17
			Medium = 19
			High = 65

	# We encode lamp mode _and_ ambient light in
	# the same enum, with ambient light codes
	# shifted by 10
	class LampMode(Enum):
		Off = 0
		Humidity = 1
		AmbientLight = 2
		NoAmbientLight = 10
		Warm = 11
		Dawn = 12
		Calm = 13
		Breath = 14

	class Brightness(Enum):
		Bright = 123
		Low = 115
		Off = 0

	class ErrorStatus(Enum):
		NoError = 0
		FillTank = -16128
		CleanFilter = -16352

	@property
	def name(self):
		return self._state.get(DEVICE_NAME, "Unknown")

	@property
	def power_status(self) -> Hu1508.OnOff:
		return Hu1508.OnOff(self._state.get(POWER_STATUS, 0))

	@power_status.setter
	def power_status(self, value: Hu1508.OnOff):
		self._state[POWER_STATUS] = value.value
		self._add_command(POWER_STATUS)

	@property
	def mode(self) -> Hu1508.WorkMode:
		return Hu1508.WorkMode(self._state.get(WORK_MODE, 0))

	@mode.setter
	def mode(self, value: Hu1508.WorkMode):
		self._state[WORK_MODE] = value.value
		# self._add_command(WORK_MODE)

	@property
	def humidity_target(self) -> int:
		return self._state.get(HUMIDITY_TARGET, 0)

	@humidity_target.setter
	def humidity_target(self, value: int):
		self._state[HUMIDITY_TARGET] = value
		# self._add_command(HUMIDITY_TARGET)

	@property
	def lamp_mode(self) -> LampMode:
		lamp_mode_ = self._state.get(LAMP_MODE, 0)
		if lamp_mode_ == 2:
			return Hu1508.LampMode(self._state.get(AMBIENT_LIGHT_MODE, 0) + 10)
		else:
			return Hu1508.LampMode(lamp_mode_)

	@lamp_mode.setter
	def lamp_mode(self, value: LampMode):
		if value.value > 10:
			self._state[LAMP_MODE] = 2
			self._state[AMBIENT_LIGHT_MODE] = value.value - 10
		else:
			self._state[LAMP_MODE] = value.value
			self._state[AMBIENT_LIGHT_MODE] = 0
		self._add_command([LAMP_MODE, AMBIENT_LIGHT_MODE])

	@property
	def brightness(self) -> Hu1508.Brightness:
		return Hu1508.Brightness(self._state.get(BRIGHTNESS, 0))

	@brightness.setter
	def brightness(self, value: Hu1508.Brightness):
		self._state[BRIGHTNESS] = value.value
		# self._add_command(BRIGHTNESS)

	@property
	def preferences_beep(self) -> Hu1508.OnOff:
		return Hu1508.OnOff(self._state.get(BEEP_STATUS, 1))

	@preferences_beep.setter
	def preferences_beep(self, value: Hu1508.OnOff):
		self._state[BEEP_STATUS] = value.value
		self._add_command(BEEP_STATUS)

	@property
	def preferences_sensors_in_standby(self) -> Hu1508.OnOff:
		return Hu1508.OnOff(self._state.get(STANDBY_SENSORS, 1))

	@preferences_sensors_in_standby.setter
	def preferences_sensors_in_standby(self, value: Hu1508.OnOff):
		self._state[STANDBY_SENSORS] = value.value
		self._add_command(STANDBY_SENSORS)

	@property
	def temperature(self) -> int:
		return self._state.get(TEMPERATURE, 0) // 10

	@property
	def humidity(self) -> int:
		return self._state.get(HUMIDITY, 0)

	@property
	def percent_unit_before_cleaning(self) -> float:
		return round(self._state.get(FILTER_REMAINING_TIME, 200) / self._state.get(FILTER_TOTAL_TIME, 200) * 100, 2)

	@property
	def error(self) -> ErrorStatus | int | None:
		error_code = self._state.get(ERROR_CODE, 100)
		if error_code == 0:
			return None
		try:
			return Hu1508.ErrorStatus(error_code)
		except ValueError:
			logger.error("Found unmapped error code: %s", error_code)
			return error_code
