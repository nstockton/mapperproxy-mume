# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import os.path
import re
from contextlib import suppress
from queue import Empty as QueueEmpty
from typing import TYPE_CHECKING, Any, Union

# Third-party Modules:
import pyglet

# Local Modules:
from ..roomdata.objects import Room
from ..typedef import GUI_QUEUE_TYPE
from ..utils import getDataPath


if TYPE_CHECKING:  # pragma: no cover
	# Prevent cyclic import.
	from ..world import World


FPS: int = 40
TILESDIR: str = getDataPath("tiles")

TILES: dict[str, Any] = {
	# terrain
	"field": pyglet.image.load(os.path.join(TILESDIR, "field.png")),
	"brush": pyglet.image.load(os.path.join(TILESDIR, "brush.png")),
	"forest": pyglet.image.load(os.path.join(TILESDIR, "forest.png")),
	"hills": pyglet.image.load(os.path.join(TILESDIR, "hill.png")),
	"mountains": pyglet.image.load(os.path.join(TILESDIR, "mountain.png")),
	"shallows": pyglet.image.load(os.path.join(TILESDIR, "swamp.png")),
	"water": pyglet.image.load(os.path.join(TILESDIR, "water.png")),
	"rapids": pyglet.image.load(os.path.join(TILESDIR, "rapid.png")),
	"underwater": pyglet.image.load(os.path.join(TILESDIR, "underwater.png")),
	"cavern": pyglet.image.load(os.path.join(TILESDIR, "cavern.png")),
	"tunnel": pyglet.image.load(os.path.join(TILESDIR, "tunnel.png")),
	"road": pyglet.image.load(os.path.join(TILESDIR, "road.png")),
	"city": pyglet.image.load(os.path.join(TILESDIR, "city.png")),
	"building": pyglet.image.load(os.path.join(TILESDIR, "indoor.png")),
	"random": pyglet.image.load(os.path.join(TILESDIR, "random.png")),
	"undefined": pyglet.image.load(os.path.join(TILESDIR, "undefined.png")),
	"deathtrap": pyglet.image.load(os.path.join(TILESDIR, "undefined.png")),
	# dark terrain
	"field-dark": pyglet.image.load(os.path.join(TILESDIR, "field-dark.png")),
	"brush-dark": pyglet.image.load(os.path.join(TILESDIR, "brush-dark.png")),
	"forest-dark": pyglet.image.load(os.path.join(TILESDIR, "forest-dark.png")),
	"hills-dark": pyglet.image.load(os.path.join(TILESDIR, "hill-dark.png")),
	"mountains-dark": pyglet.image.load(os.path.join(TILESDIR, "mountain-dark.png")),
	"shallows-dark": pyglet.image.load(os.path.join(TILESDIR, "swamp-dark.png")),
	"water-dark": pyglet.image.load(os.path.join(TILESDIR, "water-dark.png")),
	"rapids-dark": pyglet.image.load(os.path.join(TILESDIR, "rapid-dark.png")),
	"underwater-dark": pyglet.image.load(os.path.join(TILESDIR, "underwater-dark.png")),
	"cavern-dark": pyglet.image.load(os.path.join(TILESDIR, "cavern-dark.png")),
	"tunnel-dark": pyglet.image.load(os.path.join(TILESDIR, "tunnel-dark.png")),
	"road-dark": pyglet.image.load(os.path.join(TILESDIR, "road-dark.png")),
	"city-dark": pyglet.image.load(os.path.join(TILESDIR, "city-dark.png")),
	"building-dark": pyglet.image.load(os.path.join(TILESDIR, "indoor-dark.png")),
	"random-dark": pyglet.image.load(os.path.join(TILESDIR, "random-dark.png")),
	"undefined-dark": pyglet.image.load(os.path.join(TILESDIR, "undefined.png")),
	"deathtrap-dark": pyglet.image.load(os.path.join(TILESDIR, "undefined.png")),
	# exits
	"wallnorth": pyglet.image.load(os.path.join(TILESDIR, "wallnorth.png")),
	"walleast": pyglet.image.load(os.path.join(TILESDIR, "walleast.png")),
	"wallsouth": pyglet.image.load(os.path.join(TILESDIR, "wallsouth.png")),
	"wallwest": pyglet.image.load(os.path.join(TILESDIR, "wallwest.png")),
	"exitup": pyglet.image.load(os.path.join(TILESDIR, "exitup.png")),
	"exitdown": pyglet.image.load(os.path.join(TILESDIR, "exitdown.png")),
	# load flags
	"attention": pyglet.image.load(os.path.join(TILESDIR, "attention.png")),
	"armour": pyglet.image.load(os.path.join(TILESDIR, "armour.png")),
	"herb": pyglet.image.load(os.path.join(TILESDIR, "herb.png")),
	"key": pyglet.image.load(os.path.join(TILESDIR, "key.png")),
	"treasure": pyglet.image.load(os.path.join(TILESDIR, "treasure.png")),
	"weapon": pyglet.image.load(os.path.join(TILESDIR, "weapon.png")),
	# mob flags
	"guild": pyglet.image.load(os.path.join(TILESDIR, "guild.png")),
	"quest_mob": pyglet.image.load(os.path.join(TILESDIR, "quest.png")),
	"rent": pyglet.image.load(os.path.join(TILESDIR, "rent.png")),
	"shop": pyglet.image.load(os.path.join(TILESDIR, "shop.png")),
	"aggressive_mob": pyglet.image.load(os.path.join(TILESDIR, "smob.png")),
	# player
	"player": pyglet.image.load(os.path.join(TILESDIR, "player.png")),
}


pyglet.options["debug_gl"] = False
logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class Window(pyglet.window.Window):
	def __init__(self, world: World) -> None:
		# Mapperproxy world
		self.world: World = world
		# Map variables
		# Number of columns
		self.col: int = 9
		# Number of rows
		self.row: int = 23
		# The center of the window
		self.mcol: int = int(self.col / 2)
		self.mrow: int = int(self.row / 2)
		self.radius: tuple[int, int, int] = (self.mcol, self.mrow, 1)
		# The size of a tile in pixels
		self.square: int = 32
		# The list of visible rooms:
		# A dictionary using a tuple of coordinates (x, y) as keys
		self.visibleRooms: dict[tuple[int, int], Room] = {}
		# Player position and central rooms
		# They are set to None at startup.
		self.playerRoom: Union[Room, None] = None
		self.centerRoom: Union[Room, None] = None
		# Pyglet window
		super().__init__(self.col * self.square, self.row * self.square, caption="MPM", resizable=True)
		logger.info(f"Creating window {self}")
		self._gui_queue: GUI_QUEUE_TYPE = world._gui_queue
		# Sprites
		# The list of sprites
		self.sprites: list[pyglet.sprite.Sprite] = []
		# Pyglet batch of sprites
		self.batch = pyglet.graphics.Batch()
		# The list of visible layers (level 0 is covered by level 1)
		self.layer: list[pyglet.graphics.Group]
		self.layer = [pyglet.graphics.Group(order=i) for i in range(4)]
		# Define FPS
		pyglet.clock.schedule_interval_soft(self.queue_observer, 1.0 / FPS)

	def queue_observer(self, dt: float) -> None:
		while not self._gui_queue.empty():
			with suppress(QueueEmpty):
				event = self._gui_queue.get_nowait()
				if event is None:
					event = ("on_close",)
				self.dispatch_event(event[0], *event[1:])

	def on_close(self) -> None:
		logger.debug(f"Closing window {self}")
		super().on_close()

	def on_draw(self) -> None:
		logger.debug(f"Drawing window {self}")
		# pyglet stuff to clear the window
		self.clear()
		# pyglet stuff to print the batch of sprites
		self.batch.draw()

	def on_resize(self, width: int, height: int) -> None:
		logger.debug(f"Resizing window {self}")
		super().on_resize(width, height)
		# reset window size
		self.col = int(width / self.square)
		self.mcol = int(self.col / 2)
		self.row = int(height / self.square)
		self.mrow = int(self.row / 2)
		self.radius = (self.mcol, self.mrow, 1)
		if self.centerRoom is not None:
			self.draw_map(self.centerRoom)

	def on_mapSync(self, currentRoom: Room) -> None:
		logger.debug(f"Map synced to {currentRoom}, vnum {currentRoom.vnum}")
		# reset player position, center the map around
		self.playerRoom = currentRoom
		self.draw_map(currentRoom)

	def on_guiRefresh(self) -> None:
		"""This event is fired when the mapper needs to signal the GUI to clear
		the visible rooms cache and redraw the map view."""
		if self.centerRoom is not None:
			self.draw_map(self.centerRoom)
			logger.debug("GUI refreshed.")
		else:
			logger.debug("Unable to refresh the GUI. The center room is not defined.")

	def draw_map(self, centerRoom: Room) -> None:
		logger.debug(f"Drawing rooms around {centerRoom}")
		# reset the recorded state of the window
		self.sprites.clear()
		self.visibleRooms.clear()
		self.centerRoom = centerRoom
		# draw the rooms, beginning by the central one
		self.draw_room(self.mcol, self.mrow, centerRoom)
		_vnum: str
		room: Room
		x: int
		y: int
		z: int
		with self.world.roomsLock:
			for _vnum, room, x, y, z in self.world.getNeighborsFromRoom(start=centerRoom, radius=self.radius):
				if z == 0:
					self.draw_room(self.mcol + x, self.mrow + y, room)
		self.draw_player()

	def draw_room(self, x: int, y: int, room: Room) -> None:
		logger.debug(f"Drawing room: {x} {y} {room}")
		self.visibleRooms[x, y] = room
		# draw the terrain on layer 0
		if room.light == "dark":
			self.draw_tile(x, y, 0, room.terrain + "-dark")
		else:
			self.draw_tile(x, y, 0, room.terrain)
		# draw the walls on layer 1
		direction: str
		for direction in ("north", "east", "south", "west"):
			if direction not in room.exits:
				self.draw_tile(x, y, 1, "wall" + direction)
		# draw the arrows for exits up and down on layer 1
		for direction in ("up", "down"):
			if direction in room.exits:
				self.draw_tile(x, y, 1, "exit" + direction)
		# draw a single load flag on layer 2
		flag: str
		for flag in room.loadFlags:
			if flag in ("attention", "treasure", "key", "armour", "weapon", "herb"):
				self.draw_tile(x, y, 2, flag)
				break
		# draw a single mob flag on layer 2
		for flag in room.mobFlags:
			if flag in ("aggressive_mob", "rent", "quest_mob"):
				self.draw_tile(x, y, 2, flag)
				break
			if re.search("shop", flag) is not None:
				self.draw_tile(x, y, 2, "shop")
				break
			if re.search("guild", flag) is not None:
				self.draw_tile(x, y, 2, "guild")
				break

	def draw_player(self) -> None:
		if self.playerRoom is None or self.centerRoom is None:
			return
		logger.debug(f"Drawing player on room vnum {self.playerRoom.vnum}")
		# transform map coordinates to window ones
		x: int = self.playerRoom.x - self.centerRoom.x + self.mcol
		y: int = self.playerRoom.y - self.centerRoom.y + self.mrow
		z: int = self.playerRoom.z - self.centerRoom.z
		# Be sure the player coordinates are part of the window
		if z == 0 and x >= 0 and x < self.col and y >= 0 and y < self.row:
			# draw the player on layer 3
			self.draw_tile(x, y, 3, "player")

	def draw_tile(self, x: int, y: int, z: int, tile: str) -> None:
		logger.debug(f"Drawing tile: {x} {y} {tile}")
		# pyglet stuff to add a sprite to the batch
		sprite = pyglet.sprite.Sprite(TILES[tile], batch=self.batch, group=self.layer[z])
		# adapt sprite coordinates
		sprite.x = x * self.square
		sprite.y = y * self.square
		# add the sprite to the list of visible sprites
		self.sprites.append(sprite)

	def on_mouse_press(self, wx: int, wy: int, buttons: int, modifiers: int) -> None:
		logger.debug(f"Mouse press on {wx} {wy}.")
		x: int = int(wx / self.square)
		y: int = int(wy / self.square)
		# check if the player clicked on a room
		# searching for the tuple of coordinates (x, y)
		try:
			room: Room = self.visibleRooms[x, y]
		except KeyError:
			return
		# Action depends on which button the player clicked
		if buttons == pyglet.window.mouse.LEFT:
			# center the map on the selected room
			self.draw_map(room)
		elif buttons == pyglet.window.mouse.MIDDLE:
			# center the map on the player
			if self.playerRoom is not None:
				self.draw_map(self.playerRoom)
			else:
				logger.debug("Unable to center the map on the player. The player room is not defined.")
		elif buttons == pyglet.window.mouse.RIGHT:
			# print the vnum
			self.world.output(f"Click on room {room.vnum}.")


Window.register_event_type("on_mapSync")
Window.register_event_type("on_guiRefresh")
