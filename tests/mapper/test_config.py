# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

# Mapper Modules:
from mapper.config import Config, ConfigError


class TestConfig(TestCase):
	@patch("mapper.config.Path.is_dir")
	@patch("mapper.config.Path.exists")
	def test_load(self, mockExists: Mock, mockIsDir: Mock) -> None:
		mockExists.return_value = False
		cfg: Config = Config("testconfig")
		self.assertEqual(cfg.name, "testconfig")
		self.assertEqual(cfg._config, {})
		mockExists.return_value = True
		mockIsDir.return_value = True
		with self.assertRaises(ConfigError):
			cfg.reload()
		mockIsDir.return_value = False
		with ExitStack() as cm:
			cm.enter_context(patch("mapper.config.Path.open", mock_open(read_data="invalid")))
			cm.enter_context(self.assertRaises(ConfigError))
			cfg.reload()
		with patch("mapper.config.Path.open", mock_open(read_data="{}")):
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
		lines: list[str] = []
		mockOpen.return_value.write.side_effect = lines.append
		with patch("mapper.config.Path.open", mockOpen):
			cfg.save()
		mockOpen.assert_called_once_with("w", encoding="utf-8", newline="\n")
		self.assertEqual("".join(lines), '{\n  "test": "somevalue"\n}\n')
