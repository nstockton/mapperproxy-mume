# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase, mock

# Mapper Modules:
from mapper.config import Config, ConfigError


class TestConfig(TestCase):
	@mock.patch("mapper.config.os")
	def test_load(self, mockOs):
		mockOs.path.exists.return_value = False
		cfg = Config("testconfig")
		self.assertEqual(cfg.name, "testconfig")
		self.assertEqual(cfg._config, {})
		mockOs.path.exists.return_value = True
		mockOs.path.isdir.return_value = True
		with self.assertRaises(ConfigError):
			cfg.reload()
		mockOs.path.isdir.return_value = False
		with mock.patch("mapper.config.codecs.open", mock.mock_open(read_data="invalid")):
			with self.assertRaises(ConfigError):
				cfg.reload()
		with mock.patch("mapper.config.codecs.open", mock.mock_open(read_data="{}")):
			cfg.reload()
		cfg["test"] = "somevalue"
		self.assertEqual(cfg["test"], "somevalue")
		self.assertEqual(len(cfg), 1)
		del cfg["test"]
		self.assertEqual(cfg, {})

	def test_save(self):
		cfg = Config("testconfig")
		cfg["test"] = "somevalue"
		mockOpen = mock.mock_open()
		with mock.patch("mapper.config.codecs.open", mockOpen):
			cfg.save()
		mockOpen.return_value.write.assert_called_once_with('{\r\n  "test": "somevalue"\r\n}')
