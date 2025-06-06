# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Union

# Mapper Modules:
from mapper.gui.vec2d import Vec2d
from mapper.typedef import COORDINATES_TYPE, RePatternType


DIRECTIONS: tuple[str, ...] = (
	"north",
	"east",
	"south",
	"west",
	"up",
	"down",
)
REVERSE_DIRECTIONS: dict[str, str] = {
	"north": "south",
	"south": "north",
	"east": "west",
	"west": "east",
	"up": "down",
	"down": "up",
}
DIRECTION_COORDINATES: dict[str, COORDINATES_TYPE] = {
	"north": (0, 1, 0),
	"south": (0, -1, 0),
	"west": (-1, 0, 0),
	"east": (1, 0, 0),
	"up": (0, 0, 1),
	"down": (0, 0, -1),
}
COMPASS_DIRECTIONS: tuple[str, ...] = (
	"north",
	"northeast",
	"east",
	"southeast",
	"south",
	"southwest",
	"west",
	"northwest",
)
AVOID_DYNAMIC_DESC_REGEX: RePatternType = re.compile(
	r"Some roots lie here waiting to ensnare weary travellers\.|"
	+ r"The remains of a clump of roots lie here in a heap of rotting compost\.|"
	+ r"A clump of roots is here, fighting|"
	+ r"Some withered twisted roots writhe towards you\.|"
	+ r"Black roots shift uneasily all around you\.|"
	+ r"black tangle of roots|"
	+ r"Massive roots shift uneasily all around you\.|"
	+ r"rattlesnake"
)
TERRAIN_COSTS: dict[str, float] = {
	"cavern": 0.75,
	"city": 0.75,
	"building": 0.75,
	"tunnel": 0.75,
	"road": 0.85,
	"field": 1.5,
	"brush": 1.8,
	"forest": 2.15,
	"hills": 2.45,
	"shallows": 2.45,
	"mountains": 2.8,
	"undefined": 30.0,
	"water": 50.0,
	"rapids": 60.0,
	"underwater": 100.0,
	"deathtrap": 1000.0,
}
VALID_MOB_FLAGS: tuple[str, ...] = (
	"rent",
	"shop",
	"weapon_shop",
	"armour_shop",
	"food_shop",
	"pet_shop",
	"guild",
	"scout_guild",
	"mage_guild",
	"cleric_guild",
	"warrior_guild",
	"ranger_guild",
	"aggressive_mob",
	"quest_mob",
	"passive_mob",
	"elite_mob",
	"super_mob",
	"milkable",
	"rattlesnake",
)
VALID_LOAD_FLAGS: tuple[str, ...] = (
	"treasure",
	"armour",
	"weapon",
	"water",
	"food",
	"herb",
	"key",
	"mule",
	"horse",
	"pack_horse",
	"trained_horse",
	"rohirrim",
	"warg",
	"boat",
	"attention",
	"tower",  # Player can 'watch' surrounding rooms from this one.
	"clock",
	"mail",
	"stable",
	"white_word",
	"dark_word",
	"equipment",
	"coach",
	"ferry",
)
VALID_EXIT_FLAGS: tuple[str, ...] = (
	"avoid",
	"exit",
	"door",
	"road",
	"climb",
	"random",
	"special",
	"no_match",
	"flow",
	"no_flee",
	"damage",
	"fall",
	"guarded",
)
VALID_DOOR_FLAGS: tuple[str, ...] = (
	"hidden",
	"need_key",
	"no_block",
	"no_break",
	"no_pick",
	"delayed",
	"callable",
	"knockable",
	"magic",
	"action",  # Action controlled
	"no_bash",
)
DATACLASS_KWARGS: dict[str, bool] = {"eq": False}  # Use the default __hash__ method for speed.


if sys.version_info >= (3, 10):  # pragma: no cover
	# Python 3.10 and up adds a "slots" argument to automatically generate a __slots__ attribute.
	DATACLASS_KWARGS["slots"] = True


@dataclass(**DATACLASS_KWARGS)
class Exit:
	"""
	An exit.
	"""

	_direction: str = ""
	vnum: Union[str, None] = None
	to: str = "undefined"
	exitFlags: set[str] = field(default_factory=set)
	door: str = ""
	doorFlags: set[str] = field(default_factory=set)

	def __post_init__(self) -> None:
		"""Called after __init__."""
		self.exitFlags.add("exit")

	def __str__(self) -> str:
		return self._direction

	@property
	def direction(self) -> str:
		"""
		The direction of movement.

		Raises:
			ValueError: Direction undefined.
		"""
		if not self._direction:
			raise ValueError("Direction undefined.")
		return self._direction

	@direction.setter
	def direction(self, value: str) -> None:
		if value not in DIRECTIONS:
			raise ValueError(f"Direction must be one of {DIRECTIONS}.")
		self._direction = value


@dataclass(**DATACLASS_KWARGS)
class Room:
	"""
	A room.
	"""

	# Cost needs to be defined first for correct sorting.
	cost: float = field(init=False, repr=False, default=TERRAIN_COSTS["undefined"])
	vnum: str = "-1"
	serverID: str = "0"  # Server room IDs are in range 1-0x7fffffff.
	area: str = ""
	name: str = ""
	desc: str = ""
	dynamicDesc: str = ""
	note: str = ""
	terrain: str = "undefined"
	light: str = "undefined"
	align: str = "undefined"
	portable: str = "undefined"
	ridable: str = "undefined"
	sundeath: str = "undefined"
	avoid: bool = False
	mobFlags: set[str] = field(default_factory=set)
	loadFlags: set[str] = field(default_factory=set)
	x: int = 0
	y: int = 0
	z: int = 0
	exits: dict[str, Exit] = field(default_factory=dict)

	def __str__(self) -> str:
		return self.vnum

	def __lt__(self, other: Room) -> bool:
		# Unlike in Python 2 where most objects are sortable by default, our
		# Room class isn't automatically sortable in Python 3.
		# If we don't override this method, the path finder will throw an
		# exception in Python 3 because heapq.heappush requires that any object
		# passed to it be sortable.
		# We'll return False because we want heapq.heappush to sort the tuples
		# of movement cost and room object by the first item in the tuple (room cost),
		# and the order of rooms with the same movement cost is irrelevant.
		# Note that this is much faster than passing the 'order' keyword to the dataclass decorator.
		return False

	@property
	def coordinates(self) -> COORDINATES_TYPE:
		"""The room coordinates."""
		return (self.x, self.y, self.z)

	@coordinates.setter
	def coordinates(self, value: Sequence[int]) -> None:
		if len(value) != 3:
			raise ValueError("Expected sequence of length 3.")
		self.x, self.y, self.z = value

	@property
	def sortedExits(self) -> list[tuple[str, Exit]]:
		"""The room exits, sorted by direction."""
		return sorted(
			self.exits.items(),
			key=lambda item: (DIRECTIONS.index(item[0]) if item[0] in DIRECTIONS else len(DIRECTIONS)),
		)

	@property
	def info(self) -> str:
		"""A summery of the room info."""
		output: list[str] = [
			f"vnum: '{self.vnum}'",
			f"Name: '{self.name}'",
			f"Server ID: '{self.serverID}'",
			"Description:",
			"-" * 5,
			*self.desc.splitlines(),
			"-" * 5,
			"Dynamic Desc:",
			"-" * 5,
			*self.dynamicDesc.splitlines(),
			"-" * 5,
			f"Note: '{self.note}'",
			f"Area: '{self.area}'",
			f"Terrain: '{self.terrain}'",
			f"Cost: '{self.cost}'",
			f"Light: '{self.light}'",
			f"Align: '{self.align}'",
			f"Portable: '{self.portable}'",
			f"Ridable: '{self.ridable}'",
			f"Sundeath: '{self.sundeath}'",
			f"Mob Flags: '{', '.join(self.mobFlags)}'",
			f"Load Flags: '{', '.join(self.loadFlags)}'",
			f"Coordinates (X, Y, Z): '{self.coordinates}'",
			"Exits:",
		]
		for direction, exitObj in self.sortedExits:
			exits: list[str] = [
				"-" * 5,
				f"Direction: '{direction}'",
				f"To: '{exitObj.to}'",
				f"Exit Flags: '{', '.join(exitObj.exitFlags)}'",
				f"Door Name: '{exitObj.door}'",
				f"Door Flags: '{', '.join(exitObj.doorFlags)}'",
			]
			output.extend(exits)
		return "\n".join(output)

	def calculateCost(self) -> None:
		"""Calculates the movement cost for the room."""
		self.cost = TERRAIN_COSTS[self.terrain]
		if self.avoid or AVOID_DYNAMIC_DESC_REGEX.search(self.dynamicDesc):
			self.cost += 1000.0
		if self.ridable == "not_ridable":
			self.cost += 5.0

	def manhattanDistance(self, other: Room) -> int:
		"""
		Returns the Manhattan distance between this room and another.

		Note:
			https://en.wikipedia.org/wiki/Taxicab_geometry

		Args:
			other: The other room to calculate the Manhattan distance between.

		Returns:
			The Manhattan distance between this room and the other.
		"""
		return abs(other.x - self.x) + abs(other.y - self.y) + abs(other.z - self.z)

	def clockPositionTo(self, other: Room) -> str:
		"""
		Returns the clock position of another room from this one.

		Note:
			https://en.wikipedia.org/wiki/Clock_position

		Args:
			other: The other room to calculate the clock position of.

		Returns:
			The clock position of the other room, relative to this one.
		"""
		delta = Vec2d(other.x, other.y) - (self.x, self.y)
		if self.vnum == other.vnum:
			return "here"
		if delta.get_length_sqrd() == 0:
			return "same X-Y"
		position = round((90 - delta.angle_degrees + 360) % 360 / 30) or 12
		return f"{position} o'clock"

	def directionTo(self, other: Room) -> str:
		"""
		Returns the compass direction of another room from this one.

		Note:
			https://en.wikipedia.org/wiki/Points_of_the_compass

		Args:
			other: The other room to calculate the compass direction of.

		Returns:
			The compass direction of the other room, relative to this one.
		"""
		delta = Vec2d(other.x, other.y) - (self.x, self.y)
		if self.vnum == other.vnum:
			return "here"
		if delta.get_length_sqrd() == 0:
			return "same X-Y"
		return COMPASS_DIRECTIONS[round((90 - delta.angle_degrees + 360) % 360 / 45) % 8]

	def isOrphan(self) -> bool:
		"""
		Determines if room is an orphan, based on the existence of undefined exits.

		Returns:
			True if room contains no exits or only undefined exits, False otherwise.
		"""
		return all(exitObj.to == "undefined" for exitObj in self.exits.values())

	def hasUndefinedExits(self) -> bool:
		"""
		Determines if room contains one or more undefined exits.

		Returns:
			True if room contains at least one undefined exit, False otherwise.
		"""
		return any(exitObj.to == "undefined" for exitObj in self.exits.values())
