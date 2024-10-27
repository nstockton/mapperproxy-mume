# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import os.path

# Third-party Modules:
from knickknacks.platforms import getDirectoryPath, isFrozen


DATA_DIRECTORY: str = "mapper_data"


def getDataPath(*args: str) -> str:
	"""
	Retrieves the path of the data directory.

	Args:
		*args: Positional arguments to be passed to os.join after the data path.

	Returns:
		The path.
	"""
	path: str = getDirectoryPath(os.path.curdir if isFrozen() else os.path.pardir, DATA_DIRECTORY)
	return os.path.realpath(os.path.join(path, *args))
