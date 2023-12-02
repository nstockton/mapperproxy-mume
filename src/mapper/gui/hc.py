# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import math
from collections.abc import Iterable, Sequence
from contextlib import suppress
from enum import Enum, auto
from queue import Empty as QueueEmpty
from typing import TYPE_CHECKING, Any, NamedTuple, Optional, Protocol, Union

# Third-party Modules:
import pyglet
from pyglet import shapes
from pyglet.window import key
from speechlight import Speech

# Local Modules:
from .vec2d import Vec2d
from ..config import Config
from ..roomdata.objects import DIRECTION_COORDINATES, DIRECTIONS, Exit, Room
from ..typedef import GUI_QUEUE_TYPE
from ..utils import clamp


if TYPE_CHECKING:
	# Prevent cyclic import.
	from ..world import World


FPS: int = 30
DEFAULT_ROOM_SIZE: int = 100  # Pixels.
DEFAULT_WALL_PERCENTAGE: int = 8  # Percentage of room size that will be used for a wall.
AGGRESSIVE_MOB_FLAGS: set[str] = {"aggressive_mob", "elite_mob", "super_mob"}
DIRECTIONS_2D: set[str] = set(DIRECTIONS[:-2])
DIRECTIONS_UD: set[str] = set(DIRECTIONS[-2:])
DIRECTION_COORDINATES_2D: dict[str, Vec2d] = {d: Vec2d(*DIRECTION_COORDINATES[d][:2]) for d in DIRECTIONS_2D}
KEYS: dict[tuple[int, int], str] = {
	(key.ESCAPE, 0): "resetZoom",
	(key.LEFT, 0): "adjustSize",
	(key.RIGHT, 0): "adjustSize",
	(key.F11, 0): "toggleExpandWindow",
	(key.F12, 0): "toggleAlwaysOnTop",
	(key.ENTER, key.MOD_ALT): "toggleFullscreen",
}
DEFAULT_TERRAIN_COLORS: dict[str, tuple[int, ...]] = {
	"brush": (127, 255, 0),
	"building": (186, 85, 211),
	"cavern": (153, 50, 204),
	"city": (190, 190, 190),
	"deathtrap": (255, 128, 0),
	"field": (124, 252, 0),
	"forest": (8, 128, 0),
	"hills": (139, 69, 19),
	"mountains": (165, 42, 42),
	"rapids": (32, 64, 192),
	"road": (255, 255, 255),
	"shallows": (218, 120, 245),
	"tunnel": (153, 50, 204),
	"undefined": (24, 16, 32),
	"underwater": (48, 8, 120),
	"water": (32, 64, 192),
}
DEFAULT_MISC_COLORS: dict[str, tuple[int, ...]] = {
	"highlight": (0, 0, 255),
	"mob_flags": (255, 234, 0),
	"mob_flags_border": (32, 64, 128),
	"up_down_bidirectional": (255, 228, 225),
	"up_down_bidirectional_border": (0, 0, 0),
	"up_down_death_border": (0, 0, 0),
	"up_down_undefined": (0, 0, 0),
	"up_down_undefined_border": (255, 255, 255),
}


pyglet.options["debug_gl"] = False
logger: logging.Logger = logging.getLogger(__name__)


class BatchType(Protocol):
	def draw(self) -> None:
		...


class ShapeType(Protocol):
	@property
	def position(self) -> tuple[float, float]:
		...

	@position.setter
	def position(self, values: Sequence[float]) -> None:
		...

	def delete(self) -> None:
		...


class GroupType(Protocol):
	def __init__(self, order: int = 0, parent: Optional[GroupType] = None) -> None:
		...


class Groups(Enum):
	"""
	The various group/layer levels.

	Values are ordered from lowest to highest priority, with higher priority displayed on top of lower.
	"""

	@staticmethod
	def _generate_next_value_(
		name: str, start: Union[int, None], count: int, last_values: list[GroupType]
	) -> GroupType:
		# Overriding this method so that auto() will return a Group instance.
		group: GroupType = pyglet.graphics.Group(order=count)
		return group

	DEFAULT = auto()
	PRIORITY_ROOM = auto()
	ROOM_FLAGS = auto()
	UP_DOWN = auto()
	CENTER_MARK = auto()


class Color(NamedTuple):
	"""The color of a shape."""

	r: int
	g: int
	b: int
	a: int = 255


class Window(pyglet.window.Window):  # type: ignore[misc, no-any-unimported]
	width: int
	height: int

	def __init__(self, world: World) -> None:
		self.world = world
		self._gui_queue: GUI_QUEUE_TYPE = world._gui_queue
		self._speech = Speech()
		self.say = self._speech.say
		self._cfg: dict[str, Any] = {}
		cfg = Config()
		if "gui" in cfg:
			self._cfg.update(cfg["gui"])
		else:
			cfg["gui"] = {}
			cfg.save()
		del cfg
		terrainColors: dict[str, tuple[int, ...]] = {}
		terrainColors.update(DEFAULT_TERRAIN_COLORS)
		terrainColors.update(self._cfg.get("terrain_colors", {}))
		self.terrainColors: dict[str, Color] = {k: Color(*v) for k, v in terrainColors.items()}
		miscColors: dict[str, tuple[int, ...]] = {}
		miscColors.update(DEFAULT_MISC_COLORS)
		miscColors.update(self._cfg.get("misc_colors", {}))
		self.miscColors: dict[str, Color] = {k: Color(*v) for k, v in miscColors.items()}
		self.batch: BatchType = pyglet.graphics.Batch()
		self.visibleRooms: dict[str, tuple[ShapeType, Room, Vec2d]] = {}
		self.visibleRoomFlags: dict[str, tuple[ShapeType, ...]] = {}
		self.visibleExits: dict[str, tuple[ShapeType, ...]] = {}
		self.centerMark: list[ShapeType] = []
		self.highlight: Union[str, None] = None
		self.currentRoom: Union[Room, None] = None
		super().__init__(caption="MPM", resizable=True, vsync=False)
		self._originalLocation: tuple[int, int] = self.get_location()
		self._originalSize: tuple[int, int] = self.get_size()
		if self.expandWindow:
			self.expandWindow = self.expandWindow  # Triggers resize.
		# Set style manually after the window is created.
		# Prevents lag if expand window and always on top are both enabled.
		if self.alwaysOnTop:
			self.alwaysOnTop = self.alwaysOnTop  # Apply the setting.
		# Only set full screen after the call to the parent constructor above.
		# This is done so we have a chance to store the original screen location and
		# size, as full screen mode would otherwise change the values.
		fullscreen: bool = self._cfg.get("fullscreen", False)
		if fullscreen:
			self.set_fullscreen(fullscreen)
		logger.info(f"Created window {self}")
		pyglet.clock.schedule_interval_soft(self.guiQueueDispatcher, 1.0 / FPS)  # Called once every frame.

	@property
	def alwaysOnTop(self) -> bool:
		"""Specify if window should be on top of other windows."""
		return self._cfg.get("always_on_top", False)

	@alwaysOnTop.setter
	def alwaysOnTop(self, value: bool) -> None:
		if value:
			self._style = pyglet.window.Window.WINDOW_STYLE_OVERLAY
		else:
			self._style = pyglet.window.Window.WINDOW_STYLE_DEFAULT
		self._cfg["always_on_top"] = value
		self._recreate(["style"])

	@property
	def expandWindow(self) -> bool:
		"""Specify if window size should be expanded to fit the screen."""
		return self._cfg.get("expand_window", False)

	@expandWindow.setter
	def expandWindow(self, value: bool) -> None:
		if self.fullscreen:
			return None
		alwaysOnTop = self.alwaysOnTop
		if alwaysOnTop:
			# Temporarily switch to default window style to prevent full screen bug.
			self.alwaysOnTop = False
		if value:
			self.set_location(0, 0)
			self.set_size(self.screen.width, self.screen.height)
		else:
			self.set_location(*self._originalLocation)
			self.set_size(*self._originalSize)
		if alwaysOnTop:
			# Undo Temporary change.
			self.alwaysOnTop = True
		self._cfg["expand_window"] = value

	@property
	def roomSize(self) -> int:
		"""The size of a drawn room in pixels."""
		try:
			roomSize = self._cfg["room_size"]
			if not 20 <= roomSize <= 300:
				clampedSize: int = int(clamp(roomSize, 20, 300))
				logger.warn(
					"Invalid value for room_size in config.json: "
					+ f"{roomSize} not in range 20-300. Clamping to {clampedSize}."
				)
				self._cfg["room_size"] = roomSize = clampedSize
		except KeyError:
			logger.debug(
				f"Undefined value for room_size in config.json: using default value {DEFAULT_ROOM_SIZE}."
			)
			self._cfg["room_size"] = roomSize = DEFAULT_ROOM_SIZE
		return int(roomSize)

	@roomSize.setter
	def roomSize(self, value: int) -> None:
		self._cfg["room_size"] = int(clamp(value, 20, 300))

	@property
	def roomScale(self) -> float:
		"""The scale of a drawn room."""
		return self.roomSize / 100.0

	@property
	def wallSize(self) -> int:
		"""The size of a wall in pixels."""
		return int(self.roomSize * DEFAULT_WALL_PERCENTAGE / 100)

	@property
	def walledRoomSize(self) -> int:
		"""The size of a room in pixels, after subtracting the size of a wall from both sides."""
		roomSize: int = self.roomSize
		wallSize: int = int(roomSize * DEFAULT_WALL_PERCENTAGE / 100)
		return roomSize - wallSize * 2

	@property
	def cp(self) -> Vec2d:
		"""A vector of the center point in pixels."""
		return Vec2d(self.width / 2.0, self.height / 2.0)

	@property
	def roomDrawRadius(self) -> tuple[int, int, int]:
		"""The radius in room coordinates, used when searching for neighboring rooms."""
		roomSize: int = self.roomSize
		return (
			int(math.ceil(self.width / roomSize / 2)),
			int(math.ceil(self.height / roomSize / 2)),
			1,
		)

	def roomBottomLeft(self, cp: Vec2d) -> Vec2d:
		"""
		Retrieves the bottom left coordinates from a room's center point.

		Args:
			cp: The center point vector.

		Returns:
			A vector containing the bottom left coordinates.
		"""
		width = height = self.roomSize
		return cp - (width / 2.0, height / 2.0)

	def roomTopLeft(self, cp: Vec2d) -> Vec2d:
		"""
		Retrieves the top left coordinates from a room's center point.

		Args:
			cp: The center point vector.

		Returns:
			A vector containing the top left coordinates.
		"""
		width = height = self.roomSize
		return cp - (width / 2.0, -height / 2.0)

	def roomTopRight(self, cp: Vec2d) -> Vec2d:
		"""
		Retrieves the top right coordinates from a room's center point.

		Args:
			cp: The center point vector.

		Returns:
			A vector containing the top right coordinates.
		"""
		width = height = self.roomSize
		return cp + (width / 2.0, height / 2.0)

	def roomBottomRight(self, cp: Vec2d) -> Vec2d:
		"""
		Retrieves the bottom right coordinates from a room's center point.

		Args:
			cp: The center point vector.

		Returns:
			A vector containing the bottom right coordinates.
		"""
		width = height = self.roomSize
		return cp + (width / 2.0, -height / 2.0)

	def roomOffsetFromPixels(self, x: float, y: float, z: Optional[float] = None) -> tuple[int, int]:
		"""
		Given coordinates in pixels, return the offset in room coordinates from the center room.

		Args:
			x: The X coordinate in pixels.
			y: The Y coordinate in pixels.
			z: The Z coordinate in pixels (unused).

		Returns:
			The 2-dimensional offset.
		"""
		roomSize: int = self.roomSize
		cp: Vec2d = self.cp
		return (
			int((x - cp.x + roomSize / 2) // roomSize),
			int((y - cp.y + roomSize / 2) // roomSize),
		)

	def equilateralTriangle(self, cp: Vec2d, radius: float, angle: float) -> tuple[Vec2d, Vec2d, Vec2d]:
		"""
		Calculates the coordinates for the corners of an equilateral triangle.

		Args:
			cp: The center point of the triangle.
			radius: The radius of the triangle.
			angle: The angle of the triangle.

		Returns:
			The 3 corners of an equilateral triangle.
		"""
		vec = Vec2d(radius, 0)
		point1 = vec.rotated_degrees(angle)
		point2 = point1.rotated_degrees(120)
		point3 = point2.rotated_degrees(120)
		return point1 + cp, point2 + cp, point3 + cp

	def drawBorderedTriangle(
		self,
		cp: Vec2d,
		radius: float,
		innerRadiusRatio: float,
		angle: float,
		*,
		color: Optional[Color] = None,
		borderColor: Optional[Color] = None,
		batch: Optional[BatchType] = None,
		group: Optional[GroupType] = None,
	) -> tuple[ShapeType, ShapeType]:
		"""
		Draws a triangle with a border around it.

		This is accomplished by drawing an inner triangle within a larger border triangle.

		Args:
			cp: The center point of both triangles.
			radius: The radius of the inner triangle.
			innerRadiusRatio:
				The ratio of the inner triangle radius, compared to the border triangle radius.
			angle: The angle of both triangles.
			color:
				The color of the inner triangle.
				If not provided, white will be used.
			borderColor:
				The color of the border triangle.
				If not provided, black will be used.
			batch:
				The batch to add the shapes to.
				If not provided, self.batch will be used.
			group:
				The group (I.E. layer) where the shapes will appear.
				If not provided, the bottom-most group will be used.

		Returns:
			A tuple containing the border triangle and inner triangle.
		"""
		if color is None:
			color = Color(255, 255, 255)  # White.
		if borderColor is None:
			borderColor = Color(0, 0, 0)  # Black.
		if batch is None:
			batch = self.batch
		if group is None:
			group = Groups.DEFAULT.value
		border1, border2, border3 = self.equilateralTriangle(cp, radius, angle)
		inner1, inner2, inner3 = self.equilateralTriangle(cp, radius * innerRadiusRatio, angle)
		borderTriangle = shapes.Triangle(
			*border1, *border2, *border3, color=borderColor, batch=batch, group=group
		)
		innerTriangle = shapes.Triangle(*inner1, *inner2, *inner3, color=color, batch=batch, group=group)
		return borderTriangle, innerTriangle

	def drawBorderedStar(
		self,
		cp: Vec2d,
		radius: float,
		innerRadiusRatio: float,
		*,
		numSpikes: Optional[float] = None,
		rotation: Optional[float] = None,
		color: Optional[Color] = None,
		borderColor: Optional[Color] = None,
		batch: Optional[BatchType] = None,
		group: Optional[GroupType] = None,
	) -> tuple[ShapeType, ShapeType]:
		"""
		Draws a star with a border around it.

		This is accomplished by drawing an inner star within a larger border star.

		Args:
			cp: The center point of both stars.
			radius: The radius of the inner star.
			innerRadiusRatio:
				The ratio of the inner star radius, compared to the border star radius.
			numSpikes: The number of spikes the star should have.
			rotation: A number in degrees that the stars should be rotated.
			color:
				The color of the inner star.
				If not provided, white will be used.
			borderColor:
				The color of the border star.
				If not provided, black will be used.
			batch:
				The batch to add the shapes to.
				If not provided, self.batch will be used.
			group:
				The group (I.E. layer) where the shapes will appear.
				If not provided, the bottom-most group will be used.

		Returns:
			A tuple containing the border star and inner star.
		"""
		if numSpikes is None:
			numSpikes = 5
		if rotation is None:
			rotation = 0
		if color is None:
			color = Color(255, 255, 255)  # White.
		if borderColor is None:
			borderColor = Color(0, 0, 0)  # Black.
		if batch is None:
			batch = self.batch
		if group is None:
			group = Groups.DEFAULT.value
		borderStar = shapes.Star(
			*cp,
			outer_radius=radius,
			inner_radius=radius * innerRadiusRatio,
			num_spikes=numSpikes,
			rotation=rotation,
			color=borderColor,
			batch=batch,
			group=group,
		)
		innerStar = shapes.Star(
			*cp,
			outer_radius=radius / 2,
			inner_radius=radius / 2 * innerRadiusRatio,
			num_spikes=numSpikes,
			rotation=rotation,
			color=color,
			batch=batch,
			group=group,
		)
		return borderStar, innerStar

	def drawBorderedCircle(
		self,
		cp: Vec2d,
		radius: float,
		innerRadiusRatio: float,
		*,
		color: Optional[Color] = None,
		borderColor: Optional[Color] = None,
		batch: Optional[BatchType] = None,
		group: Optional[GroupType] = None,
	) -> tuple[ShapeType, ShapeType]:
		"""
		Draws a circle with a border around it.

		This is accomplished by drawing an inner circle within a larger border circle.

		Args:
			cp: The center point of both circles.
			radius: The radius of the inner circle.
			innerRadiusRatio:
				The ratio of the inner circle radius, compared to the border circle radius.
			color:
				The color of the inner circle.
				If not provided, white will be used.
			borderColor:
				The color of the border circle.
				If not provided, black will be used.
			batch:
				The batch to add the shapes to.
				If not provided, self.batch will be used.
			group:
				The group (I.E. layer) where the shapes will appear.
				If not provided, the bottom-most group will be used.

		Returns:
			A tuple containing the border circle and inner circle.
		"""
		if color is None:
			color = Color(255, 255, 255)  # White.
		if borderColor is None:
			borderColor = Color(0, 0, 0)  # Black.
		if batch is None:
			batch = self.batch
		if group is None:
			group = Groups.DEFAULT.value
		borderCircle = shapes.Circle(*cp, radius, color=borderColor, batch=batch, group=group)
		innerCircle = shapes.Circle(*cp, radius * innerRadiusRatio, color=color, batch=batch, group=group)
		return borderCircle, innerCircle

	def message(self, text: str) -> None:
		"""
		Outputs a message to Speech Light and the world.

		Args:
			text: The text to output.
		"""
		self.say(text)
		self.world.output(text)

	def keyboard_toggleExpandWindow(self, symbol: int, modifiers: int) -> None:
		"""
		Toggles expanding the window to screen size.

		Args:
			symbol: The key symbol pressed.
			modifiers: Bitwise combination of the key modifiers active.
		"""
		if self.fullscreen:
			self.say("Can't change window size while in full screen.", True)
			return None
		value = not self.expandWindow
		self.expandWindow = value
		self.say(f"Window {'expanded' if value else 'restored'}.", True)

	def keyboard_toggleAlwaysOnTop(self, symbol: int, modifiers: int) -> None:
		"""
		Toggles window always being on top of other windows.

		Args:
			symbol: The key symbol pressed.
			modifiers: Bitwise combination of the key modifiers active.
		"""
		value = not self.alwaysOnTop
		self.alwaysOnTop = value
		self.say(f"Always on top {'enabled' if value else 'disabled'}.", True)

	def keyboard_toggleFullscreen(self, symbol: int, modifiers: int) -> None:
		"""
		Toggles full screen mode.

		Args:
			symbol: The key symbol pressed.
			modifiers: Bitwise combination of the key modifiers active.
		"""
		value = not self.fullscreen
		self.set_fullscreen(value)
		self._cfg["fullscreen"] = value
		self.say(f"fullscreen {'enabled' if value else 'disabled'}.", True)

	def keyboard_adjustSize(self, symbol: int, modifiers: int) -> None:
		"""
		Adjusts the size of visible shapes, effectively zooming the view in or out.

		Args:
			symbol: The key symbol pressed.
			modifiers: Bitwise combination of the key modifiers active.
		"""
		if symbol == key.LEFT:
			self.roomSize -= 10
		elif symbol == key.RIGHT:
			self.roomSize += 10
		self.say(f"{self.roomSize}%", True)
		self.on_guiRefresh()

	def keyboard_resetZoom(self, symbol: int, modifiers: int) -> None:
		"""
		Sets the room size back to its default value, effectively resetting the zoom.

		Args:
			symbol: The key symbol pressed.
			modifiers: Bitwise combination of the key modifiers active.
		"""
		self.roomSize = DEFAULT_ROOM_SIZE
		self.on_guiRefresh()
		self.say("Reset zoom", True)

	def deleteStaleRooms(self, excludes: Optional[Iterable[str]] = None) -> None:
		"""
		Deletes stale room shapes which are no longer visible.

		Args:
			excludes: Room vnums to exclude from deletion.
		"""
		stale: set[str]
		if excludes is None:
			stale = set(self.visibleRooms)
		else:
			stale = set(self.visibleRooms).difference(excludes)
		with suppress(AssertionError):
			for vnum in stale:
				self.visibleRooms[vnum][0].delete()
				del self.visibleRooms[vnum]

	def deleteStaleRoomFlags(self, excludes: Optional[Iterable[str]] = None) -> None:
		"""
		Deletes stale room flag shapes which are no longer visible.

		Args:
			excludes: Room flag vnums to exclude from deletion.
		"""
		stale: set[str]
		if excludes is None:
			stale = set(self.visibleRoomFlags)
		else:
			stale = set(self.visibleRoomFlags).difference(excludes)
		with suppress(AssertionError):
			for vnum in stale:
				for shape in self.visibleRoomFlags[vnum]:
					shape.delete()
				del self.visibleRoomFlags[vnum]

	def deleteStaleExits(self, excludes: Optional[Iterable[str]] = None) -> None:
		"""
		Deletes stale exit shapes which are no longer visible.

		Args:
			excludes: Exit names to exclude from deletion.
		"""
		stale: set[str]
		if excludes is None:
			stale = set(self.visibleExits)
		else:
			stale = set(self.visibleExits).difference(excludes)
		with suppress(AssertionError):
			for name in stale:
				for shape in self.visibleExits[name]:
					shape.delete()
				del self.visibleExits[name]

	def deleteCenterMark(self) -> None:
		"""Deletes the center mark."""
		with suppress(AssertionError):
			for shape in self.centerMark:
				shape.delete()
		self.centerMark.clear()

	def drawCenterMark(self) -> None:
		"""Marks the center of the screen with a white circle within a black border."""
		self.centerMark.extend(
			self.drawBorderedCircle(
				self.cp, self.walledRoomSize * 0.25, 1 / 3, group=Groups.CENTER_MARK.value
			)
		)

	def drawUpDownExit(self, direction: str, exitObj: Exit, name: str, cp: Vec2d) -> None:
		"""
		Draws an up or down exit.

		Args:
			direction: The direction of the exit.
			exitObj: The exit object.
			name: A unique name for referencing the associated shapes.
			cp: The center point of the room containing the exit.
		"""
		triangleSize = self.walledRoomSize / 3
		if direction == "up":
			# Triangle pointing up on top half of room square.
			triangleCP = cp + (0, triangleSize)
			angle = 90
		else:
			# Triangle pointing down on bottom half of room square.
			triangleCP = cp - (0, triangleSize)
			angle = -90
		radius = triangleSize / 2
		innerRadiusRatio = 1 / 3 * 2  # 2 thirds.
		if name not in self.visibleExits:
			if exitObj.to == "undefined":
				color = self.miscColors["up_down_undefined"]
				borderColor = self.miscColors["up_down_undefined_border"]
			elif exitObj.to == "death":
				color = self.terrainColors["deathtrap"]
				borderColor = self.miscColors["up_down_death_border"]
			else:
				color = self.miscColors["up_down_bidirectional"]
				borderColor = self.miscColors["up_down_bidirectional_border"]
			borderTriangle, innerTriangle = self.drawBorderedTriangle(
				triangleCP,
				radius,
				innerRadiusRatio,
				angle,
				color=color,
				borderColor=borderColor,
				group=Groups.UP_DOWN.value,
			)
			self.visibleExits[name] = (borderTriangle, innerTriangle)
		else:
			borderTriangle, innerTriangle = self.visibleExits[name]
			border1, border2, border3 = self.equilateralTriangle(triangleCP, radius, angle)
			inner1, inner2, inner3 = self.equilateralTriangle(triangleCP, radius * innerRadiusRatio, angle)
			borderTriangle.position = border1
			innerTriangle.position = inner1

	def drawDeathExit2d(self, direction: str, name: str, cp: Vec2d) -> None:
		"""
		Draws a deathtrap for a 2D exit.

		Args:
			direction: The direction of the deathtrap exit.
			name: A unique name for referencing the associated shape.
			cp: The center point of the room containing the exit.
		"""
		width = height = roomSize = self.roomSize
		bottomLeft = cp - (width / 2, height / 2)
		bottomLeft += DIRECTION_COORDINATES_2D[direction] * roomSize
		if name not in self.visibleExits:
			square = shapes.Rectangle(
				*bottomLeft,
				width,
				height,
				color=self.terrainColors["deathtrap"],
				batch=self.batch,
				group=Groups.PRIORITY_ROOM.value,
			)
			self.visibleExits[name] = (square,)
		else:
			square = self.visibleExits[name][0]
			square.position = bottomLeft

	def drawSpecialExits(self) -> None:
		"""
		Draws special exits.

		A special exit is one which requires new shapes be created to represent the exit in the map view.
		2D bidirectional exits are seamless and do not require any extra work.
		2D walls and 2D undefined/one-way exits are represented by trimming the dimensions of the room.
		"""
		logger.debug("Drawing special exits")
		visibleExits = set()
		for vnum, item in self.visibleRooms.items():
			square, room, cp = item
			for direction, exitObj in room.exits.items():
				name = vnum + direction
				if direction in DIRECTIONS_UD:
					self.drawUpDownExit(direction, exitObj, name, cp)
					visibleExits.add(name)
				elif exitObj.to == "death":
					self.drawDeathExit2d(direction, name, cp)
					visibleExits.add(name)
		self.deleteStaleExits(visibleExits)

	def drawRoomFlags(self, room: Room, cp: Vec2d) -> None:
		"""
		Draws shapes representing notable room flags.

		Args:
			room: A Room object.
			cp: The center point of the room.
		"""
		if room.vnum not in self.visibleRoomFlags:
			if AGGRESSIVE_MOB_FLAGS.intersection(room.mobFlags):
				borderStar, innerStar = self.drawBorderedStar(
					cp,
					self.walledRoomSize * 1 / 3 * 2,
					1 / 3,
					rotation=-90,  # A spike should be pointing up.
					color=self.miscColors["mob_flags"],
					borderColor=self.miscColors["mob_flags_border"],
					group=Groups.ROOM_FLAGS.value,
				)
				self.visibleRoomFlags[room.vnum] = (borderStar, innerStar)
		else:
			for shape in self.visibleRoomFlags[room.vnum]:
				shape.position = cp

	def drawRoom(self, room: Room, cp: Vec2d, group: Optional[GroupType] = None) -> None:
		"""
		Draws a room.

		Args:
			room: A Room object.
			cp: The center point of the room.
			group:
				The group (I.E. layer) where the square will appear.
				If not provided, the bottom-most group will be used.
		"""
		if group is None:
			group = Groups.DEFAULT.value
		if self.highlight is not None and self.highlight == room.vnum:
			color = self.miscColors["highlight"]
		elif room.avoid:
			color = self.terrainColors["deathtrap"]
		elif room.terrain not in self.terrainColors:
			color = self.terrainColors["undefined"]
		else:
			color = self.terrainColors[room.terrain]
		walls2d = DIRECTIONS_2D.difference(room.exits)
		for direction, exitObj in room.exits.items():
			if direction in DIRECTIONS_2D:
				if exitObj.to == "undefined" or not self.world.isBidirectional(exitObj):
					# Treat these as walls for the moment.
					walls2d.add(direction)
		width = height = self.roomSize
		wallSize = self.wallSize
		bottomLeft = cp - (width / 2, height / 2)
		if "north" in walls2d:
			height -= wallSize  # Trim size from top.
		if "east" in walls2d:
			width -= wallSize  # Trim size from right.
		if "south" in walls2d:
			bottomLeft += (0, wallSize)  # Trim size from bottom.
		if "west" in walls2d:
			bottomLeft += (wallSize, 0)  # Trim size from left.
		if room.vnum not in self.visibleRooms:
			square = shapes.Rectangle(*bottomLeft, width, height, color=color, batch=self.batch, group=group)
			self.visibleRooms[room.vnum] = (square, room, cp)
		else:
			square = self.visibleRooms[room.vnum][0]
			square.position = bottomLeft
			square.group = group
			self.visibleRooms[room.vnum] = (square, room, cp)

	def drawRooms(self) -> None:
		"""Draws all the visible rooms."""
		currentRoom = self.currentRoom
		if currentRoom is None:
			logger.error("Unable to draw rooms: Current room undefined.")
			return None
		logger.debug(f"Drawing rooms near {currentRoom}")
		roomSize = self.roomSize
		visibleRooms = {currentRoom.vnum}
		self.drawRoom(currentRoom, self.cp, group=Groups.PRIORITY_ROOM.value)
		self.drawRoomFlags(currentRoom, self.cp)
		neighbors = self.world.getNeighborsFromRoom(start=currentRoom, radius=self.roomDrawRadius)
		for vnum, room, x, y, z in neighbors:
			if z == 0:
				visibleRooms.add(vnum)
				cp = self.cp + Vec2d(x * roomSize, y * roomSize)  # In pixels.
				self.drawRoom(room, cp)
				self.drawRoomFlags(room, cp)
		self.deleteStaleRooms(visibleRooms)
		self.deleteStaleRoomFlags(visibleRooms)
		self.drawSpecialExits()

	def on_close(self) -> None:
		"""
		Triggers when the user attempted to close the window.

		This event can be triggered by clicking on the "X" control box in
		the window title bar, or by some other platform-dependent manner.

		The default handler sets `has_exit` to ``True``.  In pyglet 1.1, if
		`pyglet.app.event_loop` is being used, `close` is also called,
		closing the window immediately.
		"""
		logger.debug(f"Closing window {self}")
		cfg = Config()
		cfg["gui"].update(self._cfg)
		cfg.save()
		del cfg
		super().on_close()

	def on_draw(self) -> None:
		"""
		Triggers when the window contents should be redrawn.

		The `EventLoop` will dispatch this event when the `draw`
		method has been called. The window will already have the
		GL context, so there is no need to call `switch_to`. The window's
		`flip` method will be called immediately after this event,
		so your event handler should not.

		You should make no assumptions about the window contents when
		this event is triggered; a resize or expose event may have
		invalidated the framebuffer since the last time it was drawn.
		"""
		pyglet.gl.glClearColor(0, 0, 0, 1)  # Values in range 0.0-1.0.
		self.clear()
		self.batch.draw()

	def on_key_press(self, symbol: int, modifiers: int) -> None:
		"""
		Triggers when a key on the keyboard was pressed (and held down).

		Since pyglet 1.1 the default handler dispatches the `pyglet.window.Window.on_close`
		event if the ``ESC`` key is pressed.

		Args:
			symbol: The key symbol pressed.
			modifiers: Bitwise combination of the key modifiers active.
		"""
		logger.debug(f"Key press: symbol: {symbol}, modifiers: {modifiers}")
		key = (symbol, modifiers)
		if key in KEYS:
			funcName = "keyboard_" + KEYS[key]
			func = getattr(self, funcName, None)
			if func is None:
				logger.error(f"Invalid key assignment for key {key}. No such function {funcName}.")
			else:
				try:
					func(symbol, modifiers)
				except Exception:
					logger.exception(
						f"Error while executing function {funcName}: called from key press {key}."
					)

	def on_mouse_leave(self, x: int, y: int) -> None:
		"""
		Triggers when the mouse was moved outside the window.

		This event will not be triggered if the mouse is currently being
		dragged.  Note that the coordinates of the mouse pointer will be
		outside the window rectangle.

		Args:
			x: Distance in pixels from the left edge of the window.
			y: Distance in pixels from the bottom edge of the window.
		"""
		self.highlight = None
		self.on_guiRefresh()

	def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
		"""
		Triggers when the mouse was moved with no buttons held down.

		Args:
			x: Distance in pixels from the left edge of the window.
			y: Distance in pixels from the bottom edge of the window.
			dx: Relative X position from the previous mouse position.
			dy: Relative Y position from the previous mouse position.
		"""
		for vnum, item in self.visibleRooms.items():
			square, room, cp = item
			if self.roomOffsetFromPixels(*cp) == self.roomOffsetFromPixels(x, y):
				if vnum is None or vnum not in self.world.rooms:
					return None
				elif self.highlight == vnum:
					# Room already highlighted.
					return None
				self.highlight = vnum
				self.say(f"{room.name}, {vnum}", True)
				break
		else:
			self.highlight = None
		self.on_guiRefresh()

	def on_mouse_press(self, x: int, y: int, buttons: int, modifiers: int) -> None:
		"""
		Triggers when a mouse button was pressed (and held down).

		Args:
			x: Distance in pixels from the left edge of the window.
			y: Distance in pixels from the bottom edge of the window.
			button: The mouse button that was pressed.
			modifiers: Bitwise combination of any keyboard modifiers currently active.
		"""
		logger.debug(f"Mouse press on {x} {y}, buttons: {buttons}, modifiers: {modifiers}")
		if buttons == pyglet.window.mouse.MIDDLE:
			self.keyboard_resetZoom(key.ESCAPE, 0)
			return None
		# check if the player clicked on a room
		for vnum, item in self.visibleRooms.items():
			square, room, cp = item
			if self.roomOffsetFromPixels(*cp) == self.roomOffsetFromPixels(x, y):
				# Action depends on which button the player clicked
				if vnum is None or vnum not in self.world.rooms:
					return None
				elif buttons == pyglet.window.mouse.LEFT:
					if modifiers & key.MOD_SHIFT:
						# print the vnum
						self.world.output(f"{vnum}, {room.name}")
					else:
						self.world.path(vnum)
				elif buttons == pyglet.window.mouse.RIGHT:
					self.world.currentRoom = room
					self.world.output(f"Current room now set to '{room.name}' with vnum {vnum}")
				break

	def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
		"""
		Triggers when the mouse wheel was scrolled.

		Note that most mice have only a vertical scroll wheel, so
		`scroll_x` is usually 0.  An exception to this is the Apple Mighty
		Mouse, which has a mouse ball in place of the wheel which allows
		both `scroll_x` and `scroll_y` movement.

		Args:
			x: Distance in pixels from the left edge of the window.
			y: Distance in pixels from the bottom edge of the window.
			scroll_x: Amount of movement on the horizontal axis.
			scroll_y: Amount of movement on the vertical axis.
		"""
		if scroll_y > 0:
			self.keyboard_adjustSize(key.RIGHT, 0)
		elif scroll_y < 0:
			self.keyboard_adjustSize(key.LEFT, 0)

	def on_resize(self, width: int, height: int) -> None:
		"""
		Triggers when the window was resized.

		The window will have the GL context when this event is dispatched;
		there is no need to call `switch_to` in this handler.

		Args:
			width: The new width of the window, in pixels.
			height: The new height of the window, in pixels.
		"""
		logger.debug(f"resizing window to ({width}, {height})")
		super().on_resize(width, height)
		if self.currentRoom is not None:
			self.on_guiRefresh()

	def redraw(self) -> None:
		"""Redraws the map view."""
		logger.debug("Redrawing map view.")
		if not self.centerMark:
			self.drawCenterMark()
		with self.world.roomsLock:
			self.drawRooms()

	def on_guiRefresh(self) -> None:
		"""Fires when it is necessary to clear the visible rooms cache and redraw the map view."""
		logger.debug("Clearing visible exits.")
		self.deleteStaleExits()
		logger.debug("Clearing visible room flags.")
		self.deleteStaleRoomFlags()
		logger.debug("Clearing visible rooms.")
		self.deleteStaleRooms()
		logger.debug("Clearing center mark.")
		self.deleteCenterMark()
		self.redraw()
		logger.debug("GUI refreshed.")

	def on_mapSync(self, currentRoom: Room) -> None:
		"""
		Fires when `world.currentRoom` changes value.

		This typically happens if player's location was
		automatically synced, or set manually with the 'sync' command.

		Args:
			currentRoom: The updated value of `world.currentRoom`.
		"""
		self.currentRoom = currentRoom
		logger.debug(f"Map synced to {currentRoom}")
		self.redraw()

	def guiQueueDispatcher(self, dt: float) -> None:
		"""
		Dispatches events from the GUI queue on every new frame.

		Args:
			dt: The Time delta in seconds since the last clock tick.
		"""
		while not self._gui_queue.empty():
			with suppress(QueueEmpty):
				event = self._gui_queue.get_nowait()
				if event is None:
					event = ("on_close",)
				self.dispatch_event(event[0], *event[1:])


Window.register_event_type("on_mapSync")
Window.register_event_type("on_guiRefresh")
