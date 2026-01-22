# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
from pathlib import Path
from unittest import TestCase, mock

# Mapper Modules:
from mapper import utils


class TestUtils(TestCase):
	@mock.patch("mapper.utils.is_frozen")
	def test_get_data_path(self, mockIs_frozen: mock.Mock) -> None:
		subdirectory: tuple[str, ...] = ("level1", "level2")
		frozenOutput = (
			Path(utils.__file__).parent.joinpath(utils.DATA_DIRECTORY_PATH, *subdirectory).resolve()
		)
		notFrozenOutput = (
			Path(utils.__file__).parent.parent.joinpath(utils.DATA_DIRECTORY_PATH, *subdirectory).resolve()
		)
		mockIs_frozen.return_value = True
		self.assertEqual(utils.getDataPath(*subdirectory), frozenOutput)
		mockIs_frozen.return_value = False
		self.assertEqual(utils.getDataPath(*subdirectory), notFrozenOutput)
