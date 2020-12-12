# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import codecs
import json
import os.path
from typing import Any, Dict, List, Mapping, Tuple, Union

# Local Modules:
from .objects import Room
from ..utils import getDirectoryPath


try:
	import rapidjson
except ImportError:
	rapidjson = None


DATA_DIRECTORY: str = getDirectoryPath("data")
LABELS_FILE: str = "room_labels.json"
SAMPLE_LABELS_FILE: str = "room_labels.json.sample"
LABELS_FILE_PATH: str = os.path.join(DATA_DIRECTORY, LABELS_FILE)
SAMPLE_LABELS_FILE_PATH: str = os.path.join(DATA_DIRECTORY, SAMPLE_LABELS_FILE)
MAP_FILE: str = "arda.json"
SAMPLE_MAP_FILE: str = "arda.json.sample"
MAP_DIRECTORY: str = getDirectoryPath("maps")
MAP_FILE_PATH: str = os.path.join(MAP_DIRECTORY, MAP_FILE)
SAMPLE_MAP_FILE_PATH: str = os.path.join(MAP_DIRECTORY, SAMPLE_MAP_FILE)


def _load(filePath: str) -> Tuple[Union[str, None], Union[Dict[str, Any], None]]:
	if os.path.exists(filePath):
		if not os.path.isdir(filePath):
			try:
				with codecs.open(filePath, "rb", encoding="utf-8") as fileObj:
					return None, json.load(fileObj)
			except IOError as e:
				return f"{e.strerror}: '{e.filename}'", None
			except ValueError:
				return f"Corrupted database file: {filePath}", None
		else:
			return f"Error: '{filePath}' is a directory, not a file.", None
	else:
		return f"Error: '{filePath}' doesn't exist.", None


def loadLabels() -> Tuple[Union[str, None], Union[Dict[str, str], None]]:
	errorMessages: List[str] = []
	labels: Dict[str, str] = {}
	loaded: bool = False
	# First load the sample labels.
	errors, result = _load(SAMPLE_LABELS_FILE_PATH)
	if result is None:
		errorMessages.append(f"While loading sample labels: {errors}")
	else:
		labels.update(result)
		loaded = True
	# Merge any new or modified labels from the user.
	errors, result = _load(LABELS_FILE_PATH)
	if result is None:
		errorMessages.append(f"While loading user labels: {errors}")
	else:
		labels.update(result)
		loaded = True
	return "\n".join(errorMessages) if errorMessages else None, labels if loaded else None


def dumpLabels(labels: Mapping[str, str]) -> None:
	with codecs.open(LABELS_FILE_PATH, "wb", encoding="utf-8") as fileObj:
		json.dump(labels, fileObj, sort_keys=True, indent=2, separators=(",", ": "))


def loadRooms() -> Tuple[Union[str, None], Union[Dict[str, Dict], None]]:
	errorMessages: List[str] = []
	errors, result = _load(MAP_FILE_PATH)
	if result is None:
		errorMessages.append(f"While loading user map: {errors}")
	else:
		return None, result
	errors, result = _load(SAMPLE_MAP_FILE_PATH)
	if result is None:
		errorMessages.append(f"While loading sample map: {errors}")
		return "\n".join(errorMessages), None
	else:
		return None, result


def dumpRooms(rooms: Mapping[str, Room]) -> None:
	with codecs.open(MAP_FILE_PATH, "wb", encoding="utf-8") as fileObj:
		if rapidjson is not None:
			rapidjson.dump(rooms, fileObj, sort_keys=True, indent=2, chunk_size=2 ** 16)
		else:
			fileObj.write(json.dumps(rooms, sort_keys=True, indent=2))
