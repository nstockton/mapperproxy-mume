# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import gc
import heapq
import itertools
import re
import threading
import warnings
from collections.abc import Callable, Generator, Iterable, MutableSequence, Sequence
from contextlib import suppress
from queue import SimpleQueue
from timeit import default_timer as defaultTimer
from typing import TYPE_CHECKING, Any, Optional, Union

# Third-party Modules:
from rapidfuzz import fuzz

# Local Modules:
from .roomdata.database import (
	LABELS_SCHEMA_VERSION,
	MAP_SCHEMA_VERSION,
	dumpLabels,
	dumpRooms,
	loadLabels,
	loadRooms,
)
from .roomdata.objects import (
	DIRECTION_COORDINATES,
	DIRECTIONS,
	REVERSE_DIRECTIONS,
	TERRAIN_COSTS,
	VALID_DOOR_FLAGS,
	VALID_EXIT_FLAGS,
	VALID_LOAD_FLAGS,
	VALID_MOB_FLAGS,
	Exit,
	Room,
)
from .typedef import COORDINATES_TYPE, GUI_QUEUE_TYPE, REGEX_MATCH, REGEX_PATTERN
from .utils import regexFuzzy


if TYPE_CHECKING:  # pragma: no cover
	# Only import pyglet.window if type checking. Prevents slowdown during tests.
	import pyglet.window


# Ignore warning from Pyglet's Windows Imaging Component module.
warnings.filterwarnings(
	"ignore",
	message=r"\[WinError -2147417850\] Cannot change thread mode after it is set",
)


# Ignore warnings from Pyglet Windows OpenGL context functions due to unescaped path separators in strings.
warnings.filterwarnings(
	"ignore",
	category=SyntaxWarning,
	module=r".*?pyglet.gl.wgl",
)


LEAD_BEFORE_ENTERING_VNUMS: list[str] = ["196", "3473", "3474", "12138", "12637"]
LIGHT_SYMBOLS: dict[str, str] = {
	"*": "lit",  # Sunlight, either direct or indirect.
	"!": "undefined",  # Artificial light.
	")": "lit",  # Moonlight, either direct or indirect.
	"o": "dark",  # Darkness.
}
RUN_DESTINATION_REGEX: REGEX_PATTERN = re.compile(r"^(?P<destination>.+?)(?:\s+(?P<flags>\S+))?$")
TERRAIN_SYMBOLS: dict[str, str] = {
	":": "brush",
	"[": "building",
	"O": "cavern",
	"#": "city",
	".": "field",
	"f": "forest",
	"(": "hills",
	"<": "mountains",
	"W": "rapids",
	"+": "road",
	"%": "shallows",
	"=": "tunnel",
	"?": "undefined",
	"U": "underwater",
	"~": "water",
}


class World(object):
	def __init__(self, interface: str = "text") -> None:
		self.roomsLock = threading.Lock()
		self.isSynced: bool = False
		self.rooms: dict[str, Room] = {}
		self.labels: dict[str, str] = {}
		self._interface: str = interface
		if interface != "text":
			self._gui_queue: GUI_QUEUE_TYPE = SimpleQueue()
			self.window: pyglet.window.Window  # type: ignore[no-any-unimported]
			if interface == "hc":
				from .gui import hc

				self.window = hc.Window(self)
			elif interface == "sighted":
				from .gui import sighted

				self.window = sighted.Window(self)
		self._currentRoom: Room = Room()
		self.loadRooms()
		self.loadLabels()

	@property
	def currentRoom(self) -> Room:
		return self._currentRoom

	@currentRoom.setter
	def currentRoom(self, value: Room) -> None:
		self._currentRoom = value
		if self._interface != "text":
			self._gui_queue.put(("on_mapSync", value))

	@currentRoom.deleter
	def currentRoom(self) -> None:
		self._currentRoom = Room()

	def GUIRefresh(self) -> None:
		"""Trigger the clearing and redrawing of rooms by the GUI"""
		if self._interface != "text":
			self._gui_queue.put(("on_guiRefresh",))

	def output(self, text: str) -> None:
		print(text)

	def loadRoomsV0(self, db: dict[str, dict[str, Any]]) -> None:
		terrainReplacements: dict[str, str] = {
			"indoors": "building",
			"random": "undefined",
			"shallow": "shallows",
			"shallowwater": "shallows",
		}
		loadFlagReplacements: dict[str, str] = {
			"packhorse": "pack_horse",
			"trainedhorse": "trained_horse",
		}
		mobFlagReplacements: dict[str, str] = {
			"any": "passive_mob",
			"smob": "aggressive_mob",
			"quest": "quest_mob",
			"scoutguild": "scout_guild",
			"mageguild": "mage_guild",
			"clericguild": "cleric_guild",
			"warriorguild": "warrior_guild",
			"rangerguild": "ranger_guild",
			"armourshop": "armour_shop",
			"foodshop": "food_shop",
			"petshop": "pet_shop",
			"weaponshop": "weapon_shop",
		}
		doorFlagReplacements: dict[str, str] = {
			"noblock": "no_block",
			"nobreak": "no_break",
			"nopick": "no_pick",
			"needkey": "need_key",
		}
		portableReplacements: dict[str, str] = {
			"notportable": "not_portable",
		}
		ridableReplacements: dict[str, str] = {
			"notridable": "not_ridable",
		}
		for vnum, roomDict in db.items():
			if not vnum.isdigit():
				# This should never happen, but safe to ignore if it does.
				# Todo: add a warning to alert the user here.
				continue
			elif roomDict["terrain"].startswith("death"):  # handles "death" and "deathtrap".
				# This should never happen, but safe to ignore if it does.
				# Todo: add a warning to alert the user here.
				continue
			newRoom: Room = Room()
			newRoom.vnum = vnum
			newRoom.align = roomDict["align"]
			with suppress(KeyError):
				newRoom.avoid = roomDict["avoid"]
			newRoom.desc = roomDict["desc"]
			newRoom.dynamicDesc = roomDict["dynamicDesc"]
			for direction, exitDict in roomDict["exits"].items():
				newExit: Exit = self.getNewExit(direction, exitDict["to"], vnum)
				newExit.door = exitDict["door"]
				newExit.doorFlags = {doorFlagReplacements.get(flag, flag) for flag in exitDict["doorFlags"]}
				newExit.exitFlags = set(exitDict["exitFlags"])
				newRoom.exits[direction] = newExit
				exitDict.clear()
			newRoom.light = roomDict["light"]
			newRoom.loadFlags = {loadFlagReplacements.get(flag, flag) for flag in roomDict["loadFlags"]}
			newRoom.mobFlags = {mobFlagReplacements.get(flag, flag) for flag in roomDict["mobFlags"]}
			newRoom.name = roomDict["name"]
			newRoom.note = roomDict["note"]
			portable: str = roomDict["portable"]
			newRoom.portable = portableReplacements.get(portable, portable)
			ridable: str = roomDict["ridable"]
			newRoom.ridable = ridableReplacements.get(ridable, ridable)
			with suppress(KeyError):
				newRoom.sundeath = roomDict["sundeath"]
			terrain: str = roomDict["terrain"]
			newRoom.terrain = terrainReplacements.get(terrain, terrain)
			newRoom.x = roomDict["x"]
			newRoom.y = roomDict["y"]
			newRoom.z = roomDict["z"]
			newRoom.calculateCost()
			self.rooms[vnum] = newRoom
			roomDict.clear()

	def loadRoomsV1Through2(self, db: dict[str, dict[str, Any]], schemaVersion: int) -> None:
		for vnum, roomDict in db.items():
			newRoom: Room = Room()
			newRoom.vnum = vnum
			newRoom.align = roomDict["alignment"]
			newRoom.avoid = roomDict["avoid"]
			newRoom.desc = roomDict["description"]
			newRoom.dynamicDesc = roomDict["contents"]
			for direction, exitDict in roomDict["exits"].items():
				newExit: Exit = self.getNewExit(direction, exitDict["to"], vnum)
				newExit.door = exitDict["door"]
				newExit.doorFlags = set(exitDict["door_flags"])
				newExit.exitFlags = set(exitDict["exit_flags"])
				newRoom.exits[direction] = newExit
				exitDict.clear()
			newRoom.light = roomDict["light"]
			newRoom.loadFlags = set(roomDict["load_flags"])
			newRoom.mobFlags = set(roomDict["mob_flags"])
			newRoom.name = roomDict["name"]
			newRoom.note = roomDict["note"]
			newRoom.portable = roomDict["portable"]
			newRoom.ridable = roomDict["ridable"]
			newRoom.sundeath = roomDict["sundeath"]
			newRoom.terrain = roomDict["terrain"]
			newRoom.coordinates = roomDict["coordinates"]
			if schemaVersion >= 2:
				newRoom.area = roomDict["area"]
				newRoom.serverID = roomDict["server_id"]
			newRoom.calculateCost()
			self.rooms[vnum] = newRoom
			roomDict.clear()

	def loadRooms(self) -> None:
		startTime: float = defaultTimer()
		if gc.isenabled():
			gc.disable()
		self.output("Loading the database file.")
		errors: Union[str, None]
		db: Union[dict[str, dict[str, Any]], None]
		errors, db, schemaVersion = loadRooms()
		if db is None:
			if errors is not None:
				self.output(errors)
			return None
		schemaVersionOutput: str = "latest" if schemaVersion == MAP_SCHEMA_VERSION else f"V{schemaVersion}"
		self.output(f"Creating room objects with {schemaVersionOutput} schema.")
		with self.roomsLock:
			if schemaVersion < 1:
				self.loadRoomsV0(db)
			else:
				self.loadRoomsV1Through2(db, schemaVersion)
		db.clear()
		self.currentRoom = self.rooms["0"]
		if not gc.isenabled():
			gc.enable()
			gc.collect()
		elapsedTime: float = defaultTimer() - startTime
		self.output(f"Map database loaded in {elapsedTime:.1f} seconds.")

	def saveRooms(self) -> None:
		startTime: float = defaultTimer()
		if gc.isenabled():
			gc.disable()
		self.output("Creating dict from room objects.")
		db: dict[str, dict[str, Any]] = {}
		with self.roomsLock:
			for vnum, roomObj in self.rooms.items():
				newRoom: dict[str, Any] = {}
				newRoom["alignment"] = roomObj.align
				newRoom["area"] = roomObj.area
				newRoom["avoid"] = roomObj.avoid
				newRoom["contents"] = roomObj.dynamicDesc
				newRoom["coordinates"] = roomObj.coordinates
				newRoom["description"] = roomObj.desc
				newRoom["exits"] = {}
				for direction, exitObj in roomObj.exits.items():
					newExit: dict[str, Any] = {}
					newExit["door"] = exitObj.door
					newExit["door_flags"] = sorted(exitObj.doorFlags)
					newExit["exit_flags"] = sorted(exitObj.exitFlags)
					newExit["to"] = exitObj.to
					newRoom["exits"][direction] = newExit
				newRoom["light"] = roomObj.light
				newRoom["load_flags"] = sorted(roomObj.loadFlags)
				newRoom["mob_flags"] = sorted(roomObj.mobFlags)
				newRoom["name"] = roomObj.name
				newRoom["note"] = roomObj.note
				newRoom["portable"] = roomObj.portable
				newRoom["ridable"] = roomObj.ridable
				newRoom["server_id"] = roomObj.serverID
				newRoom["sundeath"] = roomObj.sundeath
				newRoom["terrain"] = roomObj.terrain
				db[vnum] = newRoom
		self.output("Saving the database.")
		dumpRooms(db)
		if not gc.isenabled():
			gc.enable()
			gc.collect()
		elapsedTime: float = defaultTimer() - startTime
		self.output(f"Map Database saved in {elapsedTime:.1f} seconds.")

	def loadLabels(self) -> None:
		errors: Union[str, None]
		labels: Union[dict[str, str], None]
		schemaVersion: int
		errors, labels, schemaVersion = loadLabels()
		if labels is None:
			if errors is not None:
				self.output(errors)
			return None
		self.labels.update(labels)
		schemaVersionOutput: str = "latest" if schemaVersion == LABELS_SCHEMA_VERSION else f"V{schemaVersion}"
		self.output(f"Loaded room labels with {schemaVersionOutput} schema.")
		orphans: list[str] = [label for label, vnum in self.labels.items() if vnum not in self.rooms]
		if orphans:
			for label in orphans:
				del self.labels[label]
			self.output(f"Detected orphan labels: {', '.join(orphans)}")
			self.output(f"{len(orphans)} orphan labels removed.")

	def saveLabels(self) -> None:
		dumpLabels(self.labels)

	def getNewExit(self, direction: str, to: str = "undefined", vnum: Optional[str] = None) -> Exit:
		"""
		Creates a new exit object for a given direction.

		Args:
			direction: The direction of movement (north, east, south, west, up, down).
			to: The destination that the exit points to. Can be a vnum, 'undefined', or 'death'.
			vnum: The vnum of the room that the exit belongs to, defaults to self.currentRoom.vnum.

		Returns:
			The new exit object.
		"""
		newExit: Exit = Exit()
		newExit.direction = direction
		newExit.to = to
		newExit.vnum = self.currentRoom.vnum if vnum is None else vnum
		return newExit

	def isBidirectional(self, exitObj: Exit) -> bool:
		"""
		Returns True if an exit is bidirectional, False if unidirectional.
		I.E. True if moving in a given direction then moving back in the direction
		you just came from would put you back where you started, False otherwise.
		"""
		try:
			dest: Room = self.rooms[exitObj.to]
		except KeyError:
			return False
		revdir: str = REVERSE_DIRECTIONS[exitObj.direction]
		if revdir in dest.exits and dest.exits[revdir].to == exitObj.vnum:
			return True
		else:
			return False

	def getNeighborsFromCoordinates(
		self, start: Sequence[int], radius: Sequence[int]
	) -> Generator[tuple[str, Room, int, int, int], None, None]:
		"""A generator which yields all rooms in the vicinity of the given X-Y-Z coordinates.
		Each yielded result contains the vnum, room object reference, and difference in X-Y-Z coordinates."""
		x, y, z = start
		radiusX, radiusY, radiusZ = radius
		for vnum, obj in self.rooms.items():
			if obj.x == x and obj.y == y and obj.z == z:
				continue
			differenceX, differenceY, differenceZ = obj.x - x, obj.y - y, obj.z - z
			if abs(differenceX) <= radiusX and abs(differenceY) <= radiusY and abs(differenceZ) <= radiusZ:
				yield (vnum, obj, differenceX, differenceY, differenceZ)

	def getNeighborsFromRoom(
		self, start: Room, radius: Sequence[int]
	) -> Generator[tuple[str, Room, int, int, int], None, None]:
		"""A generator which yields all rooms in the vicinity of a room object.
		Each yielded result contains the vnum, room object reference, and difference in X-Y-Z coordinates."""
		x, y, z = start.x, start.y, start.z
		radiusX, radiusY, radiusZ = radius
		for vnum, obj in self.rooms.items():
			differenceX, differenceY, differenceZ = obj.x - x, obj.y - y, obj.z - z
			if (
				abs(differenceX) <= radiusX
				and abs(differenceY) <= radiusY
				and abs(differenceZ) <= radiusZ
				and obj is not start
			):
				yield (vnum, obj, differenceX, differenceY, differenceZ)

	def getVnum(self, roomObj: Room) -> Union[str, None]:
		result: Union[str, None] = None
		for vnum, obj in self.rooms.items():
			if obj is roomObj:
				result = vnum
				break
		return result

	def coordinatesSubtract(self, first: Sequence[int], second: Sequence[int]) -> tuple[int, ...]:
		return tuple(a - b for a, b in zip(first, second))

	def coordinatesAdd(self, first: Sequence[int], second: Sequence[int]) -> tuple[int, ...]:
		return tuple(a + b for a, b in zip(first, second))

	def coordinatesAddDirection(self, coordinates: Sequence[int], direction: str) -> tuple[int, ...]:
		if direction not in DIRECTIONS:
			raise ValueError(f"Direction must be one of {DIRECTIONS}.")
		return self.coordinatesAdd(coordinates, DIRECTION_COORDINATES[direction])

	def getNewVnum(self) -> str:
		return str(max(int(i) for i in self.rooms) + 1)

	def revnum(self, text: str = "") -> None:
		text = text.strip().lower()
		match: REGEX_MATCH = re.match(r"^(?:(?P<origin>\d+)\s+)?(?:\s*(?P<destination>\d+)\s*)$", text)
		if match is None:
			self.output("Syntax: 'revnum [Origin VNum] [Destination VNum]'.")
			return None
		matchDict: dict[str, str] = match.groupdict()
		if not matchDict["destination"]:
			self.output("Error: you need to supply a destination VNum.")
			return None
		destination = matchDict["destination"]
		if not matchDict["origin"]:
			origin = self.currentRoom.vnum
			self.output(f"Changing the VNum of the current room to '{destination}'.")
		else:
			origin = matchDict["origin"]
			self.output(f"Changing the Vnum '{origin}' to '{destination}'.")
		for roomVnum, roomObj in self.rooms.items():
			for direction, exitObj in roomObj.exits.items():
				if roomVnum == origin:
					exitObj.vnum = destination
				if exitObj.to == origin:
					self.rooms[roomVnum].exits[direction].to = destination
		self.rooms[origin].vnum = destination
		self.rooms[destination] = self.rooms[origin]
		del self.rooms[origin]

	def rdelete(self, text: str) -> str:
		text = text.strip().lower()
		vnum: str
		if text.isdigit():
			vnum = text
			if self.currentRoom.vnum == vnum:
				self.isSynced = False
				self.currentRoom = self.rooms.get("0", Room())
			elif vnum not in self.rooms:
				return f"Error: the vnum '{vnum}' does not exist."
		elif self.isSynced:
			vnum = self.currentRoom.vnum
			self.isSynced = False
			self.currentRoom = self.rooms.get("0", Room())
		else:
			return "Syntax: rdelete [vnum]"
		output = f"Deleting room '{vnum}' with name '{self.rooms[vnum].name}'."
		with self.roomsLock:
			for roomVnum, roomObj in self.rooms.items():
				for direction, exitObj in roomObj.exits.items():
					if exitObj.to == vnum:
						self.rooms[roomVnum].exits[direction].to = "undefined"
			del self.rooms[vnum]
		self.GUIRefresh()
		return output

	def searchRooms(self, exactMatch: bool = False, **kwargs: str) -> list[Room]:
		validArgs: tuple[str, ...] = (
			"area",
			"serverID",
			"name",
			"desc",
			"dynamicDesc",
			"note",
			"terrain",
			"light",
			"align",
			"portable",
			"ridable",
			"sundeath",
			"x",
			"y",
			"z",
			"mobFlags",
			"loadFlags",
			"exitFlags",
			"doorFlags",
			"to",
			"door",
		)
		observeExactMatch: tuple[str, ...] = ("area", "name", "desc", "dynamicDesc", "note")
		alwaysExactMatch: tuple[str, ...] = (
			"serverID",
			"terrain",
			"light",
			"align",
			"portable",
			"ridable",
			"sundeath",
			"x",
			"y",
			"z",
		)
		kwargs = {
			key: value.strip().lower()
			for key, value in kwargs.items()
			if key.strip() in validArgs and value.strip()
		}
		results: list[Room] = []
		if not kwargs:
			return results
		for vnum, roomObj in self.rooms.items():
			keysMatched = 0
			for key, value in kwargs.items():
				if key in observeExactMatch:
					roomData = getattr(roomObj, key).strip().lower()
					if not exactMatch and value in roomData or roomData == value:
						keysMatched += 1
				elif key in alwaysExactMatch and getattr(roomObj, key).strip().lower() == value:
					keysMatched += 1
				elif key in ("mobFlags", "loadFlags") and getattr(roomObj, key, set()).intersection(value):
					keysMatched += 1
				else:
					for direction, exitObj in roomObj.exits.items():
						if key in ("exitFlags", "doorFlags") and getattr(exitObj, key, set()).intersection(
							value
						):
							keysMatched += 1
						elif key in ("to", "door") and getattr(exitObj, key, "").strip().lower() == value:
							keysMatched += 1
			if len(kwargs) == keysMatched:
				results.append(roomObj)
		return results

	def fdoor(self, findFormat: str, text: str = "") -> str:
		if not text.strip():
			return "Usage: 'fdoor [text]'."
		results: list[Room] = self.searchRooms(door=text)
		if not results:
			return "Nothing found."
		currentRoom: Room = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=", ".join(
					exitDir + ": " + exitObj.door
					for exitDir, exitObj in roomObj.exits.items()
					if text.strip() in exitObj.door
				),
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(results[:20])
		)

	def fdynamic(self, findFormat: str, text: str = "") -> str:
		if not text.strip():
			return "Usage: 'fdynamic [text]'."
		results: list[Room] = self.searchRooms(dynamicDesc=text)
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=roomObj.dynamicDesc,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(results[:20])
		)

	def flabel(self, findFormat: str, text: str = "") -> str:
		if not self.labels:
			return "No labels defined."
		text = text.strip().lower()
		results: set[Room] = {
			self.rooms[vnum]
			for label, vnum in self.labels.items()
			if text and text in label.strip().lower() or not text
		}
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		return "\n".join(
			findFormat.format(
				attribute=self.getlabel(roomObj.vnum),
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(sorted(results, key=lambda r: r.manhattanDistance(currentRoom))[:20])
		)

	def fname(self, findFormat: str, text: str = "") -> str:
		if not text.strip():
			return "Usage: 'fname [text]'."
		results: list[Room] = self.searchRooms(name=text)
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute="" if "{name}" in findFormat and "{attribute}" in findFormat else roomObj.name,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(results[:20])
		)

	def fnote(self, findFormat: str, text: str = "") -> str:
		if not text.strip():
			return "Usage: 'fnote [text]'."
		results: list[Room] = self.searchRooms(note=text)
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=roomObj.note,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(results[:20])
		)

	def farea(self, findFormat: str, text: str = "") -> str:
		if not text.strip():
			return "Usage: 'farea [text]'."
		results: list[Room] = self.searchRooms(area=text)
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=roomObj.area,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(results[:20])
		)

	def fsid(self, findFormat: str, text: str = "") -> str:
		if not text.strip().isdigit():
			return "Usage: 'fsid [number]'."
		results: list[Room] = self.searchRooms(serverID=text)
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=roomObj.serverID,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**{i: getattr(roomObj, i) for i in dir(roomObj)},
			)
			for roomObj in reversed(results[:20])
		)

	def rnote(self, text: str = "") -> str:
		text = text.strip()
		if not text:
			return (
				f"Room note set to '{self.currentRoom.note}'. Use 'rnote [text]' to change it, "
				+ "'rnote -a [text]' to append to it, or 'rnote -r' to remove it."
			)
		if text.lower().startswith("-r"):
			if len(text) > 2:
				return "Error: '-r' requires no extra arguments. Change aborted."
			self.currentRoom.note = ""
			return "Note removed."
		elif text.lower().startswith("-a"):
			if len(text) == 2:
				return "Error: '-a' requires text to be appended. Change aborted."
			self.currentRoom.note = f"{self.currentRoom.note.strip()} {text[2:].strip()}"
		else:
			self.currentRoom.note = text
		return f"Room note now set to '{self.currentRoom.note}'."

	def ralign(self, text: str = "") -> str:
		text = text.strip().lower()
		validValues: tuple[str, ...] = ("good", "neutral", "evil", "undefined")
		if text not in validValues:
			return (
				f"Room alignment set to '{self.currentRoom.align}'. "
				+ f"Use 'ralign [{' | '.join(validValues)}]' to change it."
			)
		self.currentRoom.align = text
		return f"Setting room align to '{self.currentRoom.align}'."

	def rlight(self, text: str = "") -> str:
		text = text.strip()
		if not text:
			return (
				f"Room light set to '{self.currentRoom.light}'. "
				+ f"Use 'rlight [{' | '.join(set(LIGHT_SYMBOLS.values()))}]' to change it."
			)
		elif text not in LIGHT_SYMBOLS and text.lower() not in LIGHT_SYMBOLS.values():
			return (
				f"Invalid value for room light ({text}). "
				+ f"Valid values are [{' | '.join(set(LIGHT_SYMBOLS.values()))}]."
			)
		try:
			self.currentRoom.light = LIGHT_SYMBOLS[text]
		except KeyError:
			self.currentRoom.light = text.lower()
		return f"Setting room light to '{self.currentRoom.light}'."

	def rportable(self, text: str = "") -> str:
		text = text.strip().lower()
		validValues: tuple[str, ...] = ("portable", "not_portable", "undefined")
		if text not in validValues:
			return (
				f"Room portable set to '{self.currentRoom.portable}'. "
				+ f"Use 'rportable [{' | '.join(validValues)}]' to change it."
			)
		self.currentRoom.portable = text
		return f"Setting room portable to '{self.currentRoom.portable}'."

	def rridable(self, text: str = "") -> str:
		text = text.strip().lower()
		validValues: tuple[str, ...] = (
			"ridable",
			"not_ridable",
			"undefined",
		)
		if text not in validValues:
			return (
				f"Room ridable set to '{self.currentRoom.ridable}'. "
				+ f"Use 'rridable [{' | '.join(validValues)}]' to change it."
			)
		self.currentRoom.ridable = text
		self.currentRoom.calculateCost()
		return f"Setting room ridable to '{self.currentRoom.ridable}'."

	def rsundeath(self, text: str = "") -> str:
		text = text.strip().lower()
		validValues: tuple[str, ...] = ("sundeath", "no_sundeath", "undefined")
		if text not in validValues:
			return (
				f"Room sundeath set to '{self.currentRoom.sundeath}'. "
				+ f"Use 'rsundeath [{' | '.join(validValues)}]' to change it."
			)
		self.currentRoom.sundeath = text
		return f"Setting room sundeath to '{self.currentRoom.sundeath}'."

	def ravoid(self, text: str = "") -> str:
		text = text.strip().lower()
		validValues: tuple[str, ...] = ("+", "-")
		if text not in validValues:
			return (
				f"Room avoid {'enabled' if self.currentRoom.avoid else 'disabled'}. "
				+ f"Use 'ravoid [{' | '.join(validValues)}]' to change it."
			)
		self.currentRoom.avoid = text == "+"
		self.currentRoom.calculateCost()
		return f"{'Enabling' if self.currentRoom.avoid else 'Disabling'} room avoid."

	def rterrain(self, text: str = "") -> str:
		text = text.strip()
		if not text:
			return (
				f"Room terrain set to '{self.currentRoom.terrain}'. "
				+ f"Use 'rterrain [{' | '.join(sorted(TERRAIN_SYMBOLS.values()))}]' to change it."
			)
		elif text not in TERRAIN_SYMBOLS and text.lower() not in TERRAIN_SYMBOLS.values():
			return (
				f"Invalid value for room terrain ({text}). "
				+ f"Valid values are [{' | '.join(sorted(TERRAIN_SYMBOLS.values()))}]."
			)
		try:
			self.currentRoom.terrain = TERRAIN_SYMBOLS[text]
		except KeyError:
			self.currentRoom.terrain = text.lower()
		self.currentRoom.calculateCost()
		self.GUIRefresh()
		return f"Setting room terrain to '{self.currentRoom.terrain}'."

	def rx(self, text: str = "") -> str:
		text = text.strip().lower()
		if not text:
			return f"Room coordinate X set to '{self.currentRoom.x}'. Use 'rx [digit]' to change it."
		try:
			self.currentRoom.x = int(text)
			self.GUIRefresh()
			return f"Setting room X coordinate to '{self.currentRoom.x}'."
		except ValueError:
			return "Error: room coordinates must be comprised of digits only."

	def ry(self, text: str = "") -> str:
		text = text.strip().lower()
		if not text:
			return f"Room coordinate Y set to '{self.currentRoom.y}'. Use 'ry [digit]' to change it."
		try:
			self.currentRoom.y = int(text)
			self.GUIRefresh()
			return f"Setting room Y coordinate to '{self.currentRoom.y}'."
		except ValueError:
			return "Error: room coordinates must be comprised of digits only."

	def rz(self, text: str = "") -> str:
		text = text.strip().lower()
		if not text:
			return f"Room coordinate Z set to '{self.currentRoom.z}'. Use 'rz [digit]' to change it."
		try:
			self.currentRoom.z = int(text)
			self.GUIRefresh()
			return f"Setting room Z coordinate to '{self.currentRoom.z}'."
		except ValueError:
			return "Error: room coordinates must be comprised of digits only."

	def rmobflags(self, text: str = "") -> str:
		text = text.strip().lower()
		matchPattern: str = (
			rf"^(?P<mode>{regexFuzzy('add')}|{regexFuzzy('remove')})"
			+ rf"\s+(?P<flag>{'|'.join(VALID_MOB_FLAGS)})"
		)
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is not None:
			matchDict: dict[str, str] = match.groupdict()
			if "remove".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.mobFlags:
					self.currentRoom.mobFlags.remove(matchDict["flag"])
					return f"Mob flag '{matchDict['flag']}' removed."
				else:
					return f"Mob flag '{matchDict['flag']}' not set."
			elif "add".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.mobFlags:
					return f"Mob flag '{matchDict['flag']}' already set."
				else:
					self.currentRoom.mobFlags.add(matchDict["flag"])
					return f"Mob flag '{matchDict['flag']}' added."
		return (
			f"Mob flags set to '{', '.join(self.currentRoom.mobFlags)}'. "
			+ f"Use 'rmobflags [add | remove] [{' | '.join(VALID_MOB_FLAGS)}]' to change them."
		)

	def rloadflags(self, text: str = "") -> str:
		text = text.strip().lower()
		matchPattern: str = (
			rf"^(?P<mode>{regexFuzzy('add')}|{regexFuzzy('remove')})"
			+ rf"\s+(?P<flag>{'|'.join(VALID_LOAD_FLAGS)})"
		)
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is not None:
			matchDict: dict[str, str] = match.groupdict()
			if "remove".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.loadFlags:
					self.currentRoom.loadFlags.remove(matchDict["flag"])
					return f"Load flag '{matchDict['flag']}' removed."
				else:
					return f"Load flag '{matchDict['flag']}' not set."
			elif "add".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.loadFlags:
					return f"Load flag '{matchDict['flag']}' already set."
				else:
					self.currentRoom.loadFlags.add(matchDict["flag"])
					return f"Load flag '{matchDict['flag']}' added."
		return (
			f"Load flags set to '{', '.join(self.currentRoom.loadFlags)}'. "
			+ f"Use 'rloadflags [add | remove] [{' | '.join(VALID_LOAD_FLAGS)}]' to change them."
		)

	def exitflags(self, text: str = "") -> str:
		text = text.strip().lower()
		matchPattern: str = (
			rf"^((?P<mode>{regexFuzzy('add')}|{regexFuzzy('remove')})\s+)?"
			+ rf"((?P<flag>{'|'.join(VALID_EXIT_FLAGS)})\s+)?(?P<direction>{regexFuzzy(DIRECTIONS)})"
		)
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is not None:
			matchDict: dict[str, str] = match.groupdict()
			direction: str = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
			if direction not in self.currentRoom.exits:
				return f"Exit {direction} does not exist."
			elif not matchDict["mode"]:
				return (
					f"Exit flags '{direction}' set to '{', '.join(self.currentRoom.exits[direction].exitFlags)}'."
				)
			elif "remove".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.exits[direction].exitFlags:
					self.currentRoom.exits[direction].exitFlags.remove(matchDict["flag"])
					return f"Exit flag '{matchDict['flag']}' in direction '{direction}' removed."
				else:
					return f"Exit flag '{matchDict['flag']}' in direction '{direction}' not set."
			elif "add".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.exits[direction].exitFlags:
					return f"Exit flag '{matchDict['flag']}' in direction '{direction}' already set."
				else:
					self.currentRoom.exits[direction].exitFlags.add(matchDict["flag"])
					return f"Exit flag '{matchDict['flag']}' in direction '{direction}' added."
		return (
			f"Syntax: 'exitflags [add | remove] [{' | '.join(VALID_EXIT_FLAGS)}] "
			+ f"[{' | '.join(DIRECTIONS)}]'."
		)

	def doorflags(self, text: str = "") -> str:
		text = text.strip().lower()
		matchPattern: str = (
			rf"^((?P<mode>{regexFuzzy('add')}|{regexFuzzy('remove')})\s+)?"
			+ rf"((?P<flag>{'|'.join(VALID_DOOR_FLAGS)})\s+)?(?P<direction>{regexFuzzy(DIRECTIONS)})"
		)
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is not None:
			matchDict: dict[str, str] = match.groupdict()
			direction: str = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
			if direction not in self.currentRoom.exits:
				return f"Exit {direction} does not exist."
			elif not matchDict["mode"]:
				return (
					f"Door flags '{direction}' set to '{', '.join(self.currentRoom.exits[direction].doorFlags)}'."
				)
			elif "remove".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.exits[direction].doorFlags:
					self.currentRoom.exits[direction].doorFlags.remove(matchDict["flag"])
					return f"Door flag '{matchDict['flag']}' in direction '{direction}' removed."
				else:
					return f"Door flag '{matchDict['flag']}' in direction '{direction}' not set."
			elif "add".startswith(matchDict["mode"]):
				if matchDict["flag"] in self.currentRoom.exits[direction].doorFlags:
					return f"Door flag '{matchDict['flag']}' in direction '{direction}' already set."
				else:
					self.currentRoom.exits[direction].doorFlags.add(matchDict["flag"])
					return f"Door flag '{matchDict['flag']}' in direction '{direction}' added."
		return (
			f"Syntax: 'doorflags [add | remove] [{' | '.join(VALID_DOOR_FLAGS)}] "
			+ f"[{' | '.join(DIRECTIONS)}]'."
		)

	def secret(self, text: str = "") -> str:
		text = text.strip().lower()
		matchPattern: str = (
			rf"^((?P<mode>{regexFuzzy('add')}|{regexFuzzy('remove')})\s+)?"
			+ rf"((?P<name>[A-Za-z]+)\s+)?(?P<direction>{regexFuzzy(DIRECTIONS)})"
		)
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is not None:
			matchDict: dict[str, str] = match.groupdict()
			direction: str = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
			if matchDict["mode"] and "add".startswith(matchDict["mode"]):
				if not matchDict["name"]:
					return "Error: 'add' expects a name for the secret."
				elif direction not in self.currentRoom.exits:
					self.currentRoom.exits[direction] = self.getNewExit(direction)
				self.currentRoom.exits[direction].exitFlags.add("door")
				self.currentRoom.exits[direction].doorFlags.add("hidden")
				self.currentRoom.exits[direction].door = matchDict["name"]
				self.GUIRefresh()
				return f"Adding secret '{matchDict['name']}' to direction '{direction}'."
			elif direction not in self.currentRoom.exits:
				return f"Exit {direction} does not exist."
			elif not self.currentRoom.exits[direction].door:
				return f"No secret {direction} of here."
			elif not matchDict["mode"]:
				return f"Exit '{direction}' has secret '{self.currentRoom.exits[direction].door}'."
			elif "remove".startswith(matchDict["mode"]):
				if "hidden" in self.currentRoom.exits[direction].doorFlags:
					self.currentRoom.exits[direction].doorFlags.remove("hidden")
				self.currentRoom.exits[direction].door = ""
				self.GUIRefresh()
				return f"Secret {direction} removed."
		return f"Syntax: 'secret [add | remove] [name] [{' | '.join(DIRECTIONS)}]'."

	def rlink(self, text: str = "") -> str:
		text = text.strip().lower()
		matchPattern: str = (
			rf"^((?P<mode>{regexFuzzy('add')}|{regexFuzzy('remove')})\s+)?"
			+ rf"((?P<oneway>{regexFuzzy('oneway')})\s+)?"
			+ r"((?P<vnum>\d+|undefined)\s+)?"
			+ rf"(?P<direction>{regexFuzzy(DIRECTIONS)})"
		)
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is not None:
			matchDict: dict[str, str] = match.groupdict()
			direction: str = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
			if matchDict["mode"] and "add".startswith(matchDict["mode"]):
				reversedDirection: str = REVERSE_DIRECTIONS[direction]
				if not matchDict["vnum"]:
					return "Error: 'add' expects a vnum or 'undefined'."
				elif matchDict["vnum"] != "undefined" and matchDict["vnum"] not in self.rooms:
					return f"Error: vnum {matchDict['vnum']} not in database."
				elif direction not in self.currentRoom.exits:
					self.currentRoom.exits[direction] = self.getNewExit(direction)
				self.currentRoom.exits[direction].to = matchDict["vnum"]
				if matchDict["vnum"] == "undefined":
					self.GUIRefresh()
					return f"Direction {direction} now undefined."
				elif not matchDict["oneway"]:
					if (
						reversedDirection not in self.rooms[matchDict["vnum"]].exits
						or self.rooms[matchDict["vnum"]].exits[reversedDirection].to == "undefined"
					):
						self.rooms[matchDict["vnum"]].exits[reversedDirection] = self.getNewExit(
							reversedDirection, self.currentRoom.vnum
						)
						self.GUIRefresh()
						return (
							f"Linking direction {direction} to {matchDict['vnum']} "
							+ f"with name '{self.rooms[matchDict['vnum']].name if matchDict['vnum'] in self.rooms else ''}'.\n"
							+ f"Linked exit {reversedDirection} in second room with this room."
						)
					else:
						self.GUIRefresh()
						return (
							f"Linking direction {direction} to {matchDict['vnum']} "
							+ f"with name '{self.rooms[matchDict['vnum']].name if matchDict['vnum'] in self.rooms else ''}'.\n"
							+ f"Unable to link exit {reversedDirection} in second room with this room: exit already defined."
						)
				else:
					self.GUIRefresh()
					return (
						f"Linking direction {direction} one way to {matchDict['vnum']} "
						+ f"with name '{self.rooms[matchDict['vnum']].name if matchDict['vnum'] in self.rooms else ''}'."
					)
			elif direction not in self.currentRoom.exits:
				return f"Exit {direction} does not exist."
			elif not matchDict["mode"]:
				toName: str
				if self.currentRoom.exits[direction].to in self.rooms:
					toName = self.rooms[self.currentRoom.exits[direction].to].name
				else:
					toName = ""
				return (
					f"Exit '{direction}' links to '{self.currentRoom.exits[direction].to}' with name '{toName}'."
				)
			elif "remove".startswith(matchDict["mode"]):
				del self.currentRoom.exits[direction]
				self.GUIRefresh()
				return f"Exit {direction} removed."
		return f"Syntax: 'rlink [add | remove] [oneway] [vnum] [{' | '.join(DIRECTIONS)}]'."

	def getlabel(self, text: str = "") -> str:
		text = text.strip().lower()
		findVnum: str = self.currentRoom.vnum if not text.isdigit() else text
		result: str = ", ".join(sorted(label for label, vnum in self.labels.items() if vnum == findVnum))
		if not result:
			return "Room not labeled."
		return f"Room labels: {result}"

	def rlabel(self, text: str = "") -> None:
		text = text.strip().lower()
		matchPattern: str = r"^(?P<action>add|delete|info|search)(?:\s+(?P<label>\S+))?(?:\s+(?P<vnum>\d+))?$"
		match: REGEX_MATCH = re.match(matchPattern, text)
		if match is None:
			self.output(
				"Syntax: 'rlabel [add|info|delete] [label] [vnum]'. Vnum is only used when adding a room. "
				+ "Leave it blank to use the current room's vnum. Use '_label info all' to get a list of all labels."
			)
			return None
		matchDict: dict[str, str] = match.groupdict()
		if not matchDict["label"]:
			self.output("Error: you need to supply a label.")
			return None
		elif matchDict["label"] == "schema_version":
			self.output("Error: 'schema_version' not allowed as label.")
			return None
		label: str = matchDict["label"]
		if label.isdecimal():
			self.output("labels cannot be decimal values.")
		elif matchDict["action"] == "add":
			vnum: str
			if not matchDict["vnum"]:
				vnum = self.currentRoom.vnum
				self.output(f"adding the label '{label}' to current room with VNum '{vnum}'.")
			else:
				vnum = matchDict["vnum"]
				self.output(f"adding the label '{label}' with VNum '{vnum}'.")
			self.labels[label] = vnum
			self.saveLabels()
		elif matchDict["action"] == "delete":
			if label not in self.labels:
				self.output(f"There aren't any labels matching '{label}' in the database.")
				return None
			self.output(f"Deleting label '{label}'.")
			del self.labels[label]
			self.saveLabels()
		elif matchDict["action"] == "info":
			if not self.labels:
				self.output("There aren't any labels in the database yet.")
			elif "all".startswith(label):
				self.output(
					"\n".join(f"{labelString} - {vnum}" for labelString, vnum in sorted(self.labels.items()))
				)
			elif label not in self.labels:
				self.output(f"There aren't any labels matching '{label}' in the database.")
			else:
				self.output(f"Label '{label}' points to room '{self.labels[label]}'.")
		elif matchDict["action"] == "search":
			results: list[str] = sorted(
				f"{name} - {self.rooms[vnum].name if vnum in self.rooms else 'VNum not in map'} - {vnum}"
				for name, vnum in self.labels.items()
				if label in name
			)
			if not results:
				self.output("Nothing found.")
			else:
				self.output("\n".join(results))

	def rinfo(self, text: str = "") -> str:
		text = text.strip().lower()
		vnum: str = self.currentRoom.vnum if not text else text
		if vnum in self.labels:
			vnum = self.labels[vnum]
		if vnum not in self.rooms:
			return f"Error: No such vnum or label, '{vnum}'"
		return self.rooms[vnum].info

	def createSpeedWalk(self, directionsList: MutableSequence[str]) -> str:
		"""Given a list of directions, return a string of the directions in standard speed walk format"""

		def compressDirections(directionsBuffer: Sequence[str]) -> list[str]:
			speedWalkDirs: list[str] = []
			for direction, group in itertools.groupby(directionsBuffer):
				lenGroup: int = len(list(group))
				if lenGroup == 1:
					speedWalkDirs.append(direction[0])
				else:
					speedWalkDirs.append(f"{lenGroup}{direction[0]}")
			return speedWalkDirs

		numDirections: int = len([d for d in directionsList if d in DIRECTIONS])
		result: list[str] = []
		directionsBuffer: list[str] = []
		while directionsList:
			item: str = directionsList.pop()
			if item in DIRECTIONS:
				directionsBuffer.append(item)
			else:
				# The item is not a direction, so process the directions buffer, clear the buffer,
				# and add the resulting list plus the item to the result.
				result.extend(compressDirections(directionsBuffer))
				directionsBuffer.clear()
				result.append(item)
		# Process any remaining items in the directions buffer.
		if directionsBuffer:
			result.extend(compressDirections(directionsBuffer))
		return f"{numDirections} rooms. {', '.join(result)}"

	def path(self, text: str = "") -> None:
		text = text.strip().lower()
		match: REGEX_MATCH = RUN_DESTINATION_REGEX.match(text)
		if match is None:
			self.output("Usage: path [label|vnum]")
			return None
		destination: str = match.group("destination")
		flags: str = match.group("flags")
		result: list[str] = self.pathFind(destination=destination, flags=flags.split("|") if flags else None)
		if result:
			self.output(self.createSpeedWalk(result))

	def pathFind(
		self,
		origin: Optional[Room] = None,
		destination: Optional[str] = None,
		flags: Optional[Sequence[str]] = None,
	) -> list[str]:
		"""Find the path"""
		if origin is None:
			if self.currentRoom.vnum == "-1":
				self.output("Error! The mapper has no location. Please use the sync command then try again.")
				return []
			origin = self.currentRoom
		destinationRoom: Union[Room, None] = self.getRoomFromLabel(str(destination))
		if destinationRoom is None:
			return []
		elif destinationRoom is origin:
			self.output("You are already there!")
			return []
		avoidTerrains: frozenset[str]
		if flags:
			avoidTerrains = frozenset(terrain for terrain in TERRAIN_COSTS if f"no{terrain}" in flags)
		else:
			avoidTerrains = frozenset()
		ignoreVnums: frozenset[str] = frozenset(("undefined", "death"))
		isDestinationFunc: Callable[[Room], bool] = lambda currentRoomObj: (  # NOQA: E731
			currentRoomObj is destinationRoom
		)
		exitIgnoreFunc: Callable[[Exit], bool] = lambda exitObj: exitObj.to in ignoreVnums  # NOQA: E731
		exitCostFunc: Callable[[Exit, Room], int] = lambda exitObj, neighborRoomObj: (  # NOQA: E731
			(5 if "door" in exitObj.exitFlags or "climb" in exitObj.exitFlags else 0)
			+ (1000 if "avoid" in exitObj.exitFlags else 0)
			+ (10 if neighborRoomObj.terrain in avoidTerrains else 0)
		)
		exitDestinationFunc: None = None
		return self._pathFind(origin, isDestinationFunc, exitIgnoreFunc, exitCostFunc, exitDestinationFunc)

	def _pathFind(
		self,
		origin: Room,
		isDestinationFunc: Optional[Callable[[Room], bool]] = None,
		exitIgnoreFunc: Optional[Callable[[Exit], bool]] = None,
		exitCostFunc: Optional[Callable[[Exit, Room], int]] = None,
		exitDestinationFunc: Optional[Callable[[Exit, Room], bool]] = None,
	) -> list[str]:
		# Each key-value pare that gets added to this dict will be a parent room and child room respectively.
		parents: dict[Room, tuple[Room, str]] = {origin: (origin, "")}
		# unprocessed rooms.
		opened: list[tuple[float, Room]] = []
		# Using a binary heap for storing unvisited rooms significantly increases performance.
		# https://en.wikipedia.org/wiki/Binary_heap
		heapq.heapify(opened)
		# Put the origin cost and origin room on the opened rooms heap to be processed first.
		heapq.heappush(opened, (origin.cost, origin))
		# previously processed rooms.
		closed: dict[Room, float] = {}
		# Ignore the origin from the search by adding it to the closed rooms dict.
		closed[origin] = origin.cost
		# Search while there are rooms left in the opened heap.
		currentRoomCost: float
		currentRoomObj: Room
		neighborRoomCost: float
		neighborRoomObj: Room
		direction: str
		while opened:
			# Pop the last room cost and room object reference off the opened heap for processing.
			currentRoomCost, currentRoomObj = heapq.heappop(opened)
			if isDestinationFunc and isDestinationFunc(currentRoomObj):
				# We successfully found a path from the origin to the destination.
				break
			# Loop through the exits, and process each room linked to the current room.
			for exitDirection, exitObj in currentRoomObj.exits.items():
				if exitIgnoreFunc and exitIgnoreFunc(exitObj):
					continue
				# Get a reference to the room object that the exit leads to using the room's vnum.
				neighborRoomObj = self.rooms[exitObj.to]
				# The neighbor room cost should be the sum of all movement costs
				# to get to the neighbor room from the origin room.
				neighborRoomCost = (
					currentRoomCost
					+ neighborRoomObj.cost
					+ (exitCostFunc(exitObj, neighborRoomObj) if exitCostFunc else 0)
				)
				# We're only interested in the neighbor room if it hasn't been encountered yet,
				# or if the cost of moving from the current room to the neighbor room is less than
				# the cost of moving to the neighbor room from a previously discovered room.
				if neighborRoomObj not in closed or closed[neighborRoomObj] > neighborRoomCost:
					# Add the room object and room cost to the dict of closed rooms,
					# and put it on the opened rooms heap to be processed.
					closed[neighborRoomObj] = neighborRoomCost
					heapq.heappush(opened, (neighborRoomCost, neighborRoomObj))
					# Since the current room is so far the most optimal way into the neighbor room,
					# set it as the parent of the neighbor room.
					parents[neighborRoomObj] = (currentRoomObj, exitDirection)
					if exitDestinationFunc and exitDestinationFunc(exitObj, neighborRoomObj):
						break
		else:
			# The while loop terminated normally (I.E. without encountering a break statement),
			# and the destination was *not* found.
			self.output("No routes found.")
			return []
		# The while statement was broken prematurely, meaning that the destination was found.
		# Find the path from the origin to the destination by traversing the hierarchy
		# of room parents, starting with the current room.
		results: list[str] = []
		while currentRoomObj is not origin:
			currentRoomObj, direction = parents[currentRoomObj]
			if (
				currentRoomObj.vnum in LEAD_BEFORE_ENTERING_VNUMS
				and currentRoomObj.exits[direction].to not in LEAD_BEFORE_ENTERING_VNUMS
				and currentRoomObj is not origin
			):
				results.append("ride")
			results.append(direction)
			if currentRoomObj.exits[direction].to in LEAD_BEFORE_ENTERING_VNUMS and (
				currentRoomObj.vnum not in LEAD_BEFORE_ENTERING_VNUMS or currentRoomObj is origin
			):
				results.append("lead")
			if "door" in currentRoomObj.exits[direction].exitFlags:
				results.append(
					f"open {currentRoomObj.exits[direction].door if currentRoomObj.exits[direction].door else 'exit'} "
					+ f"{direction}"
				)
		return results

	def getRoomFromLabel(self, text: str) -> Union[Room, None]:
		text = text.strip().lower()
		vnum: str
		if not text:
			self.output("No label or room vnum specified.")
		elif text.isdecimal():  # The text is a vnum.
			vnum = text
			if vnum in self.rooms:
				return self.rooms[vnum]
			self.output(f"No room with vnum {vnum}.")
		elif text in self.labels:  # The text is an existing label.
			vnum = self.labels[text]
			if vnum in self.rooms:
				return self.rooms[vnum]
			self.output(f"{text} is set to vnum {vnum}, but there is no room with that vnum")
		else:  # The text is *not* an existing label.
			similarLabels: list[str] = sorted(self.labels, key=lambda l: fuzz.ratio(l, text), reverse=True)
			self.output(f"Unknown label. Did you mean {', '.join(similarLabels[0:4])}?")
		return None

	def crawl(self, start: str, borders: Iterable[str]) -> tuple[str, ...]:
		explored: set[str] = set()
		unexplored: set[str] = set()
		unexplored.add(start)
		while unexplored:
			vnum = unexplored.pop()
			for _, exitObj in self.rooms[vnum].exits.items():
				if exitObj.to not in explored and exitObj.to not in borders and exitObj.to.isdigit():
					unexplored.add(exitObj.to)
			explored.add(vnum)
		return tuple(explored)

	def overlapping(self) -> tuple[tuple[COORDINATES_TYPE, tuple[str, ...]], ...]:
		results: dict[COORDINATES_TYPE, list[str]] = {}
		for vnum, room in self.rooms.items():
			results.setdefault(room.coordinates, []).append(vnum)
		return tuple((coordinates, tuple(vnums)) for coordinates, vnums in results.items() if len(vnums) > 1)
