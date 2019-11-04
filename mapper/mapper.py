# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import re
import socket
import textwrap
import threading
import traceback
from contextlib import suppress
from queue import SimpleQueue
from timeit import default_timer
from typing import Any, Callable, Dict, List, Match, Optional, Pattern, Set, Tuple, Union

# Local Modules:
from . import EVENT_CALLER_TYPE, INTERFACES, OUTPUT_FORMATS
from .cleanmap import ExitsCleaner
from .clock import CLOCK_REGEX, DAWN_REGEX, DAY_REGEX, DUSK_REGEX, MONTHS, NIGHT_REGEX, TIME_REGEX, Clock
from .config import Config
from .delays import OneShot
from .protocols.proxy import ProxyHandler
from .roomdata.objects import DIRECTIONS, REVERSE_DIRECTIONS, Exit, Room
from .utils import decodeBytes, escapeXMLString, formatDocString, regexFuzzy, simplified, stripAnsi
from .world import LIGHT_SYMBOLS, RUN_DESTINATION_REGEX, TERRAIN_SYMBOLS, World


MAPPER_QUEUE_TYPE = Union[EVENT_CALLER_TYPE, None]
EXIT_TAGS_REGEX: Pattern[str] = re.compile(
	r"(?P<door>[\(\[\#]?)(?P<road>[=-]?)(?P<climb>[/\\]?)(?P<portal>[\{]?)"
	+ fr"(?P<direction>{'|'.join(DIRECTIONS)})"
)
MOVEMENT_FORCED_REGEX: Pattern[str] = re.compile(
	"|".join(
		[
			r"You feel confused and move along randomly\.\.\.",
			r"Suddenly an explosion of ancient rhymes makes the space collapse around you\!",
			r"The pain stops\, your vision clears\, and you realize that you are elsewhere\.",
			r"A guard leads you out of the house\.",
			r"You leave the ferry\.",
			r"You reached the riverbank\.",
			r"You stop moving towards the (?:left|right) bank and drift downstream\.",
			r"You are borne along by a strong current\.",
			r"You are swept away by the current\.",
			r"You are swept away by the powerful current of water\.",
			r"You board the ferry\.",
			r"You are dead\! Sorry\.\.\.",
			r"With a jerk\, the basket starts gliding down the rope towards the platform\.",
			r"The current pulls you faster\. Suddenly\, you are sucked downwards into darkness\!",
			r"You are washed blindly over the rocks\, and plummet sickeningly downwards\.\.\.",
			r"Oops\! You walk off the bridge and fall into the rushing water below\!",
			r"Holding your breath and with closed eyes\, you are squeezed below the surface of the water\.",
			r"You tighten your grip as (:a Great Eagle|Gwaihir the Windlord) starts to descend fast\.",
			r"The trees confuse you\, making you wander around in circles\.",
			r"Sarion helps you outside\.",
			(
				r"You cannot control your mount on the slanted and unstable surface\!"
				+ r"(?: You begin to slide to the north\, and plunge toward the water below\!)?"
			),
			(
				r"Stepping on the lizard corpses\, you use some depressions in the wall for support\, "
				+ r"push the muddy ceiling apart and climb out of the cave\."
			),
		]
	)
)
MOVEMENT_PREVENTED_REGEX: Pattern[str] = re.compile(
	"^(?:{lines})$".format(
		lines="|".join(
			[
				r"The \w+ seem[s]? to be closed\.",
				r"It seems to be locked\.",
				r"You cannot ride there\.",
				r"Your boat cannot enter this place\.",
				r"A guard steps in front of you\.",
				r"The clerk bars your way\.",
				r"You cannot go that way\.\.\.",
				r"Alas\, you cannot go that way\.\.\.",
				r"You need to swim to go there\.",
				r"You failed swimming there\.",
				r"You failed to climb there and fall down\, hurting yourself\.",
				r"Your mount cannot climb the tree\!",
				r"No way\! You are fighting for your life\!",
				r"In your dreams\, or what\?",
				r"You are too exhausted\.",
				r"You unsuccessfully try to break through the ice\.",
				r"Your mount refuses to follow your orders\!",
				r"You are too exhausted to ride\.",
				r"You can\'t go into deep water\!",
				r"You don\'t control your mount\!",
				r"Your mount is too sensible to attempt such a feat\.",
				r"Oops\! You cannot go there riding\!",
				r"You\'d better be swimming if you want to dive underwater\.",
				r"You need to climb to go there\.",
				r"You cannot climb there\.",
				r"If you still want to try\, you must \'climb\' there\.",
				r"Nah\.\.\. You feel too relaxed to do that\.",
				r"Maybe you should get on your feet first\?",
				r"Not from your present position\!",
				(
					r".+ (?:prevents|keeps) you from going "
					+ r"(?:north|south|east|west|up|down|upstairs|downstairs|past (?:him|her|it))\."
				),
				(
					r"A (?:pony|dales-pony|horse|warhorse|pack horse|trained horse|"
					+ r"horse of the Rohirrim|brown donkey|mountain mule|hungry warg|brown wolf)"
					+ r"(?: \(\w+\))? (?:is too exhausted|doesn't want you riding (?:him|her|it) anymore)\."
				),
			]
		)
	)
)
PROMPT_REGEX: Pattern[str] = re.compile(
	r"^(?P<light>[@*!\)o]?)(?P<terrain>[\#\(\[\+\.%fO~UW:=<]?)"
	+ r"(?P<weather>[*'\"~=-]{0,2})\s*(?P<movementFlags>[RrSsCcW]{0,4})[^\>]*\>$"
)


logger: logging.Logger = logging.getLogger(__name__)


class Mapper(threading.Thread, World):
	def __init__(
		self,
		playerSocket: socket.socket,
		gameSocket: socket.socket,
		outputFormat: str,
		interface: str,
		promptTerminator: Union[bytes, None],
		gagPrompts: bool,
		findFormat: str,
		isEmulatingOffline: bool,
	) -> None:
		threading.Thread.__init__(self)
		self.name: str = "Mapper"
		# Initialize the timer.
		self.initTimer: float = default_timer()
		self.outputFormat: str = outputFormat
		self.interface: str = interface
		self.gagPrompts: bool = gagPrompts
		self.findFormat: str = findFormat
		self.isEmulatingOffline: bool = isEmulatingOffline
		self.queue: SimpleQueue[MAPPER_QUEUE_TYPE] = SimpleQueue()
		cfg: Config = Config()
		self._autoUpdateRooms: bool = cfg.get("autoUpdateRooms", False)
		del cfg
		self.autoMapping: bool = False
		self.autoMerging: bool = True
		self.autoLinking: bool = True
		self.autoWalk: bool = False
		self.autoWalkDirections: List[str] = []
		self.userCommands: List[str] = [
			func[len("user_command_") :]
			for func in dir(self)
			if func.startswith("user_command_") and callable(getattr(self, func))
		]
		self.mudEventHandlers: Dict[str, Set[Callable[[str], None]]] = {}
		self.unknownMudEvents: List[str] = []
		for legacyHandler in [
			func[len("mud_event_") :]
			for func in dir(self)
			if func.startswith("mud_event_") and callable(getattr(self, func))
		]:
			self.registerMudEventHandler(legacyHandler, getattr(self, f"mud_event_{legacyHandler}"))
		ExitsCleaner(self, "exits")
		self.emulationCommands: List[str] = [
			func[len("emulation_command_") :]
			for func in dir(self)
			if func.startswith("emulation_command_") and callable(getattr(self, func))
		]
		# Commands that should have priority when matching user input to an emulation command.
		priorityCommands: List[str] = [
			"exits",
		]
		self.emulationCommands.sort(
			key=lambda command: (
				# Sort emulation commands with prioritized commands at the top, alphabetically otherwise.
				priorityCommands.index(command) if command in priorityCommands else len(priorityCommands),
				command,
			)
		)
		self.isEmulatingBriefMode: bool = True
		self.isEmulatingDynamicDescs: bool = True
		self.lastPathFindQuery: str = ""
		self.prompt: str = ""
		self.clock: Clock = Clock()
		self.scouting: bool = False
		self.movement: Union[str, None] = None
		self.moved: Union[str, None] = None
		self.roomName: Union[str, None] = None
		self.description: Union[str, None] = None
		self.dynamic: Union[str, None] = None
		self.exits: Union[str, None] = None
		self.timeEvent: Union[str, None] = None
		self.timeEventOffset: int = 0
		self.parsedHour: int = 0
		self.parsedMinutes: int = 0
		self.timeSynchronized: bool = False
		self.proxy: ProxyHandler = ProxyHandler(
			playerSocket.sendall,
			gameSocket.sendall,
			outputFormat=outputFormat,
			promptTerminator=promptTerminator,
			isEmulatingOffline=isEmulatingOffline,
			mapperCommands=[func.encode("us-ascii") for func in self.userCommands],
			eventCaller=self.queue.put,
		)
		self.proxy.connect()
		World.__init__(self, interface=self.interface)
		self.emulationRoom: Room = self.currentRoom
		self.lastEmulatedJump: Room = self.currentRoom

	@property
	def outputFormat(self) -> str:
		return str(getattr(self, "_outputFormat", OUTPUT_FORMATS[0]))

	@outputFormat.setter
	def outputFormat(self, value: str) -> None:
		if value not in OUTPUT_FORMATS:
			raise ValueError(f"{value} not in {OUTPUT_FORMATS}")
		self._outputFormat = value

	@property
	def interface(self) -> str:
		return str(getattr(self, "_interface", INTERFACES[0]))

	@interface.setter
	def interface(self, value: str) -> None:
		if value not in INTERFACES:
			raise ValueError(f"{value} not in {INTERFACES}")
		self._interface = value

	@property
	def autoUpdateRooms(self) -> bool:
		return self._autoUpdateRooms

	@autoUpdateRooms.setter
	def autoUpdateRooms(self, value: bool) -> None:
		self._autoUpdateRooms = bool(value)
		cfg: Config = Config()
		cfg["autoUpdateRooms"] = self._autoUpdateRooms
		cfg.save()
		del cfg

	def output(self, *args: Any, **kwargs: Any) -> None:
		# Override World.output.
		self.sendPlayer(*args, **kwargs)

	def sendPlayer(self, msg: str, showPrompt: bool = True) -> None:
		if self.outputFormat == "raw":
			if showPrompt and self.prompt and not self.gagPrompts:
				msg = f"{escapeXMLString(msg)}\n<prompt>{escapeXMLString(self.prompt)}</prompt>"
				self.proxy.player.write(msg.encode("utf-8"), escape=True, prompt=True)
			else:
				msg = f"\n{escapeXMLString(msg)}\n"
				self.proxy.player.write(msg.encode("utf-8"), escape=True)
		elif self.outputFormat == "tintin":
			if showPrompt and self.prompt and not self.gagPrompts:
				msg = f"{msg}\nPROMPT:{self.prompt}:PROMPT"
				self.proxy.player.write(msg.encode("utf-8"), escape=True, prompt=True)
			else:
				msg = f"\n{msg}\n"
				self.proxy.player.write(msg.encode("utf-8"), escape=True)
		else:
			if showPrompt and self.prompt and not self.gagPrompts:
				msg = f"{msg}\n{self.prompt}"
				self.proxy.player.write(msg.encode("utf-8"), escape=True, prompt=True)
			else:
				msg = f"\n{msg}\n"
				self.proxy.player.write(msg.encode("utf-8"), escape=True)

	def sendGame(self, msg: str) -> None:
		self.proxy.game.write(msg.encode("utf-8") + b"\n", escape=True)

	def emulation_command_quit(self, *args: str) -> None:
		"""Exits the program."""
		self.proxy.game.write(b"quit")

	def emulation_command_at(self, label: str, *args: str) -> None:
		"""mimic the /at command that the ainur use."""
		room: Union[Room, None] = self.getRoomFromLabel(label)
		if room is None:
			return None
		command = " ".join(args)
		if not command:
			self.sendPlayer(f"What do you want to do at {label}?")
			return
		# execute command at room
		oldRoom = self.emulationRoom
		self.emulationRoom = room
		self.user_command_emu(command)
		self.emulationRoom = oldRoom

	def emulation_command_brief(self, *args: str) -> None:
		"""toggles brief mode."""
		self.isEmulatingBriefMode = not self.isEmulatingBriefMode
		self.output(f"Brief mode {'on' if self.isEmulatingBriefMode else 'off'}")

	def emulation_command_dynamic(self, *args: str) -> None:
		"""toggles automatic speaking of dynamic descs."""
		self.isEmulatingDynamicDescs = not self.isEmulatingDynamicDescs
		self.sendPlayer("dynamic descs {}".format("on" if self.isEmulatingDynamicDescs else "off"))

	def emulation_command_examine(self, *args: str) -> None:
		"""shows the room's description."""
		self.output(self.emulationRoom.desc)

	def emulation_command_exits(self, *args: str) -> None:
		"""shows the exits in the room."""
		exits: List[str] = [key for key in DIRECTIONS if key in self.emulationRoom.exits.keys()]
		self.output(f"Exits: {', '.join(exits)}.")

	def emulation_command_go(self, label: Union[str, Room], isJump: bool = True) -> None:
		"""mimic the /go command that the ainur use."""
		room: Union[Room, None] = label if isinstance(label, Room) else self.getRoomFromLabel(label)
		if room is None:
			return None
		self.emulationRoom = room
		self.emulation_command_look()
		self.emulation_command_exits()
		if self.isEmulatingOffline:
			self.currentRoom = self.emulationRoom
		if isJump:
			self.lastEmulatedJump = room

	def emulation_command_help(self, *args: str) -> None:
		"""Shows documentation for mapper's emulation commands."""
		helpTexts: List[Tuple[str, str]] = [
			(funcName, getattr(self, "emulation_command_" + funcName).__doc__)
			for funcName in self.emulationCommands
		]
		documentedFuncs: List[Tuple[str, str]] = [
			(name, formatDocString(docString, prefix=" " * 8).strip())
			for name, docString in helpTexts
			if docString.strip()
		]
		undocumentedFuncs: List[Tuple[str, str]] = [text for text in helpTexts if not text[1].strip()]
		result: List[str] = [
			"The following commands allow you to emulate exploring the map without needing to move in game:",
			"\n".join("    {}: {}".format(*helpText) for helpText in documentedFuncs),
		]
		if undocumentedFuncs:
			result.append("The following commands have no documentation yet.")
			result.append(
				textwrap.indent(
					textwrap.fill(
						", ".join(helpText[0] for helpText in undocumentedFuncs),
						width=79,
						break_long_words=False,
						break_on_hyphens=False,
					),
					prefix="    ",
				)
			)
		self.output("\n".join(result))

	def emulation_command_look(self, *args: str) -> None:
		"""looks at the room."""
		self.output(self.emulationRoom.name)
		if not self.isEmulatingBriefMode:
			self.output(self.emulationRoom.desc)
		if self.isEmulatingDynamicDescs:
			self.sendPlayer(self.emulationRoom.dynamicDesc)
		if self.emulationRoom.note:
			self.output(f"Note: {self.emulationRoom.note}")

	def emulation_command_return(self, *args: str) -> None:
		"""returns to the last room jumped to with the go command."""
		if self.lastEmulatedJump:
			self.emulation_command_go(self.lastEmulatedJump)
		else:
			self.output("Cannot return anywhere until the go command has been used at least once.")

	def emulation_command_sync(self, *args: str) -> None:
		"""
		When emulating while connected to the mud, syncs the emulated location with the in-game location.
		When running in offline mode, is equivalent to the return command.
		"""
		if self.isEmulatingOffline:
			self.emulation_command_return()
		else:
			self.emulation_command_go(self.currentRoom)

	def emulate_leave(self, direction: str) -> None:
		"""emulates leaving the room into a neighbouring room"""
		if direction not in self.emulationRoom.exits:
			self.output("Alas, you cannot go that way...")
			return None
		vnum: str = self.emulationRoom.exits[direction].to
		if vnum == "death":
			self.output("deathtrap!")
		elif vnum == "undefined":
			self.output("undefined")
		else:
			self.emulation_command_go(vnum, isJump=False)

	def user_command_emu(self, *args: str) -> None:
		inputText: List[str] = args[0].strip().split()
		userCommand: str = inputText[0].lower()
		userArgs: str = " ".join(inputText[1:])
		if not userCommand:
			self.output("What command do you want to emulate?")
			return None
		# get the full name of the user's command
		for command in [*DIRECTIONS, *self.emulationCommands]:
			if command.startswith(userCommand):
				if command in DIRECTIONS:
					self.emulate_leave(command)
				else:
					getattr(self, f"emulation_command_{command}")(userArgs)
				return None
		# else try to execute the user command as a regular mapper command
		if userCommand in self.userCommands:
			# call the user command
			# first set current room to the emulation room so the user command acts on the emulation room
			oldRoom: Room = self.currentRoom
			self.currentRoom = self.emulationRoom
			getattr(self, f"user_command_{userCommand}")(userArgs)
			self.currentRoom = oldRoom
		else:
			room = self.getRoomFromLabel(userCommand)
			if room:
				self.emulation_command_go(room)
			else:
				self.output("Invalid command. Type 'help' for more help.")

	def user_command_gettimer(self, *args: str) -> None:
		self.sendPlayer(f"TIMER:{int(default_timer() - self.initTimer)}:TIMER")

	def user_command_gettimerms(self, *args: str) -> None:
		self.sendPlayer(f"TIMERMS:{int((default_timer() - self.initTimer) * 1000)}:TIMERMS")

	def user_command_clock(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.sendPlayer(self.clock.time())
		else:
			self.sendGame(self.clock.time(args[0].strip().lower()))

	def user_command_secretaction(self, *args: str) -> None:
		matchPattern: str = fr"^\s*(?P<action>.+?)(?:\s+(?P<direction>{regexFuzzy(DIRECTIONS)}))?$"
		match: Union[Match[str], None] = re.match(matchPattern, args[0].strip().lower())
		if match is None:
			self.sendPlayer(f"Syntax: 'secretaction [action] [{' | '.join(DIRECTIONS)}]'.")
			return None
		matchDict: Dict[str, str] = match.groupdict()
		direction: str
		if matchDict["direction"]:
			direction = "".join(d for d in DIRECTIONS if d.startswith(matchDict["direction"]))
		else:
			direction = ""
		door: str
		if direction and direction in self.currentRoom.exits and self.currentRoom.exits[direction].door:
			door = self.currentRoom.exits[direction].door
		else:
			door = "exit"
		self.sendGame(" ".join(item for item in (matchDict["action"], door, direction[0:1]) if item))

	def user_command_automap(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.autoMapping = not self.autoMapping
		else:
			self.autoMapping = args[0].strip().lower() == "on"
		self.sendPlayer(f"Auto Mapping {'on' if self.autoMapping else 'off'}.")

	def user_command_autoupdate(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.autoUpdateRooms = not self.autoUpdateRooms
		else:
			self.autoUpdateRooms = args[0].strip().lower() == "on"
		self.sendPlayer(f"Auto update rooms {'on' if self.autoUpdateRooms else 'off'}.")

	def user_command_automerge(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.autoMerging = not self.autoMerging
		else:
			self.autoMerging = args[0].strip().lower() == "on"
		self.sendPlayer(f"Auto Merging {'on' if self.autoMerging else 'off'}.")

	def user_command_autolink(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.autoLinking = not self.autoLinking
		else:
			self.autoLinking = args[0].strip().lower() == "on"
		self.sendPlayer(f"Auto Linking {'on' if self.autoLinking else 'off'}.")

	def user_command_rdelete(self, *args: str) -> None:
		self.sendPlayer(self.rdelete(*args))

	def user_command_fdoor(self, *args: str) -> None:
		self.sendPlayer(self.fdoor(self.findFormat, *args))

	def user_command_fdynamic(self, *args: str) -> None:
		self.sendPlayer(self.fdynamic(self.findFormat, *args))

	def user_command_flabel(self, *args: str) -> None:
		self.sendPlayer(self.flabel(self.findFormat, *args))

	def user_command_fname(self, *args: str) -> None:
		self.sendPlayer(self.fname(self.findFormat, *args))

	def user_command_fnote(self, *args: str) -> None:
		self.sendPlayer(self.fnote(self.findFormat, *args))

	def user_command_rnote(self, *args: str) -> None:
		self.sendPlayer(self.rnote(*args))

	def user_command_ralign(self, *args: str) -> None:
		self.sendPlayer(self.ralign(*args))

	def user_command_rlight(self, *args: str) -> None:
		self.sendPlayer(self.rlight(*args))

	def user_command_rportable(self, *args: str) -> None:
		self.sendPlayer(self.rportable(*args))

	def user_command_rridable(self, *args: str) -> None:
		self.sendPlayer(self.rridable(*args))

	def user_command_ravoid(self, *args: str) -> None:
		self.sendPlayer(self.ravoid(*args))

	def user_command_rterrain(self, *args: str) -> None:
		self.sendPlayer(self.rterrain(*args))

	def user_command_rx(self, *args: str) -> None:
		self.sendPlayer(self.rx(*args))

	def user_command_ry(self, *args: str) -> None:
		self.sendPlayer(self.ry(*args))

	def user_command_rz(self, *args: str) -> None:
		self.sendPlayer(self.rz(*args))

	def user_command_rmobflags(self, *args: str) -> None:
		self.sendPlayer(self.rmobflags(*args))

	def user_command_rloadflags(self, *args: str) -> None:
		self.sendPlayer(self.rloadflags(*args))

	def user_command_exitflags(self, *args: str) -> None:
		self.sendPlayer(self.exitflags(*args))

	def user_command_doorflags(self, *args: str) -> None:
		self.sendPlayer(self.doorflags(*args))

	def user_command_secret(self, *args: str) -> None:
		self.sendPlayer(self.secret(*args))

	def user_command_rlink(self, *args: str) -> None:
		self.sendPlayer(self.rlink(*args))

	def user_command_rinfo(self, *args: str) -> None:
		self.sendPlayer(self.rinfo(*args))

	def user_command_vnum(self, *args: str) -> None:
		"""states the vnum of the current room"""
		self.sendPlayer(f"Vnum: {self.currentRoom.vnum}.")

	def user_command_tvnum(self, *args: str) -> None:
		"""tells a given char the vnum of your room"""
		if not args or not args[0] or not args[0].strip():
			self.sendPlayer("Tell VNum to who?")
		else:
			self.sendGame(f"tell {args[0].strip()} {self.currentRoom.vnum}")

	def user_command_rlabel(self, *args: str) -> None:
		self.rlabel(*args)

	def user_command_getlabel(self, *args: str) -> None:
		self.sendPlayer(self.getlabel(*args))

	def user_command_savemap(self, *args: str) -> None:
		self.saveRooms()

	def user_command_run(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.sendPlayer("Usage: run [label|vnum]")
			return None
		self.stopRun()
		match: Union[Match[str], None]
		destination: str
		argString: str = args[0].strip()
		if argString.lower() == "t" or argString.lower().startswith("t "):
			argString = argString[2:].strip()
			if not argString and self.lastPathFindQuery:
				self.sendPlayer(
					f"Run target set to '{self.lastPathFindQuery}'. Use 'run t [rlabel|vnum]' to change it."
				)
				return None
			elif not argString:
				self.sendPlayer("Please specify a VNum or room label to target.")
				return None
			self.lastPathFindQuery = argString
			self.sendPlayer(f"Setting run target to '{self.lastPathFindQuery}'")
			return None
		elif argString.lower() == "c":
			if self.lastPathFindQuery:
				match = RUN_DESTINATION_REGEX.match(self.lastPathFindQuery)
				if match is None:
					return None
				destination = match.group("destination")
				self.sendPlayer(destination)
			else:
				self.sendPlayer("Error: no previous path to continue.")
				return None
		else:
			match = RUN_DESTINATION_REGEX.match(argString)
			if match is None:
				return None
			destination = match.group("destination")
		flags: str = match.group("flags")
		result: Union[List[str], None] = self.pathFind(
			destination=destination, flags=flags.split("|") if flags else None
		)
		if result is not None:
			self.autoWalk = True
			if result:
				if argString != "c":
					self.lastPathFindQuery = argString
				self.autoWalkDirections.extend(result)
				self.walkNextDirection()

	def user_command_step(self, *args: str) -> None:
		if not args or not args[0] or not args[0].strip():
			self.sendPlayer("Usage: step [label|vnum]")
			return None
		self.autoWalkDirections.clear()
		argString: str = args[0].strip()
		match: Union[Match[str], None] = RUN_DESTINATION_REGEX.match(argString)
		if match is not None:
			destination: str = match.group("destination")
			flags: str = match.group("flags")
			result: Union[List[str], None] = self.pathFind(
				destination=destination, flags=flags.split("|") if flags else None
			)
			if result is not None:
				self.autoWalkDirections.extend(result)
				self.walkNextDirection()
				return None
		self.sendPlayer("Please specify a valid destination.")

	def user_command_stop(self, *args: str) -> None:
		self.stopRun()
		self.sendPlayer("Run canceled!")

	def user_command_path(self, *args: str) -> None:
		self.path(*args)

	def user_command_sync(self, *args: str) -> None:
		if not args or not args[0]:
			self.sendPlayer("Map no longer synced. Auto sync on.")
			self.isSynced = False
			self.sendGame("look")
		else:
			self.sync(vnum=args[0].strip())

	def user_command_maphelp(self, *args: str) -> None:
		"""Shows documentation for mapper commands"""
		helpTexts: List[Tuple[str, str]] = [
			(funcName, getattr(self, "user_command_" + funcName).__doc__ or "")
			for funcName in self.userCommands
		]
		documentedFuncs: List[Tuple[str, str]] = [
			(name, formatDocString(docString, prefix=" " * 8).strip())
			for name, docString in helpTexts
			if docString.strip()
		]
		undocumentedFuncs: List[Tuple[str, str]] = [text for text in helpTexts if not text[1].strip()]
		result: List[str] = [
			"Mapper Commands",
			"The following commands are used for viewing and editing map data:",
			"\n".join("    {}: {}".format(*helpText) for helpText in documentedFuncs),
		]
		if undocumentedFuncs:
			result.append("Undocumented Commands:")
			result.append(
				textwrap.indent(
					textwrap.fill(
						", ".join(helpText[0] for helpText in undocumentedFuncs),
						width=79,
						break_long_words=False,
						break_on_hyphens=False,
					),
					prefix="    ",
				)
			)
		self.output("\n".join(result))

	def walkNextDirection(self) -> None:
		if not self.autoWalkDirections:
			return None
		while self.autoWalkDirections:
			command: str = self.autoWalkDirections.pop()
			if not self.autoWalkDirections:
				self.sendPlayer("Arriving at destination.")
				self.autoWalk = False
			if command in DIRECTIONS:
				# Send the first character of the direction to Mume.
				self.sendGame(command[0])
				break
			else:
				# command is a non-direction such as 'lead' or 'ride'.
				self.sendGame(command)

	def stopRun(self) -> None:
		self.autoWalk = False
		self.autoWalkDirections.clear()

	def sync(
		self, name: Optional[str] = None, desc: Optional[str] = None, vnum: Optional[str] = None
	) -> bool:
		if vnum is not None:
			roomObj: Union[Room, None] = self.getRoomFromLabel(vnum)
			if roomObj is not None:
				self.currentRoom = roomObj
				self.isSynced = True
				self.sendPlayer(f"Synced to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}")
		else:
			nameVnums: List[str] = []
			descVnums: List[str] = []
			for vnum, roomObj in self.rooms.items():
				if name and roomObj.name == name:
					nameVnums.append(vnum)
				if desc and roomObj.desc == desc:
					descVnums.append(vnum)
			if not nameVnums:
				self.sendPlayer("Current room not in the database. Unable to sync.")
			elif len(descVnums) == 1:
				self.currentRoom = self.rooms[descVnums[0]]
				self.isSynced = True
				self.sendPlayer(f"Synced to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}")
			elif len(nameVnums) == 1:
				self.currentRoom = self.rooms[nameVnums[0]]
				self.isSynced = True
				self.sendPlayer(
					f"Name-only synced to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}"
				)
			else:
				self.sendPlayer("More than one room in the database matches current room. Unable to sync.")
		return self.isSynced

	def roomDetails(self) -> None:
		doors: List[str] = []
		deathTraps: List[str] = []
		oneWays: List[str] = []
		undefineds: List[str] = []
		for direction, exitObj in self.currentRoom.exits.items():
			if exitObj.door and exitObj.door != "exit":
				doors.append(f"{direction}: {exitObj.door}")
			if not exitObj.to or exitObj.to == "undefined":
				undefineds.append(direction)
			elif exitObj.to == "death":
				deathTraps.append(direction)
			elif (
				REVERSE_DIRECTIONS[direction] not in self.rooms[exitObj.to].exits
				or self.rooms[exitObj.to].exits[REVERSE_DIRECTIONS[direction]].to != self.currentRoom.vnum
			):
				oneWays.append(direction)
		if doors:
			self.sendPlayer(f"Doors: {', '.join(doors)}", showPrompt=False)
		if deathTraps:
			self.sendPlayer(f"Death Traps: {', '.join(deathTraps)}", showPrompt=False)
		if oneWays:
			self.sendPlayer(f"One ways: {', '.join(oneWays)}", showPrompt=False)
		if undefineds:
			self.sendPlayer(f"Undefineds: {', '.join(undefineds)}", showPrompt=False)
		if self.currentRoom.note:
			self.sendPlayer(f"Note: {self.currentRoom.note}", showPrompt=False)

	def updateRoomFlags(self, prompt: str) -> None:
		match: Union[Match[str], None] = PROMPT_REGEX.search(prompt)
		if match is None:
			return None
		promptDict: Dict[str, str] = match.groupdict()
		output: List[str] = []
		with suppress(KeyError):
			light: str = LIGHT_SYMBOLS[promptDict["light"]]
			if light == "lit" and self.currentRoom.light != light:
				output.append(self.rlight("lit"))
		with suppress(KeyError):
			terrain: str = TERRAIN_SYMBOLS[promptDict["terrain"]]
			if self.currentRoom.terrain not in (terrain, "deathtrap"):
				output.append(self.rterrain(terrain))
		with suppress(KeyError):
			ridable: bool = "r" in promptDict["movementFlags"].lower()
			if ridable and self.currentRoom.ridable != "ridable":
				output.append(self.rridable("ridable"))
		if output:
			self.sendPlayer("\n".join(output))

	def updateExitFlags(self, exits: str) -> None:
		if not exits:
			return None
		output: List[str] = []
		exitsOutput: List[str] = []
		for door, road, climb, portal, direction in EXIT_TAGS_REGEX.findall(exits):
			# Portals aren't real exits.
			if portal:
				continue
			if direction not in self.currentRoom.exits:
				output.append(f"Adding exit '{direction}' to current room.")
				self.currentRoom.exits[direction] = self.getNewExit(direction)
				if self.autoLinking:
					currentRoomCoords: Tuple[int, int, int] = (
						self.currentRoom.x,
						self.currentRoom.y,
						self.currentRoom.z,
					)
					vnums: List[str] = [
						vnum
						for vnum, roomObj in self.rooms.items()
						if self.coordinatesAddDirection(currentRoomCoords, direction)
						== (roomObj.x, roomObj.y, roomObj.z)
					]
					if (
						len(vnums) == 1
						and REVERSE_DIRECTIONS[direction] in self.rooms[vnums[0]].exits
						and self.rooms[vnums[0]].exits[REVERSE_DIRECTIONS[direction]].to == "undefined"
					):
						output.append(self.rlink(f"add {vnums[0]} {direction}"))
			roomExit: Exit = self.currentRoom.exits[direction]
			if door and "door" not in roomExit.exitFlags:
				output.append(self.exitflags(f"add door {direction}"))
			if road and "road" not in roomExit.exitFlags:
				output.append(self.exitflags(f"add road {direction}"))
			if climb and "climb" not in roomExit.exitFlags:
				output.append(self.exitflags(f"add climb {direction}"))
			if exitsOutput:
				exitsOutput.insert(0, f"Exit {direction}:")
				output.extend(exitsOutput)
				exitsOutput.clear()
		if output:
			self.sendPlayer("\n".join(output))

	def autoMergeRoom(self, movement: str, roomObj: Room) -> None:
		output: List[str] = []
		if (
			self.autoLinking
			and REVERSE_DIRECTIONS[movement] in roomObj.exits
			and roomObj.exits[REVERSE_DIRECTIONS[movement]].to == "undefined"
		):
			output.append(self.rlink(f"add {roomObj.vnum} {movement}"))
		else:
			output.append(self.rlink(f"add oneway {roomObj.vnum} {movement}"))
		output.append(f"Auto Merging '{roomObj.vnum}' with name '{roomObj.name}'.")
		self.sendPlayer("\n".join(output))

	def addNewRoom(self, movement: str, name: str, description: str, dynamic: str) -> None:
		vnum: str = self.getNewVnum()
		newRoom: Room = Room()
		newRoom.vnum = vnum
		newRoom.name = name
		newRoom.desc = description
		newRoom.dynamicDesc = dynamic
		newRoom.x, newRoom.y, newRoom.z = self.coordinatesAddDirection(
			(self.currentRoom.x, self.currentRoom.y, self.currentRoom.z), movement
		)
		self.rooms[vnum] = newRoom
		if movement not in self.currentRoom.exits:
			self.currentRoom.exits[movement] = self.getNewExit(movement, to=vnum)
		else:
			self.currentRoom.exits[movement].to = vnum
		self.sendPlayer(f"Adding room '{newRoom.name}' with vnum '{vnum}'")

	def mud_event_prompt(self, text: str) -> None:
		self.prompt = text
		if self.isSynced:
			if self.autoMapping and self.moved:
				self.updateRoomFlags(self.prompt)
		elif self.roomName:
			self.sync(self.roomName, self.description)
		if self.isSynced and self.dynamic is not None:
			self.roomDetails()
			if self.autoWalkDirections and self.moved and self.autoWalk:
				# The player is auto-walking. Send the next direction to Mume.
				self.walkNextDirection()
		self.scouting = False
		self.movement = None
		self.moved = None
		self.roomName = None
		self.description = None
		self.dynamic = None

	def mud_event_movement(self, text: str) -> None:
		self.movement = text
		self.scouting = False

	def mud_event_line(self, text: str) -> None:
		if text.startswith("You quietly scout "):
			self.scouting = True
			return None
		elif text == "A huge clock is standing here.":
			self.sendGame("look at clock")
		elif text == (
			"Wet, cold and filled with mud you drop down into a dark "
			+ "and moist cave, while you notice the mud above you moving "
			+ "to close the hole you left in the cave ceiling."
		):
			self.sync(vnum="17189")
		elif text == (
			"The gravel below your feet loosens, shifting slightly.. "
			+ "Suddenly, you lose your balance and crash to the cave floor below."
		):
			self.sync(vnum="15324")
		elif not self.timeSynchronized:
			self.syncTime(text)
		if MOVEMENT_FORCED_REGEX.search(text) or MOVEMENT_PREVENTED_REGEX.search(text):
			self.stopRun()
		if self.isSynced and self.autoMapping:
			if text == "It's too difficult to ride here." and self.currentRoom.ridable != "notridable":
				self.sendPlayer(self.rridable("notridable"))
			elif text == "You are already riding." and self.currentRoom.ridable != "ridable":
				self.sendPlayer(self.rridable("ridable"))

	def syncTime(self, text: str) -> None:
		clockMatch: Union[Match[str], None] = CLOCK_REGEX.match(text)
		timeMatch: Union[Match[str], None] = TIME_REGEX.match(text)
		if self.timeEvent is None:
			if clockMatch is not None:
				hour: int = int(clockMatch.group("hour"))
				minutes: int = int(clockMatch.group("minutes"))
				amPm: str = clockMatch.group("am_pm")
				# parsedHour should be 0 - 23.
				self.parsedHour = hour % 12 + (12 if amPm == "pm" else 0)
				self.parsedMinutes = minutes
				if self.parsedHour == 23 and self.parsedMinutes == 59:
					OneShot(1.0, self.sendGame, "look at clock")
				else:
					self.timeEvent = "clock"
					self.sendGame("time")
			elif DAWN_REGEX.match(text) is not None:
				self.timeEvent = "dawn"
				self.timeEventOffset = 0
				self.sendGame("time")
			elif DAY_REGEX.match(text) is not None:
				self.timeEvent = "dawn"
				self.timeEventOffset = 1
				self.sendGame("time")
			elif DUSK_REGEX.match(text) is not None:
				self.timeEvent = "dusk"
				self.timeEventOffset = 0
				self.sendGame("time")
			elif NIGHT_REGEX.match(text) is not None:
				self.timeEvent = "dusk"
				self.timeEventOffset = 1
				self.sendGame("time")
		elif timeMatch is not None:
			day: int = int(timeMatch.group("day"))
			year: int = int(timeMatch.group("year"))
			month: int = 0
			for i, m in enumerate(MONTHS):
				if timeMatch.group("month") in (m["westron"], m["sindarin"]):
					month = i
					break
			if self.timeEvent in ("dawn", "dusk"):
				self.parsedHour = int(MONTHS[month][self.timeEvent]) + self.timeEventOffset
				self.parsedMinutes = 0
			self.clock.setTime(year, month, day, self.parsedHour, self.parsedMinutes)
			self.timeEvent = None
			self.timeEventOffset = 0
			self.timeSynchronized = True
			self.sendPlayer(f"Synchronized with epoch {self.clock.epoch}.", showPrompt=False)

	def mud_event_name(self, text: str) -> None:
		if text not in ("You just see a dense fog around you...", "It is pitch black..."):
			self.roomName = simplified(text)
		else:
			self.roomName = ""

	def mud_event_description(self, text: str) -> None:
		self.description = simplified(text)

	def validateMovement(self, movement: str) -> bool:
		if not movement:
			# The player was forcibly moved in an unknown direction.
			self.sendPlayer("Forced movement, no longer synced.")
		elif movement not in DIRECTIONS:
			self.sendPlayer(f"Error: Invalid direction '{movement}'. Map no longer synced!")
		elif not self.autoMapping and movement not in self.currentRoom.exits:
			self.sendPlayer(f"Error: direction '{movement}' not in database. Map no longer synced!")
		elif not self.autoMapping and self.currentRoom.exits[movement].to not in self.rooms:
			self.sendPlayer(
				f"Error: vnum ({self.currentRoom.exits[movement].to}) in direction ({movement}) "
				+ "is not in the database. Map no longer synced!"
			)
		else:
			return True
		self.isSynced = False
		return False

	def mud_event_dynamic(self, text: str) -> None:
		self.dynamic = text
		self.moved = None
		addedNewRoomFrom: Union[str, None] = None
		if not self.isSynced or self.movement is None:
			return None
		elif self.validateMovement(self.movement):
			if self.autoMapping and (
				self.movement not in self.currentRoom.exits
				or self.currentRoom.exits[self.movement].to not in self.rooms
			):
				# Player has moved in a direction that either doesn't exist in the database
				# or links to an invalid vnum (E.G. undefined).
				duplicates: Union[List[Room], None]
				if self.autoMerging and self.roomName and self.description:
					duplicates = self.searchRooms(exactMatch=True, name=self.roomName, desc=self.description)
				else:
					duplicates = None
				if not self.roomName:
					self.sendPlayer("Unable to add new room: empty room name.")
				elif not self.description:
					self.sendPlayer("Unable to add new room: empty room description.")
				elif duplicates is not None and len(duplicates) == 1:
					self.autoMergeRoom(self.movement, duplicates[0])
				else:
					# Create new room.
					addedNewRoomFrom = self.currentRoom.vnum
					self.addNewRoom(self.movement, self.roomName, self.description, self.dynamic)
			self.currentRoom = self.rooms[self.currentRoom.exits[self.movement].to]
			self.moved = self.movement
			self.movement = None
			if self.autoMapping and self.autoUpdateRooms:
				if self.roomName and self.currentRoom.name != self.roomName:
					self.currentRoom.name = self.roomName
					self.sendPlayer("Updating room name.")
				if self.description and self.currentRoom.desc != self.description:
					self.currentRoom.desc = self.description
					self.sendPlayer("Updating room description.")
				if self.dynamic and self.currentRoom.dynamicDesc != self.dynamic:
					self.currentRoom.dynamicDesc = self.dynamic
					self.sendPlayer("Updating room dynamic description.")
		if self.autoMapping and self.isSynced and self.moved and self.exits:
			if addedNewRoomFrom and REVERSE_DIRECTIONS[self.moved] in self.exits:
				self.currentRoom.exits[REVERSE_DIRECTIONS[self.moved]] = self.getNewExit(
					REVERSE_DIRECTIONS[self.moved], to=addedNewRoomFrom
				)
			self.updateExitFlags(self.exits)
		self.exits = None

	def mud_event_exits(self, text: str) -> None:
		self.exits = text

	def handleUserData(self, data: bytes) -> None:
		data = data.strip()
		if not data:
			return None
		elif self.isEmulatingOffline:
			self.user_command_emu(decodeBytes(data))
		else:
			userCommand: bytes = data.split()[0]
			args: bytes = data[len(userCommand) :].strip()
			getattr(self, f"user_command_{decodeBytes(userCommand)}")(decodeBytes(args))

	def handleMudEvent(self, event: str, data: bytes) -> None:
		text: str = stripAnsi(decodeBytes(data))
		if event in self.mudEventHandlers:
			if not self.scouting or event in ("prompt", "movement"):
				for handler in self.mudEventHandlers[event]:
					handler(text)
		elif event not in self.unknownMudEvents:
			self.unknownMudEvents.append(event)
			logger.debug(f"received data with an unknown event type of {event}")

	def registerMudEventHandler(self, event: str, handler: Callable[[str], None]) -> None:
		"""Registers a method to handle mud events of a given type.
		Params: event, handler
		where event is the name of the event type, typically corresponding to the XML tag of the incoming data,
		and handler is a method that takes a single argument, text, which is the text received from the mud.
		"""
		if event not in self.mudEventHandlers:
			self.mudEventHandlers[event] = set()
		if event in self.unknownMudEvents:
			self.unknownMudEvents.remove(event)
		self.mudEventHandlers[event].add(handler)

	def deregisterMudEventHandler(self, event: str, handler: Callable[[str], None]) -> None:
		"""Deregisters mud event handlers.
		params: same as registerMudEventHandler.
		"""
		if event in self.mudEventHandlers and handler in self.mudEventHandlers[event]:
			self.mudEventHandlers[event].remove(handler)
			if not self.mudEventHandlers[event]:
				del self.mudEventHandlers[event]

	def run(self) -> None:
		item: EVENT_CALLER_TYPE
		for item in iter(self.queue.get, None):
			try:
				event, data = item
				if event == "userInput":
					self.handleUserData(data)
				else:
					self.handleMudEvent(*item)
			except Exception:
				self.output(f"Error in mapper thread:\n{traceback.format_exc().strip()}")
				logger.exception("Error in mapper thread")
		self.sendPlayer("Exiting mapper thread.")
