import inspect
from enum import Enum, EnumType
from functools import wraps
from typing import get_origin, Literal

CoapStatus = dict[str, int | float | str]


def ensure_setter_type(f):
	target_type = f.__annotations__.get("value")
	assert target_type, f"Setter {f.__name__} has no type annotation, or no 'value' field"
	if get_origin(target_type) == Literal:
		target_type = type(target_type.__args__[0])
	if isinstance(target_type, str):
		local_type = target_type.split(".")[-1]
		stack = inspect.stack()
		caller_frame_types = stack[1].frame.f_locals
		target_type = caller_frame_types[local_type]
	@wraps(f)
	def wrapper(self, value):
		if target_type and not isinstance(value, target_type):
			if issubclass(target_type, Enum):
				intermediate_type = type(next(iter(target_type)).value)
				value = intermediate_type(value)
			value = target_type(value)
		return f(self, value)

	return wrapper


class CoapDevice:
	def __init__(self):
		self._state: CoapStatus = {}
		self._commands = []

	def update(self, state: CoapStatus):
		self._state = state

	def properties(self):
		return [k for k, v in self.__class__.__dict__.items() if isinstance(v, property)]

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

	@property
	def raw(self) -> CoapStatus:
		return self._state

