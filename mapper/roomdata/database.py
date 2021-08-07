# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import json
import logging
import os.path
from typing import Any, Callable, Dict, List, Mapping, Tuple, Union

# Third-party Modules:
import jsonschema
import rapidjson  # type: ignore[import]

# Local Modules:
from ..utils import getDirectoryPath


DATA_DIRECTORY: str = getDirectoryPath("data")
LABELS_FILE: str = "room_labels.json"
SAMPLE_LABELS_FILE: str = "room_labels.json.sample"
LABELS_SCHEMA_FILE: str = "room_labels.json.schema"
LABELS_SCHEMA_FILE_PATH: str = os.path.join(DATA_DIRECTORY, LABELS_SCHEMA_FILE)
LABELS_FILE_PATH: str = os.path.join(DATA_DIRECTORY, LABELS_FILE)
SAMPLE_LABELS_FILE_PATH: str = os.path.join(DATA_DIRECTORY, SAMPLE_LABELS_FILE)
MAP_FILE: str = "arda.json"
SAMPLE_MAP_FILE: str = "arda.json.sample"
MAP_DIRECTORY: str = getDirectoryPath("maps")
MAP_FILE_PATH: str = os.path.join(MAP_DIRECTORY, MAP_FILE)
SAMPLE_MAP_FILE_PATH: str = os.path.join(MAP_DIRECTORY, SAMPLE_MAP_FILE)
MAP_SCHEMA_FILE: str = "map.json.schema"
MAP_SCHEMA_FILE_PATH: str = os.path.join(DATA_DIRECTORY, MAP_SCHEMA_FILE)


logger: logging.Logger = logging.getLogger(__name__)


class SchemaValidationError(ValueError):
	"""Raised if there was an error validating an object's schema."""


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
		schema: Dict[str, Any] = json.load(fileObj)
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


def _load(databasePath: str, schemaPath: str) -> Union[Tuple[str, None], Tuple[None, Dict[str, Any]]]:
	"""
	Loads a database into memory.

	Args:
		databasePath: The location of the database.
		schemaPath: The location of the schema.

	Returns:
		An error message or None, and the loaded database or None.
	"""
	if not os.path.exists(databasePath):
		return f"Error: '{databasePath}' doesn't exist.", None
	elif os.path.isdir(databasePath):
		return f"Error: '{databasePath}' is a directory, not a file.", None
	try:
		with open(databasePath, "r", encoding="utf-8") as fileObj:
			database: Dict[str, Any] = json.load(fileObj)
		_validate(database, schemaPath)
		return None, database
	except IOError as e:
		return f"{e.strerror}: '{e.filename}'", None
	except ValueError:
		return f"Corrupted database file: {databasePath}", None


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


def loadLabels() -> Union[Tuple[str, None], Tuple[None, Dict[str, str]]]:
	"""
	Loads the labels database into memory.

	The default label definitions are first loaded, then the user's label definitions are merged in.

	Returns:
		An error message and None, or None and the loaded labels database.
	"""
	errorMessages: List[str] = []
	labels: Dict[str, str] = {}
	for path in (SAMPLE_LABELS_FILE_PATH, LABELS_FILE_PATH):
		errors, result = _load(path, LABELS_SCHEMA_FILE_PATH)
		if result is None:
			dataType: str = "sample" if path.endswith("sample") else "user"
			errorMessages.append(f"While loading {dataType} labels: {errors}")
		else:
			labels.update(result)
	if labels:
		return None, labels
	else:
		return "\n".join(errorMessages), None


def dumpLabels(labels: Mapping[str, str]) -> None:
	"""
	Saves the labels database to disk.

	Args:
		labels: The labels database to be saved.
	"""
	_dump(labels, LABELS_FILE_PATH, LABELS_SCHEMA_FILE_PATH)


def loadRooms() -> Union[Tuple[str, None], Tuple[None, Dict[str, Dict[str, Any]]]]:
	"""
	Loads the rooms database into memory.

	An attempt to load the user's database is made first, otherwise the sample database is loaded.

	Returns:
		An error message and None, or None and the loaded rooms database.
	"""
	errorMessages: List[str] = []
	for path in (MAP_FILE_PATH, SAMPLE_MAP_FILE_PATH):
		errors, result = _load(path, MAP_SCHEMA_FILE_PATH)
		if result is None:
			dataType: str = "sample" if path.endswith("sample") else "user"
			errorMessages.append(f"While loading {dataType} map: {errors}")
		else:
			return None, result
	return "\n".join(errorMessages), None


def dumpRooms(rooms: Mapping[str, Mapping[str, Any]]) -> None:
	"""
	Saves the rooms database to disk.

	Args:
		rooms: The rooms database to be saved.
	"""
	_dump(rooms, MAP_FILE_PATH, MAP_SCHEMA_FILE_PATH)
