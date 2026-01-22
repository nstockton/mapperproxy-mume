# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Any

# Third-party Modules:
import fastjsonschema
import orjson

# Mapper Modules:
from mapper.utils import getDataPath


LABELS_SCHEMA_VERSION: int = 1  # Increment this when the labels schema changes.
MAP_SCHEMA_VERSION: int = 2  # Increment this when the map schema changes.
DATA_DIRECTORY_PATH: Path = getDataPath()
LABELS_FILE: str = "room_labels.json"
LABELS_FILE_PATH: Path = DATA_DIRECTORY_PATH / LABELS_FILE
SAMPLE_LABELS_FILE: str = LABELS_FILE + ".sample"
SAMPLE_LABELS_FILE_PATH: Path = DATA_DIRECTORY_PATH / SAMPLE_LABELS_FILE
MAP_FILE: str = "map.json"
MAP_FILE_PATH: Path = DATA_DIRECTORY_PATH / MAP_FILE
SAMPLE_MAP_FILE: str = MAP_FILE + ".sample"
SAMPLE_MAP_FILE_PATH: Path = DATA_DIRECTORY_PATH / SAMPLE_MAP_FILE


logger: logging.Logger = logging.getLogger(__name__)


def getSchemaPath(databasePath: Path | str, schemaVersion: int) -> Path:
	"""
	Determines the schema file path from a schema version.

	Args:
		databasePath: The path of the database file.
		schemaVersion: The schema version.

	Returns:
		The schema file path.
	"""
	path: Path = Path(databasePath)
	if path.suffix.lower() == ".sample":
		path = path.with_suffix("")  # Clear the suffix.
	return path.with_name(f"{path.stem}_v{schemaVersion}{path.suffix}.schema")


@cache
def getValidator(schemaPath: Path | str) -> Callable[..., None]:  # type: ignore[misc]
	path: Path = Path(schemaPath)
	validator: Callable[..., None] = fastjsonschema.compile(orjson.loads(path.read_bytes()))
	return validator


def _validate(database: Mapping[str, Any], schemaPath: Path | str) -> None:
	"""
	Validates a database against a schema.

	Args:
		database: The database to be validated.
		schemaPath: The location of the schema.
	"""
	validator = getValidator(Path(schemaPath))
	try:
		validator(database)
	except fastjsonschema.JsonSchemaException:
		logger.exception("Data failed validation.")


def _load(databasePath: Path | str) -> tuple[str, None, int] | tuple[None, dict[str, Any], int]:
	"""
	Loads a database into memory.

	Args:
		databasePath: The location of the database.

	Returns:
		An error message or None, the loaded database or None, and the schema version.
	"""
	path: Path = Path(databasePath)
	if not path.is_file():
		return f"Error: '{databasePath}' file not found.", None, 0
	try:
		database: dict[str, Any] = orjson.loads(path.read_bytes())
		schemaVersion: int = database.get("schema_version", 0)
		schemaPath = getSchemaPath(path, schemaVersion)
		_validate(database, schemaPath)
	except OSError as e:
		return f"OSError: {e}", None, 0
	except orjson.JSONDecodeError as e:
		return f"Error: '{databasePath}' is corrupted. {e}", None, 0
	else:
		database.pop("schema_version", None)
		return None, database, schemaVersion


def _dump(database: Mapping[str, Any], databasePath: Path | str, schemaPath: Path | str) -> None:
	"""
	Saves a database to disk.

	Args:
		database: The database to be saved.
		databasePath: The location where the database should be saved.
		schemaPath: The location of the schema.
	"""
	_validate(database, Path(schemaPath))
	options: int = (
		orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_STRICT_INTEGER
	)
	try:
		data: bytes = orjson.dumps(database, option=options)
	except orjson.JSONEncodeError:
		logger.exception(f"Error: Cannot encode to '{databasePath}'.")
		return
	try:
		Path(databasePath).write_bytes(data)
	except OSError:
		logger.exception("Error writing to disk:")


def loadLabels() -> tuple[str, None, int] | tuple[None, dict[str, str], int]:
	"""
	Loads the labels database into memory.

	The default label definitions are first loaded, then the user's label definitions are merged in.

	Returns:
		An error message or None, the labels database or None, and the schema version.
	"""
	errorMessages: list[str] = []
	labels: dict[str, str] = {}
	for path in (SAMPLE_LABELS_FILE_PATH, LABELS_FILE_PATH):
		if not path.is_file():
			continue
		errors, result, schemaVersion = _load(path)
		if result is None:
			dataType: str = "sample" if path.suffix.lower() == ".sample" else "user"
			errorMessages.append(f"While loading {dataType} labels: {errors}")
		else:
			labels.update(result if schemaVersion < 1 else result["labels"])
	if labels:
		return None, labels, schemaVersion
	return "\n".join(errorMessages), None, 0


def dumpLabels(labels: Mapping[str, str]) -> None:
	"""
	Saves the labels database to disk.

	Args:
		labels: The labels database to be saved.
	"""
	output: dict[str, Any] = {
		"schema_version": LABELS_SCHEMA_VERSION,
		"labels": dict(labels),  # Shallow copy.
	}
	_dump(output, LABELS_FILE_PATH, getSchemaPath(LABELS_FILE_PATH, LABELS_SCHEMA_VERSION))


def loadRooms() -> tuple[str, None, int] | tuple[None, dict[str, dict[str, Any]], int]:
	"""
	Loads the rooms database into memory.

	An attempt to load the user's database is made first, otherwise the sample database is loaded.

	Returns:
		An error message or None, the rooms database or None, and the schema version.
	"""
	errorMessages: list[str] = []
	for path in (MAP_FILE_PATH, SAMPLE_MAP_FILE_PATH):
		errors, result, schemaVersion = _load(path)
		if result is None:
			dataType: str = "sample" if path.suffix.lower() == ".sample" else "user"
			errorMessages.append(f"While loading {dataType} map: {errors}")
		else:
			return None, result, schemaVersion
	return "\n".join(errorMessages), None, 0


def dumpRooms(rooms: Mapping[str, Mapping[str, Any]]) -> None:
	"""
	Saves the rooms database to disk.

	Args:
		rooms: The rooms database to be saved.
	"""
	output: dict[str, Any] = dict(rooms)  # Shallow copy.
	output["schema_version"] = MAP_SCHEMA_VERSION
	_dump(output, MAP_FILE_PATH, getSchemaPath(MAP_FILE_PATH, MAP_SCHEMA_VERSION))
