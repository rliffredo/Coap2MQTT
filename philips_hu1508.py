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

# Unused fields
# MODEL_ID = "D01S05"
# SOFTWARE_VERSION = "D01S12"
# PRODUCT_ID = "ProductId"
# DEVICE_ID = "DeviceId"
# RUNTIME = "Runtime"
# WIFI_VERSION = "WifiVersion"
# MODE_A = "D0310A"
# MODE_D = "D0310D"
# UNKNOWN_06 = "D03110"  # Timer-related?
# UNKNOWN_07 = "D03211" # Timer-related?

AMBIENT_LIGHT_MODE_MAP = {
	1: "warm",
	2: "dawn",
	3: "calm",
	4: "breath",
}
REVERSE_AMBIENT_LIGHT_MODE_MAP = {v: k for k, v in AMBIENT_LIGHT_MODE_MAP.items()}

LAMP_MODE_MAP = {
	0: "Off",
	1: "Humidity",
	2: "Ambient light mode",
}
REVERSE_LAMP_MODE_MAP = {v: k for k, v in LAMP_MODE_MAP.items()}

WORK_MODE_MAP = {
	0: "Auto",
	17: "Sleep",
	19: "Medium",
	65: "High",
}
REVERSE_WORK_MODE_MAP = {v: k for k, v in WORK_MODE_MAP.items()}

ERROR_CODES_MAP = {
	0: None,
	-16128: "Fill tank",
	-16352: "Clean filter",
}
REVERSE_ERROR_CODES_MAP = {v: k for k, v in ERROR_CODES_MAP.items()}

ON_OFF_MAP = {
	0: "ON",
	1: "OFF",
}
REVERSE_ON_OFF_MAP = {v: k for k, v in ON_OFF_MAP.items()}

BRIGHTNESS_MAP = {
	123: "Bright",
	115: "Low",
	0: "Off",
}
REVERSE_BRIGHTNESS_MAP = {k: v for k, v in BRIGHTNESS_MAP.items()}


def parse_state(state) -> dict[str, str | int | float | bool | None]:
	parsed_state = {
		"DeviceName": state[DEVICE_NAME],
		"PowerStatus": ON_OFF_MAP[state[POWER_STATUS]],
		"Mode": WORK_MODE_MAP[state[WORK_MODE]],
		"HumidityTarget": state[HUMIDITY_TARGET],
		"LampMode": LAMP_MODE_MAP[state[LAMP_MODE]],
		"AmbientLight": AMBIENT_LIGHT_MODE_MAP[state[AMBIENT_LIGHT_MODE]] if state[LAMP_MODE] == 2 else None,
		"Brightness": BRIGHTNESS_MAP[state[BRIGHTNESS]],
		"PreferencesBeep": ON_OFF_MAP[state[BEEP_STATUS]],
		"PreferencesSensorsInStandby": ON_OFF_MAP[state[STANDBY_SENSORS]],
		"Temperature": state[TEMPERATURE] // 10,
		"Humidity": state[HUMIDITY],
		"PercentBeforeUnitCleaning": round(state[FILTER_REMAINING_TIME] / state[FILTER_TOTAL_TIME] * 100, 2),
		"ErrorCode": ERROR_CODES_MAP.get(state[ERROR_CODE], state[ERROR_CODE]),
	}
	return parsed_state
