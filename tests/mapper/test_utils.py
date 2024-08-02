# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import os.path
from unittest import TestCase

# Mapper Modules:
from mapper import utils


class TestUtils(TestCase):
	def test_getDataPath(self) -> None:
		subdirectory: tuple[str, ...] = ("level1", "level2")
		output: str = os.path.join(
			os.path.dirname(utils.__file__), os.path.pardir, utils.DATA_DIRECTORY, *subdirectory
		)
		self.assertEqual(utils.getDataPath(*subdirectory), os.path.realpath(output))
