# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from ..constants import AVOID_DYNAMIC_DESC_REGEX, TERRAIN_COSTS


class Room(object):
	def __init__(self, vnum):
		self.vnum = vnum
		self.name = ""
		self.desc = ""
		self.dynamicDesc = ""
		self.note = ""
		self.terrain = "undefined"
		self.cost = TERRAIN_COSTS["undefined"]
		self.light = "undefined"
		self.align = "undefined"
		self.portable = "undefined"
		self.ridable = "undefined"
		self.avoid = False
		self.mobFlags = set()
		self.loadFlags = set()
		self.x = 0
		self.y = 0
		self.z = 0
		self.exits = {}

	def __lt__(self, other):
		# Unlike in Python 2 where most objects are sortable by default, our Room class isn't automatically sortable in Python 3.
		# If we don't override this method, the path finder will throw an exception in Python 3 because heapq.heappush requires that any object passed to it be sortable.
		# We'll return False because we want heapq.heappush to sort the tuples of movement cost and room object by the first item in the tuple (room cost), and the order of rooms with the same movement cost is irrelevant.
		return False

	def calculateCost(self):
		try:
			self.cost = TERRAIN_COSTS[self.terrain]
		except KeyError:
			self.cost = TERRAIN_COSTS["undefined"]
		if self.avoid or AVOID_DYNAMIC_DESC_REGEX.search(self.dynamicDesc):
			self.cost += 1000.0
		if self.ridable == "notridable":
			self.cost += 5.0

	def manhattanDistance(self, destination):
		return abs(destination.x - self.x) + abs(destination.y - self.y) + abs(destination.z - self.z)


class Exit(object):
	def __init__(self):
		self.direction = None
		self.vnum = None
		self.to = "undefined"
		self.exitFlags = set(["exit"])
		self.door = ""
		self.doorFlags = set()
