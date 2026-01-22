# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
from pathlib import Path

# Third-party Modules:
from knickknacks.platforms import get_directory_path, is_frozen


DATA_DIRECTORY_PATH: Path = Path("mapper_data")


def getDataPath(*args: Path | str) -> Path:
	"""
	Retrieves the path of the data directory.

	Args:
		*args: Positional arguments to be passed to Path.joinpath after the data path.

	Returns:
		The path.
	"""
	path: Path = Path(get_directory_path())
	if not is_frozen():
		path = path.parent
	return path.joinpath(DATA_DIRECTORY_PATH, *args).resolve()
