# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re
from typing import Union
from unittest import TestCase
from unittest.mock import Mock

# Mapper Modules:
from mapper.cleanmap import EXIT_REGEX, ExitsCleaner
from mapper.mapper import Mapper
from mapper.roomdata.objects import DIRECTIONS, Exit, Room


class test_exitRegex(TestCase):
	def test_exitsCommandRegex_matches_allExitsThatAreNeitherOpenNorBrokenDoors(self) -> None:
		exits: tuple[str, ...] = (
			"[North]  - A closed 'stabledoor'",
			"South   - The Path over the Bruinen",
			"[North]  - A closed 'marblegate'",
			"East    - On a Graceful Bridge",
			"South   - On a Balcony over the Bruinen",
			"West    - Meandering Path along the Bruinen",
			"Up      - At the Last Pavilion",
			"  [North]   - A closed 'curtain'",
			"  [East]   - A closed 'curtainthing'",
			"  [South]   - A closed 'wizardofozcurtain'",
			" ~[West]~   - A closed 'bedroomcurtain'",
			" ~[Up]~   - A closed 'DooMDoor'",
			" ~[Down]~   - A closed 'azZeuZjoec'",
		)
		for item in exits:
			match: Union[re.Match[str], None] = EXIT_REGEX.match(item)
			self.assertIsNotNone(match, f"{item} does not match EXIT_REGEX.")
			if match is not None:
				direction: str = match.group("dir").lower()
				self.assertIn(direction, DIRECTIONS, f"{direction} is not a valid direction.")

	def test_exitRegex_doesNotMatch_exitsThatAreOpenOrBrokenDoors_or_autoexits(self) -> None:
		exits: tuple[str, ...] = (
			"#South#  - (archedfence) The Summer Terrace",
			"  (West)  - (door) a room",
			"None",
			"Exits: down.",
			"Exits: north, east, south, west." "Exits: none.",
		)
		for item in exits:
			match: Union[re.Match[str], None] = EXIT_REGEX.match(item)
			self.assertIsNone(match, f"{item} should not match EXIT_REGEX, but it does.")


class TestExitsCleaner(TestCase):
	def setUp(self) -> None:
		self.mapper: Mock = Mock(spec=Mapper)
		self.mapper.isSynced = True
		self.mapper.autoUpdateRooms = True
		self.exitsCleaner: ExitsCleaner = ExitsCleaner(self.mapper)

	def createRoom(self, *exits: tuple[str, bool]) -> Room:
		room: Room = Room()
		room.vnum = "0"
		for direction, isHidden in exits:
			if direction not in DIRECTIONS:
				raise ValueError(f"Invalid direction {direction}. Cannot create room.")
			room.exits[direction] = Exit()
			if isHidden:
				room.exits[direction].doorFlags.add("hidden")
		return room

	def test_handle_withZeroOrOneExits(self) -> None:
		validExits: tuple[tuple[Room, str], ...] = (
			(self.createRoom(), "None\r\n"),
			(self.createRoom(("east", False)), "None\r\n"),
			(self.createRoom(("south", True)), "None\r\n"),
			(self.createRoom(), "  (West)   - The Grand Hallway\r\n"),
			(self.createRoom(("up", False)), "  #Up#   - Private Stair\r\n"),
			(
				self.createRoom(("down", True)),
				"  [east]   - A closed 'EastDoorWhereYouThoughtThereWasADownExit\r\n",
			),
			(self.createRoom(), "  [North]   - A closed 'Northdoor'\r\n"),
			(self.createRoom(("east", False)), "  {East}   - You see something strange.\r\n"),
			(self.createRoom(), "  /West\\   - Western Slope\r\n"),
			(self.createRoom(("up", False)), "  Up   - Private Stair\r\n"),
			(self.createRoom(("down", True)), "Exits: *=Down=*   - Public Courtyard\r\n"),
		)
		for room, exit in validExits:
			self.mapper.currentRoom = room
			self.exitsCleaner.handle(exit)
			self.mapper.user_command_secret.assert_not_called()
			self.mapper.user_command_secret.reset_mock()
		junkExits: tuple[tuple[Room, str], ...] = (
			(self.createRoom(("south", True)), "  \\South/   - Southern Slope\r\n"),
			(self.createRoom(("down", True)), "  *=Down=*   - Public Courtyard\r\n"),
		)
		for room, exitStr in junkExits:
			self.mapper.currentRoom = room
			match: Union[re.Match[str], None] = EXIT_REGEX.match(exitStr)
			self.assertIsNotNone(match, "Regex does not match exit string.")
			if match is not None:
				direction = match.group("dir").lower()
				self.exitsCleaner.handle(exitStr)
				self.mapper.user_command_secret.assert_called_once_with(f"remove {direction}")
			self.mapper.user_command_secret.reset_mock()
