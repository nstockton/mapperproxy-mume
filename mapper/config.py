# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import codecs
import collections.abc
import json
import os.path
import threading
from typing import Dict, MutableMapping

# Local Modules:
from .utils import getDirectoryPath


DATA_DIRECTORY = getDirectoryPath("data")
CONFIG_LOCK = threading.RLock()


class ConfigError(Exception):
	"""Implements the base class for Config exceptions."""


class Config(collections.abc.MutableMapping):
	"""
	Implements loading and saving of program configuration.
	"""

	def __init__(self, name: str = "config") -> None:
		"""
		Defines the constructor for the object.

		Args:
			name: The name of the configuration.
		"""
		super().__init__()
		self.name = name
		self._config: MutableMapping = dict()
		self.reload()

	@property
	def name(self) -> str:
		"""The name of the configuration."""
		return self._name

	@name.setter
	def name(self, value: str) -> None:
		self._name = value

	def _parse(self, filename: str) -> Dict:
		filename = os.path.join(DATA_DIRECTORY, filename)
		if not os.path.exists(filename):
			return {}
		elif os.path.isdir(filename):
			raise ConfigError(f"'{filename}' is a directory, not a file.")
		with CONFIG_LOCK:
			try:
				with codecs.open(filename, "rb", encoding="utf-8") as fileObj:
					return json.load(fileObj)
			except IOError as e:  # pragma: no cover
				raise ConfigError(f"{e.strerror}: '{e.filename}'")
			except ValueError:
				raise ConfigError(f"Corrupted json file: {filename}")

	def reload(self) -> None:
		"""Reloads the configuration from disc."""
		self._config.clear()
		self._config.update(self._parse(f"{self._name}.json.sample"))
		self._config.update(self._parse(f"{self._name}.json"))

	def save(self) -> None:
		"""Saves the configuration to disc."""
		filename = os.path.join(DATA_DIRECTORY, f"{self._name}.json")
		with CONFIG_LOCK:
			with codecs.open(filename, "wb", encoding="utf-8") as fileObj:
				# Configuration should be stored using Windows style line endings (\r\n)
				# so the file can be viewed in Notepad.
				# However, codecs.open forces opening files in binary mode, which
				# prevents the use of the newline flag to force a particular delimiter for new lines.
				# The json data must therefore be modified to replace Unix line endings
				# with Windows line endings before it is written.
				data = json.dumps(self._config, sort_keys=True, indent=2)
				fileObj.write(data.replace("\n", "\r\n"))

	def __getitem__(self, key):
		return self._config[key]

	def __setitem__(self, key, value):
		self._config[key] = value

	def __delitem__(self, key):
		del self._config[key]

	def __iter__(self):
		return iter(self._config)

	def __len__(self):
		return len(self._config)
