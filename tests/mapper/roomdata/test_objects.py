# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase

# Mapper Modules:
from mapper.roomdata.objects import DIRECTIONS, Exit, Room
from mapper.utils import ContainerEmptyMixin


class TestExit(TestCase):
	def setUp(self) -> None:
		self.exit: Exit = Exit()

	def tearDown(self) -> None:
		del self.exit

	def testExitDirection(self) -> None:
		with self.assertRaises(ValueError, msg="direction undefined"):
			self.exit.direction
		with self.assertRaises(ValueError, msg="invalid direction"):
			self.exit.direction = "junk"
		self.exit.direction = "north"
		self.assertEqual(self.exit.direction, "north")


class TestRoom(ContainerEmptyMixin, TestCase):
	def setUp(self) -> None:
		self.room: Room = Room()

	def tearDown(self) -> None:
		del self.room

	def testRoomCompare(self) -> None:
		tempRoom: Room = Room()
		self.assertFalse(self.room < tempRoom)

	def testCoordinates(self) -> None:
		self.room.x = 1
		self.room.y = 2
		self.room.z = 3
		self.assertEqual(self.room.coordinates, (1, 2, 3))
		self.room.coordinates = (4, 5, 6)
		self.assertEqual((self.room.x, self.room.y, self.room.z), self.room.coordinates)
		with self.assertRaises(ValueError):
			self.room.coordinates = (1, 2)  # type: ignore[assignment]

	def testRoomSortedExits(self) -> None:
		exits: list[tuple[str, Exit]] = [(direction, Exit()) for direction in DIRECTIONS]
		for direction, exitObj in reversed(exits):
			self.room.exits[direction] = exitObj
		self.assertEqual(self.room.sortedExits, exits)

	def testRoomInfo(self) -> None:
		self.room.vnum = "0"
		self.room.area = "The Blue Mountains"
		self.room.serverID = "1234"  # Fake server room ID.
		self.room.name = "Vig's Shop"
		self.room.desc = (
			"This dim tunnel is unfinished and unadorned, the walls still scarred by the "
			+ "picks of Dwarven miners. Facing the entrance is a huge wooden worktable, made "
			+ "of a single huge slab of oak, which also serves as a counter. Behind it, in the "
			+ "distance, bright red and yellow coals glow fiercely under the great smelting "
			+ "pots. Wood smoke laced with the smells of melted rock and hot metal wafts over "
			+ "the counter whenever a current of air passes this way. A notice has been hung "
			+ "on the wall, and a smaller piece of paper has been nailed beside it."
		)
		self.room.dynamicDesc = "Vig the Dwarven smelter stands here, overseeing his store.\n"
		self.room.terrain = "city"
		self.room.light = "dark"
		self.room.ridable = "not_ridable"
		self.room.sundeath = "no_sundeath"
		self.room.mobFlags.add("shop")
		self.room.x = 22
		self.room.y = 225
		self.room.z = 0
		self.room.calculateCost()
		exitEast: Exit = Exit()
		exitEast.to = "1"
		self.room.exits["east"] = exitEast
		expectedOutput: str = (
			f"vnum: '{self.room.vnum}'\n"
			+ f"Name: '{self.room.name}'\n"
			+ f"Server ID: '{self.room.serverID}'\n"
			+ "Description:\n"
			+ "-----\n"
			+ f"{self.room.desc}\n"
			+ "-----\n"
			+ "Dynamic Desc:\n"
			+ "-----\n"
			+ f"{self.room.dynamicDesc.rstrip()}\n"
			+ "-----\n"
			+ f"Note: '{self.room.note}'\n"
			+ f"Area: '{self.room.area}'\n"
			+ f"Terrain: '{self.room.terrain}'\n"
			+ f"Cost: '{self.room.cost}'\n"
			+ f"Light: '{self.room.light}'\n"
			+ f"Align: '{self.room.align}'\n"
			+ f"Portable: '{self.room.portable}'\n"
			+ f"Ridable: '{self.room.ridable}'\n"
			+ f"Sundeath: '{self.room.sundeath}'\n"
			+ f"Mob Flags: '{', '.join(self.room.mobFlags)}'\n"
			+ f"Load Flags: '{', '.join(self.room.loadFlags)}'\n"
			+ f"Coordinates (X, Y, Z): '{self.room.x}', '{self.room.y}', '{self.room.z}'\n"
			+ "Exits:\n"
			+ "-----\n"
			+ "Direction: 'east'\n"
			+ f"To: '{exitEast.to}'\n"
			+ f"Exit Flags: '{', '.join(exitEast.exitFlags)}'\n"
			+ f"Door Name: '{exitEast.door}'\n"
			+ f"Door Flags: '{', '.join(exitEast.doorFlags)}'"
		)
		self.assertEqual(self.room.info, expectedOutput)

	def testRoomCalculateCost(self) -> None:
		self.room.terrain = "city"
		self.room.calculateCost()
		self.assertEqual(self.room.cost, 0.75)
		self.room.avoid = True
		self.room.calculateCost()
		self.assertEqual(self.room.cost, 1000.75)
		self.room.ridable = "not_ridable"
		self.room.calculateCost()
		self.assertEqual(self.room.cost, 1005.75)

	def testRoomManhattanDistance(self) -> None:
		self.room.x = 12
		self.room.y = 23
		self.room.z = 34
		tempRoom: Room = Room()
		tempRoom.x = 45
		tempRoom.y = 56
		tempRoom.z = 67
		self.assertEqual(self.room.manhattanDistance(tempRoom), 99)

	def testRoomClockPositionTo(self) -> None:
		self.room.vnum = "0"
		self.room.x = 22
		self.room.y = 225
		tempRoom: Room = Room()
		tempRoom.vnum = "0"
		self.assertEqual(self.room.clockPositionTo(tempRoom), "here")
		tempRoom.vnum = "1"
		tempRoom.x = self.room.x
		tempRoom.y = self.room.y
		self.assertEqual(self.room.clockPositionTo(tempRoom), "same X-Y")
		tempRoom.x = 100
		self.assertEqual(self.room.clockPositionTo(tempRoom), "3 o'clock")
		tempRoom.y = 300
		self.assertEqual(self.room.clockPositionTo(tempRoom), "2 o'clock")
		tempRoom.y = 400
		self.assertEqual(self.room.clockPositionTo(tempRoom), "1 o'clock")
		tempRoom.y = 600
		self.assertEqual(self.room.clockPositionTo(tempRoom), "12 o'clock")
		tempRoom.y = 150
		self.assertEqual(self.room.clockPositionTo(tempRoom), "4 o'clock")
		tempRoom.y = 100
		self.assertEqual(self.room.clockPositionTo(tempRoom), "5 o'clock")
		tempRoom.x = 5
		tempRoom.y = self.room.y
		self.assertEqual(self.room.clockPositionTo(tempRoom), "9 o'clock")
		tempRoom.y = 240
		self.assertEqual(self.room.clockPositionTo(tempRoom), "10 o'clock")
		tempRoom.y = 250
		self.assertEqual(self.room.clockPositionTo(tempRoom), "11 o'clock")
		tempRoom.y = 290
		self.assertEqual(self.room.clockPositionTo(tempRoom), "12 o'clock")
		tempRoom.y = 210
		self.assertEqual(self.room.clockPositionTo(tempRoom), "8 o'clock")
		tempRoom.y = 200
		self.assertEqual(self.room.clockPositionTo(tempRoom), "7 o'clock")
		tempRoom.y = 100
		self.assertEqual(self.room.clockPositionTo(tempRoom), "6 o'clock")

	def testRoomDirectionTo(self) -> None:
		self.room.vnum = "0"
		self.room.x = 22
		self.room.y = 225
		tempRoom: Room = Room()
		tempRoom.vnum = "0"
		self.assertEqual(self.room.directionTo(tempRoom), "here")
		tempRoom.vnum = "1"
		tempRoom.x = self.room.x
		tempRoom.y = self.room.y
		self.assertEqual(self.room.directionTo(tempRoom), "same X-Y")
		tempRoom.x = 100
		self.assertEqual(self.room.directionTo(tempRoom), "east")
		tempRoom.y = 300
		self.assertEqual(self.room.directionTo(tempRoom), "northeast")
		tempRoom.y = 600
		self.assertEqual(self.room.directionTo(tempRoom), "north")
		tempRoom.y = 150
		self.assertEqual(self.room.directionTo(tempRoom), "southeast")
		tempRoom.x = 5
		tempRoom.y = self.room.y
		self.assertEqual(self.room.directionTo(tempRoom), "west")
		tempRoom.y = 240
		self.assertEqual(self.room.directionTo(tempRoom), "northwest")
		tempRoom.y = 290
		self.assertEqual(self.room.directionTo(tempRoom), "north")
		tempRoom.y = 210
		self.assertEqual(self.room.directionTo(tempRoom), "southwest")
		tempRoom.y = 100
		self.assertEqual(self.room.directionTo(tempRoom), "south")

	def testIsOrphan(self) -> None:
		self.assertContainerEmpty(self.room.exits)
		self.assertTrue(self.room.isOrphan())
		self.room.exits["north"] = Exit()
		self.room.exits["north"].to = "undefined"
		self.room.exits["south"] = Exit()
		self.room.exits["south"].to = "undefined"
		self.assertTrue(self.room.isOrphan())
		self.room.exits["east"] = Exit()
		self.room.exits["east"].to = "0"
		self.assertFalse(self.room.isOrphan())

	def testHasUndefinedExits(self) -> None:
		self.assertContainerEmpty(self.room.exits)
		self.assertFalse(self.room.hasUndefinedExits())
		self.room.exits["north"] = Exit()
		self.room.exits["north"].to = "undefined"
		self.room.exits["east"] = Exit()
		self.room.exits["east"].to = "0"
		self.assertTrue(self.room.hasUndefinedExits())
