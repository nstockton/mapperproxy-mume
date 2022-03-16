# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import json
import os.path
import threading
from collections.abc import Iterator
from typing import Any, MutableMapping

# Local Modules:
from .utils import getDataPath


DATA_DIRECTORY: str = getDataPath()


class ConfigError(Exception):
	"""Implements the base class for Config exceptions."""


class Config(MutableMapping[str, Any]):
	"""
	Implements loading and saving of program configuration.
	"""

	_configLock: threading.RLock = threading.RLock()

	def __init__(self, name: str = "config") -> None:
		"""
		Defines the constructor for the object.

		Args:
			name: The name of the configuration.
		"""
		super().__init__()
		self._name: str = name
		self._config: dict[str, Any] = dict()
		self.reload()

	@property
	def name(self) -> str:
		"""The name of the configuration."""
		return self._name

	def _parse(self, filename: str) -> dict[str, Any]:
		filename = os.path.join(DATA_DIRECTORY, filename)
		if not os.path.exists(filename):
			return {}
		elif os.path.isdir(filename):
			raise ConfigError(f"'{filename}' is a directory, not a file.")
		with self._configLock:
			try:
				with open(filename, "r", encoding="utf-8") as fileObj:
					return dict(json.load(fileObj))
			except IOError as e:  # pragma: no cover
				raise ConfigError(f"{e.strerror}: '{e.filename}'")
			except ValueError:
				raise ConfigError(f"Corrupted json file: {filename}")

	def reload(self) -> None:
		"""Reloads the configuration from disc."""
		self._config.clear()
		self._config.update(self._parse(f"{self.name}.json.sample"))
		self._config.update(self._parse(f"{self.name}.json"))

	def save(self) -> None:
		"""Saves the configuration to disc."""
		filename: str = os.path.join(DATA_DIRECTORY, f"{self.name}.json")
		with self._configLock:
			with open(filename, "w", encoding="utf-8", newline="\r\n") as fileObj:
				# Configuration should be stored using Windows style line endings (\r\n)
				# so the file can be viewed in Notepad.
				json.dump(self._config, fileObj, sort_keys=True, indent=2)

	def __getitem__(self, key: str) -> Any:
		return self._config[key]

	def __setitem__(self, key: str, value: Any) -> None:
		self._config[key] = value

	def __delitem__(self, key: str) -> None:
		del self._config[key]

	def __iter__(self) -> Iterator[str]:
		return iter(self._config)

	def __len__(self) -> int:
		return len(self._config)
