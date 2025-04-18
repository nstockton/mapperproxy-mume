# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import os.path

# Third-party Modules:
from knickknacks.platforms import get_directory_path, is_frozen


DATA_DIRECTORY: str = "mapper_data"


def getDataPath(*args: str) -> str:
	"""
	Retrieves the path of the data directory.

	Args:
		*args: Positional arguments to be passed to os.join after the data path.

	Returns:
		The path.
	"""
	path: str = get_directory_path(os.path.curdir if is_frozen() else os.path.pardir, DATA_DIRECTORY)
	return os.path.realpath(os.path.join(path, *args))
