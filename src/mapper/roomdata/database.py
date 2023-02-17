# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import json
import logging
import os.path
from collections.abc import Callable, Mapping
from typing import Any, Union

# Third-party Modules:
import jsonschema
import rapidjson

# Local Modules:
from ..utils import getDataPath


LABELS_SCHEMA_VERSION: int = 0  # Increment this when the labels schema changes.
MAP_SCHEMA_VERSION: int = 1  # Increment this when the map schema changes.
DATA_DIRECTORY: str = getDataPath()
LABELS_FILE: str = "room_labels.json"
LABELS_FILE_PATH: str = os.path.join(DATA_DIRECTORY, LABELS_FILE)
SAMPLE_LABELS_FILE: str = LABELS_FILE + ".sample"
SAMPLE_LABELS_FILE_PATH: str = os.path.join(DATA_DIRECTORY, SAMPLE_LABELS_FILE)
MAP_FILE: str = "map.json"
MAP_FILE_PATH: str = os.path.join(DATA_DIRECTORY, MAP_FILE)
SAMPLE_MAP_FILE: str = MAP_FILE + ".sample"
SAMPLE_MAP_FILE_PATH: str = os.path.join(DATA_DIRECTORY, SAMPLE_MAP_FILE)


logger: logging.Logger = logging.getLogger(__name__)


class SchemaValidationError(ValueError):
	"""Raised if there was an error validating an object's schema."""


def getSchemaPath(databasePath: str, schemaVersion: int) -> str:
	"""
	Determines the schema file path from a schema version.

	Args:
		databasePath: The path of the database file.
		schemaVersion: The schema version.

	Returns:
		The schema file path.
	"""
	if databasePath.endswith(".sample"):
		databasePath = databasePath[: -len(".sample")]
	return "{}_v{ver}{}.schema".format(*os.path.splitext(databasePath), ver=schemaVersion)


def _validate(database: Mapping[str, Any], schemaPath: str) -> None:
	"""
	Validates a database against a schema.

	Note:
		The `jsonschema` library validates python data structures directly and
		produces nice error messages, but validation is slow.
		The `rapidjson` library validates much faster, however it produces poor error messages.
		For this reason rapidjson is used for the initial
		validation, and jsonschema is used if there is a failure.

	Args:
		database: The database to be validated.
		schemaPath: The location of the schema.
	"""
	with open(schemaPath, "r", encoding="utf-8") as fileObj:
		schema: dict[str, Any] = json.load(fileObj)
	validate: Callable[[str], None] = rapidjson.Validator(rapidjson.dumps(schema))
	try:
		validate(rapidjson.dumps(database))
	except rapidjson.ValidationError as rapidjsonExc:
		try:
			jsonschema.validate(database, schema)
		except jsonschema.ValidationError as jsonschemaExc:
			raise SchemaValidationError(str(jsonschemaExc)) from jsonschemaExc
		else:
			logger.warning(
				f"Error: jsonschema did not raise an exception, whereas rapidjson raised {rapidjsonExc}."
			)
			raise SchemaValidationError(str(rapidjsonExc)) from rapidjsonExc


def _load(databasePath: str) -> Union[tuple[str, None, int], tuple[None, dict[str, Any], int]]:
	"""
	Loads a database into memory.

	Args:
		databasePath: The location of the database.

	Returns:
		An error message or None, the loaded database or None, and the schema version.
	"""
	if not os.path.exists(databasePath):
		return f"Error: '{databasePath}' doesn't exist.", None, 0
	elif os.path.isdir(databasePath):
		return f"Error: '{databasePath}' is a directory, not a file.", None, 0
	try:
		with open(databasePath, "r", encoding="utf-8") as fileObj:
			database: dict[str, Any] = json.load(fileObj)
		schemaVersion: int = database.pop("schema_version", 0)
		schemaPath = getSchemaPath(databasePath, schemaVersion)
		_validate(database, schemaPath)
		return None, database, schemaVersion
	except IOError as e:
		return f"{e.strerror}: '{e.filename}'", None, 0
	except ValueError:
		return f"Corrupted database file: {databasePath}", None, 0


def _dump(database: Mapping[str, Any], databasePath: str, schemaPath: str) -> None:
	"""
	Saves a database to disk.

	Args:
		database: The database to be saved.
		databasePath: The location where the database should be saved.
		schemaPath: The location of the schema.
	"""
	with open(databasePath, "w", encoding="utf-8") as fileObj:
		_validate(database, schemaPath)
		rapidjson.dump(database, fileObj, sort_keys=True, indent=2, chunk_size=2 ** 16)


def loadLabels() -> Union[tuple[str, None, int], tuple[None, dict[str, str], int]]:
	"""
	Loads the labels database into memory.

	The default label definitions are first loaded, then the user's label definitions are merged in.

	Returns:
		An error message or None, the labels database or None, and the schema version.
	"""
	errorMessages: list[str] = []
	labels: dict[str, str] = {}
	for path in (SAMPLE_LABELS_FILE_PATH, LABELS_FILE_PATH):
		errors, result, schemaVersion = _load(path)
		if result is None:
			dataType: str = "sample" if path.endswith("sample") else "user"
			errorMessages.append(f"While loading {dataType} labels: {errors}")
		else:
			labels.update(result)
	if labels:
		return None, labels, schemaVersion
	else:
		return "\n".join(errorMessages), None, 0


def dumpLabels(labels: Mapping[str, str]) -> None:
	"""
	Saves the labels database to disk.

	Args:
		labels: The labels database to be saved.
	"""
	output: dict[str, Any] = dict(labels)  # Shallow copy.
	output["schema_version"] = LABELS_SCHEMA_VERSION
	_dump(output, LABELS_FILE_PATH, getSchemaPath(LABELS_FILE_PATH, LABELS_SCHEMA_VERSION))


def loadRooms() -> Union[tuple[str, None, int], tuple[None, dict[str, dict[str, Any]], int]]:
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
			dataType: str = "sample" if path.endswith("sample") else "user"
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
