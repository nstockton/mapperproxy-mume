# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, _CallList, call, patch

# Third-party Modules:
import orjson

# Mapper Modules:
from mapper.roomdata.database import _dump  # NOQA: PLC2701
from mapper.roomdata.database import _load  # NOQA: PLC2701
from mapper.roomdata.database import _validate  # NOQA: PLC2701
from mapper.roomdata.database import (
	LABELS_FILE_PATH,
	LABELS_SCHEMA_VERSION,
	MAP_FILE_PATH,
	MAP_SCHEMA_VERSION,
	SAMPLE_LABELS_FILE_PATH,
	SAMPLE_MAP_FILE_PATH,
	dumpLabels,
	dumpRooms,
	getSchemaPath,
	loadLabels,
	loadRooms,
)


LABELS_SCHEMA_FILE_PATH: str = getSchemaPath(LABELS_FILE_PATH, 0)
MAP_SCHEMA_FILE_PATH: str = getSchemaPath(MAP_FILE_PATH, 0)


class TestDatabase(TestCase):
	def setUp(self) -> None:
		self.rooms: dict[str, Any] = {
			"0": {
				"align": "undefined",
				"avoid": False,
				"desc": (
					"This dim tunnel is unfinished and unadorned, "
					+ "the walls still scarred by the picks of Dwarven"
				),
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
				"ridable": "not_ridable",
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
				"ridable": "not_ridable",
				"terrain": "city",
				"x": 23,
				"y": 225,
				"z": 0,
			},
		}

	def tearDown(self) -> None:
		self.rooms.clear()
		del self.rooms

	def testValidate(self) -> None:
		schemaPath: str = MAP_SCHEMA_FILE_PATH
		_validate(self.rooms, schemaPath)
		loggerOutput: str
		with self.assertLogs("mapper.roomdata.database", level="ERROR") as mockLogger:
			_validate({"invalid": "invalid"}, schemaPath)
			loggerOutput = "".join(mockLogger.output)
		self.assertIn(
			"Data failed validation.",
			loggerOutput,
			msg="Expected message not found in logger output.",
		)

	@patch("mapper.roomdata.database._validate")
	@patch("mapper.roomdata.database.open")
	@patch("mapper.roomdata.database.os.path")
	def testLoad(self, mockOSPath: Mock, mockOpen: Mock, mockValidate: Mock) -> None:
		fileName: str = "__junk__.json"
		schemaPath: str = MAP_SCHEMA_FILE_PATH
		mockFileObj: Mock = Mock()
		mockOpen.return_value.__enter__.return_value = mockFileObj
		mockOSPath.isdir.return_value = False
		# Test path does not exist:
		mockOSPath.exists.return_value = False
		errors, database, schemaVersion = _load(fileName)
		self.assertEqual(f"Error: '{fileName}' doesn't exist.", errors)
		self.assertIsNone(database)
		self.assertEqual(schemaVersion, 0)
		mockOSPath.exists.return_value = True
		# Test path is directory:
		mockOSPath.isdir.return_value = True
		errors, database, schemaVersion = _load(fileName)
		self.assertEqual(f"Error: '{fileName}' is a directory, not a file.", errors)
		self.assertIsNone(database)
		self.assertEqual(schemaVersion, 0)
		mockOSPath.isdir.return_value = False
		# Test OSError:
		mockFileObj.read.side_effect = lambda *args: (_ for _ in ()).throw(OSError("some error"))
		errors, database, schemaVersion = _load(fileName)
		self.assertEqual("OSError: some error", errors)
		self.assertIsNone(database)
		self.assertEqual(schemaVersion, 0)
		# Test corrupted data:
		mockFileObj.read.side_effect = lambda *args: "corrupted data"
		errors, database, schemaVersion = _load(fileName)
		self.assertTrue(str(errors).startswith(f"Error: '{fileName}' is corrupted."))
		self.assertIsNone(database)
		self.assertEqual(schemaVersion, 0)
		# Test valid data:
		mockFileObj.read.side_effect = lambda *args: orjson.dumps(self.rooms)
		with patch("mapper.roomdata.database.getSchemaPath", return_value=schemaPath):
			errors, database, schemaVersion = _load(fileName)
		self.assertIsNone(errors)
		self.assertIsNotNone(database)
		self.assertEqual(schemaVersion, 0)
		mockValidate.assert_called_once_with(database, schemaPath)
		self.assertEqual(database, self.rooms)

	@patch("mapper.roomdata.database._validate")
	@patch("mapper.roomdata.database.open")
	def testDump(self, mockOpen: Mock, mockValidate: Mock) -> None:
		mockFileObj = Mock()
		mockOpen.return_value.__enter__.return_value = mockFileObj
		fileName: str = "__junk__.json"
		loggerOutput: str
		# Test invalid database:
		invalidDatabase = {"**integer larger than 53-bit**": 2**53}
		with self.assertLogs("mapper.roomdata.database", level="ERROR") as mockLogger:
			_dump(invalidDatabase, fileName, MAP_SCHEMA_FILE_PATH)
			loggerOutput = "".join(mockLogger.output)
		mockValidate.assert_called_once_with(invalidDatabase, MAP_SCHEMA_FILE_PATH)
		self.assertIn(
			f"Error: Cannot encode to '{fileName}'.",
			loggerOutput,
			msg="Expected message not found in logger output.",
		)
		mockFileObj.write.assert_not_called()
		mockValidate.reset_mock()
		# Test valid database:
		_dump(self.rooms, fileName, MAP_SCHEMA_FILE_PATH)
		mockValidate.assert_called_once_with(self.rooms, MAP_SCHEMA_FILE_PATH)
		mockFileObj.write.assert_called_once()
		mockValidate.reset_mock()
		mockFileObj.reset_mock()
		# Test OSError:
		mockOpen.side_effect = OSError("some error")
		with self.assertLogs("mapper.roomdata.database", level="ERROR") as mockLogger:
			_dump(self.rooms, fileName, MAP_SCHEMA_FILE_PATH)
			loggerOutput = "".join(mockLogger.output)
		mockValidate.assert_called_once_with(self.rooms, MAP_SCHEMA_FILE_PATH)
		self.assertIn(
			"OSError: some error",
			loggerOutput,
			msg="Expected message not found in logger output.",
		)
		mockFileObj.write.assert_not_called()

	@patch("mapper.roomdata.database._load")
	def testLoadLabels(self, mockLoad: Mock) -> None:
		database: dict[str, str] = {"label1": "1", "label2": "2"}
		expectedErrors: str = "While loading sample labels: some_error"
		mockLoad.return_value = ("some_error", None, 0)
		errors, labels, schemaVersion = loadLabels()
		self.assertIn(expectedErrors, str(errors))
		self.assertIsNone(labels)
		self.assertEqual(schemaVersion, 0)
		loadCalls: _CallList = mockLoad.mock_calls
		self.assertGreaterEqual(len(loadCalls), 1)
		self.assertEqual(
			loadCalls[0],
			call(SAMPLE_LABELS_FILE_PATH),
			msg="First call to _load was not as expected.",
		)
		mockLoad.return_value = (None, database, 0)
		errors, labels, schemaVersion = loadLabels()
		self.assertIsNone(errors)
		self.assertEqual(labels, database)
		self.assertEqual(schemaVersion, 0)

	@patch("mapper.roomdata.database._dump")
	def testDumpLabels(self, mockDump: Mock) -> None:  # NOQA: PLR6301
		database: dict[str, str] = {"label1": "1", "label2": "2"}
		dumpLabels(database)
		output: dict[str, Any] = {
			"schema_version": LABELS_SCHEMA_VERSION,
			"labels": dict(database),  # Shallow copy.
		}
		mockDump.assert_called_once_with(
			output, LABELS_FILE_PATH, getSchemaPath(LABELS_FILE_PATH, LABELS_SCHEMA_VERSION)
		)

	@patch("mapper.roomdata.database._load")
	def testLoadRooms(self, mockLoad: Mock) -> None:
		expectedErrors: str = "While loading user map: some_error\nWhile loading sample map: some_error"
		mockLoad.return_value = ("some_error", None, 0)
		errors, rooms, schemaVersion = loadRooms()
		self.assertEqual(errors, expectedErrors)
		self.assertIsNone(rooms)
		self.assertEqual(schemaVersion, 0)
		loadCalls: _CallList = mockLoad.mock_calls
		self.assertEqual(len(loadCalls), 2)
		self.assertEqual(
			loadCalls[0],
			call(MAP_FILE_PATH),
			msg="First call to _load was not as expected.",
		)
		self.assertEqual(
			loadCalls[1],
			call(SAMPLE_MAP_FILE_PATH),
			msg="Second call to _load was not as expected.",
		)
		mockLoad.return_value = ("some_error", self.rooms, 0)
		errors, rooms, schemaVersion = loadRooms()
		self.assertIsNone(errors)
		self.assertEqual(rooms, self.rooms)
		self.assertEqual(schemaVersion, 0)

	@patch("mapper.roomdata.database._dump")
	def testDumpRooms(self, mockDump: Mock) -> None:
		dumpRooms(self.rooms)
		output: dict[str, Any] = dict(self.rooms)  # Shallow copy.
		output["schema_version"] = MAP_SCHEMA_VERSION
		mockDump.assert_called_once_with(
			output, MAP_FILE_PATH, getSchemaPath(MAP_FILE_PATH, MAP_SCHEMA_VERSION)
		)
