# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re
from typing import Dict, List, Pattern, Set, Tuple, Union

# Local Modules:
from ..gui.vec2d import Vec2d


DIRECTIONS: Tuple[str, ...] = (
	"north",
	"east",
	"south",
	"west",
	"up",
	"down",
)
REVERSE_DIRECTIONS: Dict[str, str] = {
	"north": "south",
	"south": "north",
	"east": "west",
	"west": "east",
	"up": "down",
	"down": "up",
}
DIRECTION_COORDINATES: Dict[str, Tuple[int, ...]] = {
	"north": (0, 1, 0),
	"south": (0, -1, 0),
	"west": (-1, 0, 0),
	"east": (1, 0, 0),
	"up": (0, 0, 1),
	"down": (0, 0, -1),
}
COMPASS_DIRECTIONS: Tuple[str, ...] = (
	"north",
	"northeast",
	"east",
	"southeast",
	"south",
	"southwest",
	"west",
	"northwest",
)
AVOID_DYNAMIC_DESC_REGEX: Pattern[str] = re.compile(
	r"Some roots lie here waiting to ensnare weary travellers\.|"
	r"The remains of a clump of roots lie here in a heap of rotting compost\.|"
	r"A clump of roots is here, fighting|"
	r"Some withered twisted roots writhe towards you\.|"
	r"Black roots shift uneasily all around you\.|"
	r"black tangle of roots|"
	r"Massive roots shift uneasily all around you\.|"
	r"rattlesnake"
)
TERRAIN_COSTS: Dict[str, float] = {
	"cavern": 0.75,
	"city": 0.75,
	"indoors": 0.75,
	"tunnel": 0.75,
	"road": 0.85,
	"field": 1.5,
	"brush": 1.8,
	"forest": 2.15,
	"hills": 2.45,
	"shallow": 2.45,
	"mountains": 2.8,
	"undefined": 30.0,
	"water": 50.0,
	"rapids": 60.0,
	"underwater": 100.0,
	"deathtrap": 1000.0,
}
VALID_MOB_FLAGS: Tuple[str, ...] = (
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
)
VALID_LOAD_FLAGS: Tuple[str, ...] = (
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
VALID_EXIT_FLAGS: Tuple[str, ...] = (
	"exit",
	"door",
	"road",
	"climb",
	"random",
	"special",
	"avoid",
	"no_match",
	"flow",
	"no_flee",
	"damage",
	"fall",
	"guarded",
)
VALID_DOOR_FLAGS: Tuple[str, ...] = (
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


class Exit(object):
	"""
	An exit.
	"""

	def __init__(self) -> None:
		self.direction: Union[None, str] = None
		self.vnum: Union[None, str] = None
		self.to: str = "undefined"
		self.exitFlags: Set[str] = set(["exit"])
		self.door: str = ""
		self.doorFlags: Set[str] = set()


class Room(object):
	"""
	A room.
	"""

	def __init__(self) -> None:
		self.vnum: str = "-1"
		self.name: str = ""
		self.desc: str = ""
		self.dynamicDesc: str = ""
		self.note: str = ""
		self.terrain: str = "undefined"
		self.cost: float = TERRAIN_COSTS["undefined"]
		self.light: str = "undefined"
		self.align: str = "undefined"
		self.portable: str = "undefined"
		self.ridable: str = "undefined"
		self.avoid: bool = False
		self.mobFlags: Set[str] = set()
		self.loadFlags: Set[str] = set()
		self.x: int = 0
		self.y: int = 0
		self.z: int = 0
		self.exits: Dict[str, Exit] = {}

	def __lt__(self, other: Room) -> bool:
		# Unlike in Python 2 where most objects are sortable by default, our
		# Room class isn't automatically sortable in Python 3.
		# If we don't override this method, the path finder will throw an
		# exception in Python 3 because heapq.heappush requires that any object
		# passed to it be sortable.
		# We'll return False because we want heapq.heappush to sort the tuples
		# of movement cost and room object by the first item in the tuple (room cost),
		# and the order of rooms with the same movement cost is irrelevant.
		return False

	@property
	def sortedExits(self) -> List[Tuple[str, Exit]]:
		"""The room exits, sorted by direction."""
		return sorted(
			self.exits.items(),
			key=lambda item: (DIRECTIONS.index(item[0]) if item[0] in DIRECTIONS else len(DIRECTIONS)),
		)

	@property
	def info(self) -> str:
		"""A summery of the room info."""
		output = []
		output.append(f"vnum: '{self.vnum}'")
		output.append(f"Name: '{self.name}'")
		output.append("Description:")
		output.append("-" * 5)
		output.extend(self.desc.splitlines())
		output.append("-" * 5)
		output.append("Dynamic Desc:")
		output.append("-" * 5)
		output.extend(self.dynamicDesc.splitlines())
		output.append("-" * 5)
		output.append(f"Note: '{self.note}'")
		output.append(f"Terrain: '{self.terrain}'")
		output.append(f"Cost: '{self.cost}'")
		output.append(f"Light: '{self.light}'")
		output.append(f"Align: '{self.align}'")
		output.append(f"Portable: '{self.portable}'")
		output.append(f"Ridable: '{self.ridable}'")
		output.append(f"Mob Flags: '{', '.join(self.mobFlags)}'")
		output.append(f"Load Flags: '{', '.join(self.loadFlags)}'")
		output.append(f"Coordinates (X, Y, Z): '{self.x}', '{self.y}', '{self.z}'")
		output.append("Exits:")
		for direction, exitObj in self.sortedExits:
			output.append("-" * 5)
			output.append(f"Direction: '{direction}'")
			output.append(f"To: '{exitObj.to}'")
			output.append(f"Exit Flags: '{', '.join(exitObj.exitFlags)}'")
			output.append(f"Door Name: '{exitObj.door}'")
			output.append(f"Door Flags: '{', '.join(exitObj.doorFlags)}'")
		return "\n".join(output)

	def calculateCost(self) -> None:
		"""Calculates the movement cost for the room."""
		self.cost = TERRAIN_COSTS[self.terrain]
		if self.avoid or AVOID_DYNAMIC_DESC_REGEX.search(self.dynamicDesc):
			self.cost += 1000.0
		if self.ridable == "notridable":
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
		elif delta.get_length_sqrd() == 0:
			return "same X-Y"
		else:
			position = int(round((90 - delta.get_angle_degrees() + 360) % 360 / 30)) or 12
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
		elif delta.get_length_sqrd() == 0:
			return "same X-Y"
		else:
			return COMPASS_DIRECTIONS[round((90 - delta.get_angle_degrees() + 360) % 360 / 45) % 8]
