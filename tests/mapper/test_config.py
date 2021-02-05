# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import os.path
from typing import List
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

# Mapper Modules:
from mapper.config import DATA_DIRECTORY, Config, ConfigError


class TestConfig(TestCase):
	@patch("mapper.config.os")
	def test_load(self, mockOs: Mock) -> None:
		mockOs.path.exists.return_value = False
		cfg: Config = Config("testconfig")
		self.assertEqual(cfg.name, "testconfig")
		self.assertEqual(cfg._config, {})
		mockOs.path.exists.return_value = True
		mockOs.path.isdir.return_value = True
		with self.assertRaises(ConfigError):
			cfg.reload()
		mockOs.path.isdir.return_value = False
		with patch("mapper.config.open", mock_open(read_data="invalid")):
			with self.assertRaises(ConfigError):
				cfg.reload()
		with patch("mapper.config.open", mock_open(read_data="{}")):
			cfg.reload()
		cfg["test"] = "somevalue"
		self.assertEqual(cfg["test"], "somevalue")
		self.assertEqual(len(cfg), 1)
		del cfg["test"]
		self.assertEqual(cfg, {})

	def test_save(self) -> None:
		cfg: Config = Config("testconfig")
		cfg["test"] = "somevalue"
		mockOpen: Mock = mock_open()
		lines: List[str] = []
		mockOpen.return_value.write.side_effect = lambda line: lines.append(line)
		with patch("mapper.config.open", mockOpen):
			cfg.save()
		fileName: str = os.path.join(DATA_DIRECTORY, f"{cfg.name}.json")
		mockOpen.assert_called_once_with(fileName, "w", encoding="utf-8", newline="\r\n")
		self.assertEqual("".join(lines), '{\n  "test": "somevalue"\n}')
