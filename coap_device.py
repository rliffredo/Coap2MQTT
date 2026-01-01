from enum import Enum, EnumType
from typing import get_origin, Literal


class Device:
	def __init__(self, state):
		self._state = state
		self._commands = []

	@classmethod
	def properties(cls):
		return [k for k, v in cls.__dict__.items() if isinstance(v, property)]

	@classmethod
	def values_for(cls, p):
		pp = getattr(cls, p, None)
		if not pp or not pp.fset:
			return None
		rtype = pp.fset.__annotations__["value"]
		if get_origin(rtype) == Literal:
			return rtype.__args__
		if isinstance(rtype, EnumType):
			return [n.value for n in rtype]
		return [f"<{rtype}>"]

	def _add_command(self, fields):
		if not isinstance(fields, list):
			fields = [fields]
		self._commands.append({field: self._state[field] for field in fields})

	def get_commands(self):
		command_queue = self._commands
		self._commands = []
		return command_queue

	def as_dict(self) -> dict[str, str | int | float | bool | None]:
		def get_value(name):
			value = getattr(self, name)
			return value.name if isinstance(value, Enum) else value

		return {prop_name: get_value(prop_name) for prop_name in self.properties()}
