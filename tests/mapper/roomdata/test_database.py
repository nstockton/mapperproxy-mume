# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from contextlib import ExitStack
from typing import Any, Dict
from unittest import TestCase
from unittest.mock import Mock, _CallList, call, patch

# Third-party Modules:
import rapidjson

# Mapper Modules:
from mapper.roomdata.database import (
	LABELS_FILE_PATH,
	LABELS_SCHEMA_FILE_PATH,
	MAP_FILE_PATH,
	MAP_SCHEMA_FILE_PATH,
	SAMPLE_LABELS_FILE_PATH,
	SAMPLE_MAP_FILE_PATH,
	SchemaValidationError,
	_dump,
	_load,
	_validate,
	dumpLabels,
	dumpRooms,
	loadLabels,
	loadRooms,
)


ROOMS: Dict[str, Any] = {
	"0": {
		"align": "undefined",
		"avoid": False,
		"desc": "This dim tunnel is unfinished and unadorned, the walls still scarred by the picks of Dwarven",
		"dynamicDesc": "Vig the Dwarven smelter stands here, overseeing his store.\n",
		"exits": {
			"east": {
				"door": "",
				"doorFlags": [],
				"exitFlags": ["exit"],
				"to": "1",
			},
		},
		"light": "dark",
		"loadFlags": [],
		"mobFlags": ["shop"],
		"name": "Vig's Shop",
		"note": "",
		"portable": "undefined",
		"ridable": "notridable",
		"terrain": "city",
		"x": 22,
		"y": 225,
		"z": 0,
	},
	"1": {
		"align": "neutral",
		"avoid": False,
		"desc": "The lowest level of the city begins here, where the houses and parks of the",
		"dynamicDesc": "",
		"exits": {
			"west": {
				"door": "",
				"doorFlags": [],
				"exitFlags": ["exit"],
				"to": "0",
			},
		},
		"light": "dark",
		"loadFlags": [],
		"mobFlags": [],
		"name": "Kizdin Crafts",
		"note": "",
		"portable": "portable",
		"ridable": "notridable",
		"terrain": "city",
		"x": 23,
		"y": 225,
		"z": 0,
	},
}


class TestDatabase(TestCase):
	def testValidate(self) -> None:
		schemaPath: str = MAP_SCHEMA_FILE_PATH
		_validate(ROOMS, schemaPath)
		cm: ExitStack
		with ExitStack() as cm:
			cm.enter_context(patch("mapper.roomdata.database.jsonschema.validate"))
			mockLogger: Any = cm.enter_context(self.assertLogs("mapper.roomdata.database", level="WARNING"))
			cm.enter_context(
				self.assertRaises(SchemaValidationError, msg="rapidjson fails validation, jsonschema passes")
			)
			_validate({"invalid": "invalid"}, schemaPath)
			self.assertIn(
				"Error: jsonschema did not raise an exception, whereas rapidjson raised", mockLogger.output
			)
		with self.assertRaises(SchemaValidationError, msg="rapidjson and jsonschema fail validation"):
			_validate({"invalid": "invalid"}, schemaPath)

	@patch("mapper.roomdata.database._validate")
	@patch("mapper.roomdata.database.open")
	@patch("mapper.roomdata.database.os.path")
	def testLoad(self, mockOSPath: Mock, mockOpen: Mock, mockValidate: Mock) -> None:
		fileName: str = "__junk__.json"
		schemaPath: str = MAP_SCHEMA_FILE_PATH
		mockFileObj: Mock = Mock()
		mockOpen.return_value.__enter__.return_value = mockFileObj
		mockOSPath.isdir.return_value = False
		# Check path does not exist.
		mockOSPath.exists.return_value = False
		errors, database = _load(fileName, schemaPath)
		self.assertIsNotNone(errors)
		self.assertIsNone(database)
		mockOSPath.exists.return_value = True
		# Check path is directory.
		mockOSPath.isdir.return_value = True
		errors, database = _load(fileName, schemaPath)
		self.assertIsNotNone(errors)
		self.assertIsNone(database)
		mockOSPath.isdir.return_value = False
		# Check IOError.
		mockFileObj.read.side_effect = lambda *args: (_ for _ in ()).throw(IOError("some error"))
		errors, database = _load(fileName, schemaPath)
		self.assertIsNotNone(errors)
		self.assertIsNone(database)
		# Check corrupted data.
		mockFileObj.read.side_effect = lambda *args: "corrupted data"
		errors, database = _load(fileName, schemaPath)
		self.assertIsNotNone(errors)
		self.assertIsNone(database)
		# Check valid data.
		mockFileObj.read.side_effect = lambda *args: rapidjson.dumps(ROOMS)
		errors, database = _load(fileName, schemaPath)
		self.assertIsNone(errors)
		self.assertIsNotNone(database)
		mockValidate.assert_called_once_with(database, schemaPath)
		self.assertEqual(database, ROOMS)

	@patch("mapper.roomdata.database.rapidjson.dump")
	@patch("mapper.roomdata.database._validate")
	@patch("mapper.roomdata.database.open")
	def testDump(self, mockOpen: Mock, mockValidate: Mock, mockJsonDump: Mock) -> None:
		mockFileObj = Mock()
		mockOpen.return_value.__enter__.return_value = mockFileObj
		_dump(ROOMS, "__junk__.json", MAP_SCHEMA_FILE_PATH)
		mockValidate.assert_called_once_with(ROOMS, MAP_SCHEMA_FILE_PATH)
		mockJsonDump.assert_called_once_with(ROOMS, mockFileObj, sort_keys=True, indent=2, chunk_size=2 ** 16)

	@patch("mapper.roomdata.database._load")
	def testLoadLabels(self, mockLoad: Mock) -> None:
		database: Dict[str, str] = {"label1": "1", "label2": "2"}
		expectedErrors: str = "While loading sample labels: some_error\nWhile loading user labels: some_error"
		mockLoad.return_value = ("some_error", None)
		errors, labels = loadLabels()
		self.assertEqual(errors, expectedErrors)
		self.assertIsNone(labels)
		loadCalls: _CallList = mockLoad.mock_calls
		self.assertEqual(len(loadCalls), 2)
		self.assertEqual(
			loadCalls[0],
			call(SAMPLE_LABELS_FILE_PATH, LABELS_SCHEMA_FILE_PATH),
			"First call to _load was not as expected.",
		)
		self.assertEqual(
			loadCalls[1],
			call(LABELS_FILE_PATH, LABELS_SCHEMA_FILE_PATH),
			"Second call to _load was not as expected.",
		)
		mockLoad.return_value = (None, database)
		errors, labels = loadLabels()
		self.assertIsNone(errors)
		self.assertEqual(labels, database)

	@patch("mapper.roomdata.database._dump")
	def testDumpLabels(self, mockDump: Mock) -> None:
		database: Dict[str, str] = {"label1": "1", "label2": "2"}
		dumpLabels(database)
		mockDump.assert_called_once_with(database, LABELS_FILE_PATH, LABELS_SCHEMA_FILE_PATH)

	@patch("mapper.roomdata.database._load")
	def testLoadRooms(self, mockLoad: Mock) -> None:
		expectedErrors: str = "While loading user map: some_error\nWhile loading sample map: some_error"
		mockLoad.return_value = ("some_error", None)
		errors, rooms = loadRooms()
		self.assertEqual(errors, expectedErrors)
		self.assertIsNone(rooms)
		loadCalls: _CallList = mockLoad.mock_calls
		self.assertEqual(len(loadCalls), 2)
		self.assertEqual(
			loadCalls[0],
			call(MAP_FILE_PATH, MAP_SCHEMA_FILE_PATH),
			"First call to _load was not as expected.",
		)
		self.assertEqual(
			loadCalls[1],
			call(SAMPLE_MAP_FILE_PATH, MAP_SCHEMA_FILE_PATH),
			"Second call to _load was not as expected.",
		)
		mockLoad.return_value = ("some_error", ROOMS)
		errors, rooms = loadRooms()
		self.assertIsNone(errors)
		self.assertEqual(rooms, ROOMS)

	@patch("mapper.roomdata.database._dump")
	def testDumpRooms(self, mockDump: Mock) -> None:
		dumpRooms(ROOMS)
		mockDump.assert_called_once_with(ROOMS, MAP_FILE_PATH, MAP_SCHEMA_FILE_PATH)
