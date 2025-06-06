# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import json
import logging
import re
import textwrap
import threading
import traceback
from contextlib import suppress
from itertools import starmap
from queue import SimpleQueue
from timeit import default_timer
from typing import Any, Optional, Union, cast

# Third-party Modules:
from knickknacks.databytes import decode_bytes
from knickknacks.strings import format_docstring, regex_fuzzy, simplified, strip_ansi
from knickknacks.xml import escape_xml_string, get_xml_attributes

# Local Modules:
from . import INTERFACES, OUTPUT_FORMATS, cfg
from .cleanmap import ExitsCleaner
from .clock import CLOCK_REGEX, DAWN_REGEX, DAY_REGEX, DUSK_REGEX, MONTHS, NIGHT_REGEX, TIME_REGEX, Clock
from .delays import OneShot
from .proxy import Game, Player, ProxyHandler
from .remoteediting import GMCPRemoteEditing, RemoteEditingCommand
from .roomdata.objects import DIRECTIONS, REVERSE_DIRECTIONS, Exit, Room
from .sockets.bufferedsocket import BufferedSocket
from .typedef import (
	GAME_WRITER_TYPE,
	MAPPER_QUEUE_TYPE,
	MUD_EVENT_HANDLER_TYPE,
	PLAYER_WRITER_TYPE,
	ReMatchType,
	RePatternType,
)
from .world import LIGHT_SYMBOLS, RUN_DESTINATION_REGEX, World


EXIT_TAGS_REGEX: RePatternType = re.compile(
	r"(?P<door>[\(\[\#]?)(?P<road>[=-]?)(?P<climb>[/\\]?)(?P<portal>[\{]?)"
	+ rf"(?P<direction>{'|'.join(DIRECTIONS)})"
)
MOVEMENT_FORCED_REGEX: RePatternType = re.compile(
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
MOVEMENT_PREVENTED_REGEX: RePatternType = re.compile(
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
				r"You can(?:not ride|\'t go) into deep water\!",
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


logger: logging.Logger = logging.getLogger(__name__)


class Mapper(threading.Thread, World):
	def __init__(
		self,
		playerSocket: BufferedSocket,
		gameSocket: BufferedSocket,
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
		self.queue: MAPPER_QUEUE_TYPE = SimpleQueue()
		self.autoMapping: bool = False
		self.autoMerging: bool = True
		self.autoLinking: bool = True
		self.autoWalk: bool = False
		self.autoWalkDirections: list[str] = []
		userCommandPrefix: str = "user_command_"
		self.userCommands: list[str] = [
			func.removeprefix(userCommandPrefix)
			for func in dir(self)
			if func.startswith(userCommandPrefix) and callable(getattr(self, func))
		]
		self.mudEventHandlers: dict[str, set[MUD_EVENT_HANDLER_TYPE]] = {}
		self.unknownMudEvents: list[str] = []
		mudEventPrefix: str = "mud_event_"
		legacyHandlers: list[str] = [
			func.removeprefix(mudEventPrefix)
			for func in dir(self)
			if func.startswith(mudEventPrefix) and callable(getattr(self, func))
		]
		for legacyHandler in legacyHandlers:
			self.registerMudEventHandler(legacyHandler, getattr(self, mudEventPrefix + legacyHandler))
		ExitsCleaner(self, "exits")
		emulationCommandPrefix: str = "emulation_command_"
		self.emulationCommands: list[str] = [
			func.removeprefix(emulationCommandPrefix)
			for func in dir(self)
			if func.startswith(emulationCommandPrefix) and callable(getattr(self, func))
		]
		# Commands that should have priority when matching user input to an emulation command.
		priorityCommands: list[str] = [
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
		self.xmlRoomAttributes: dict[str, Union[str, None]] = {}
		self.timeEvent: Union[str, None] = None
		self.timeEventOffset: int = 0
		self.parsedHour: int = 0
		self.parsedMinutes: int = 0
		self.timeSynchronized: bool = False
		self.proxy: ProxyHandler = ProxyHandler(
			cast(PLAYER_WRITER_TYPE, playerSocket.send),  # TODO: Fix this later.
			cast(GAME_WRITER_TYPE, gameSocket.send),  # TODO: Fix this later.
			outputFormat=outputFormat,
			promptTerminator=promptTerminator,
			isEmulatingOffline=isEmulatingOffline,
			mapperCommands=[func.encode("us-ascii") for func in self.userCommands],
			eventCaller=self.queue.put,
		)
		self._autoUpdateRooms: bool = cfg.get("autoUpdateRooms", False)
		self.proxy.connect()
		World.__init__(self, interface=self.interface)
		self.emulationRoom: Room = self.currentRoom
		self.lastEmulatedJump: Union[str, None] = None
		self.shouldNotifyNotSynced: bool = True
		self.gmcpRemoteEditing = GMCPRemoteEditing(
			outputFormat=outputFormat, gmcpSend=self.gameTelnetHandler.gmcp_send
		)
		try:
			self.gmcpRemoteEditing.isWordWrapping = cfg.get("wordwrap", False)
		except LookupError:
			logger.exception("Unable to set initial value of GMCP remote editing word wrap.")
		self.gmcpCharacter: dict[str, Any] = {}
		self.gmcpGroup: dict[int, dict[str, Any]] = {}

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
		cfg["autoUpdateRooms"] = self._autoUpdateRooms
		cfg.save()

	@property
	def gameTelnetHandler(self) -> Game:
		for handler in self.proxy.game._handlers:
			if isinstance(handler, Game):
				return handler
		raise LookupError("Game Telnet Handler not found")

	@property
	def playerTelnetHandler(self) -> Player:
		for handler in self.proxy.player._handlers:
			if isinstance(handler, Player):
				return handler
		raise LookupError("Player Telnet Handler not found")

	def output(self, *args: Any, **kwargs: Any) -> None:
		# Override World.output.
		self.sendPlayer(*args, **kwargs)

	def sendPlayer(self, msg: str, showPrompt: bool = True) -> None:
		with suppress(ConnectionError):
			with suppress(LookupError):
				gmcpMessageOutput: bool = self.playerTelnetHandler.mpmMessageSend({"text": msg})
				if gmcpMessageOutput:
					# Player is receiving messages through GMCP.
					return
			if self.outputFormat == "raw":
				if showPrompt and self.prompt and not self.gagPrompts:
					msg = f"{escape_xml_string(msg)}\n<prompt>{escape_xml_string(self.prompt)}</prompt>"
					self.proxy.player.write(msg.encode("utf-8"), escape=True, prompt=True)
				else:
					msg = f"\n{escape_xml_string(msg)}\n"
					self.proxy.player.write(msg.encode("utf-8"), escape=True)
			elif self.outputFormat == "tintin":
				if showPrompt and self.prompt and not self.gagPrompts:
					msg = f"{msg}\nPROMPT:{self.prompt}:PROMPT"
					self.proxy.player.write(msg.encode("utf-8"), escape=True, prompt=True)
				else:
					msg = f"\n{msg}\n"
					self.proxy.player.write(msg.encode("utf-8"), escape=True)
			elif showPrompt and self.prompt and not self.gagPrompts:
				msg = f"{msg}\n{self.prompt}"
				self.proxy.player.write(msg.encode("utf-8"), escape=True, prompt=True)
			else:
				msg = f"\n{msg}\n"
				self.proxy.player.write(msg.encode("utf-8"), escape=True)

	def sendGame(self, msg: str) -> None:
		with suppress(ConnectionError):
			self.proxy.game.write(msg.encode("utf-8") + b"\n", escape=True)

	def emulation_command_quit(self, *args: str) -> tuple[str, ...]:
		"""Exits the program."""
		self.proxy.game.write(b"quit")
		return args

	def emulation_command_at(self, *args: str) -> tuple[str, ...]:
		"""Mimic the /at command that the ainur use. Syntax: at (room label|room number) (command)"""
		label: str = "".join(args[:1]).strip()
		command: str = " ".join(args[1:]).strip()
		if not label:
			self.sendPlayer("Please provide a room in which to execute commands.")
		else:
			room: Union[Room, None] = self.getRoomFromLabel(label)
			if room is None:
				pass  # Alternative suggestions were sent by the call to `getRoomFromLabel`.
			elif not command:
				self.sendPlayer(f"What do you want to do at {label}?")
			else:
				# Execute command at room.
				oldRoom: Room = self.emulationRoom
				self.emulationRoom = room
				self.user_command_emu(command)
				self.emulationRoom = oldRoom
		return ()

	def emulation_command_brief(self, *args: str) -> tuple[str, ...]:
		"""Toggles brief mode."""
		self.isEmulatingBriefMode = not self.isEmulatingBriefMode
		self.output(f"Brief mode {'on' if self.isEmulatingBriefMode else 'off'}")
		return args

	def emulation_command_dynamic(self, *args: str) -> tuple[str, ...]:
		"""Toggles automatic speaking of dynamic descs."""
		self.isEmulatingDynamicDescs = not self.isEmulatingDynamicDescs
		self.sendPlayer(f"dynamic descs {'on' if self.isEmulatingDynamicDescs else 'off'}")
		return args

	def emulation_command_examine(self, *args: str) -> tuple[str, ...]:
		"""Shows the room's description."""
		self.output(self.emulationRoom.desc)
		return args

	def emulation_command_exits(self, *args: str) -> tuple[str, ...]:
		"""Shows the exits in the room."""
		exits: list[str] = [key for key in DIRECTIONS if key in self.emulationRoom.exits]
		self.output(f"Exits: {', '.join(exits)}.")
		return args

	def emulation_command_go(self, *args: str, isJump: bool = True) -> tuple[str, ...]:
		"""Mimic the /go command that the ainur use. Syntax: go (room label|room number) (command)"""
		label: str = "".join(args[:1]).strip()
		args = args[1:]
		room: Union[Room, None] = self.getRoomFromLabel(label)
		if room is not None:
			self.emulationRoom = room
			self.emulation_command_look()
			self.emulation_command_exits()
			if self.isEmulatingOffline:
				self.currentRoom = self.emulationRoom
			if isJump:
				self.lastEmulatedJump = room.vnum
		return args

	def emulation_command_help(self, *args: str) -> tuple[str, ...]:
		"""Shows documentation for mapper's emulation commands."""
		helpTexts: list[tuple[str, str]] = [
			(funcName, getattr(self, "emulation_command_" + funcName).__doc__)
			for funcName in self.emulationCommands
		]
		documentedFuncs: list[tuple[str, str]] = [
			(name, format_docstring(docString, prefix=" " * 8).strip())
			for name, docString in helpTexts
			if docString.strip()
		]
		undocumentedFuncs: list[tuple[str, str]] = [text for text in helpTexts if not text[1].strip()]
		result: list[str] = [
			"The following commands allow you to emulate exploring the map without needing to move in game:",
			"\n".join(starmap("    {}: {}".format, documentedFuncs)),
		]
		if undocumentedFuncs:
			undocumentedText: str = textwrap.indent(
				textwrap.fill(
					", ".join(helpText[0] for helpText in undocumentedFuncs),
					width=79,
					break_long_words=False,
					break_on_hyphens=False,
				),
				prefix="    ",
			)
			result.append(f"The following commands have no documentation yet.\n{undocumentedText}")
		self.output("\n".join(result))
		return args

	def emulation_command_look(self, *args: str) -> tuple[str, ...]:
		"""Looks at the room."""
		self.output(self.emulationRoom.name)
		if not self.isEmulatingBriefMode:
			self.output(self.emulationRoom.desc)
		if self.isEmulatingDynamicDescs:
			self.sendPlayer(self.emulationRoom.dynamicDesc)
		if self.emulationRoom.note:
			self.output(f"Note: {self.emulationRoom.note}")
		return args

	def emulation_command_return(self, *args: str) -> tuple[str, ...]:
		"""Returns to the last room jumped to with the go command."""
		if self.lastEmulatedJump is not None:
			self.emulation_command_go(self.lastEmulatedJump)
		else:
			self.output("Cannot return anywhere until the go command has been used at least once.")
		return args

	def emulation_command_rename(self, *args: str) -> tuple[str, ...]:
		"""Changes the room name. (useful for exploring places with many similar names)"""
		name: str = " ".join(args).strip()
		if name:
			self.emulationRoom.name = name
			self.sendPlayer(f"Room name set to '{name}'.")
		else:
			self.sendPlayer("Error: You must specify a new room name.")
		return ()

	def emulation_command_sync(self, *args: str) -> tuple[str, ...]:
		"""
		When emulating while connected to the mud, syncs the emulated location with the in-game location.
		When running in offline mode, is equivalent to the return command.
		"""
		if self.isEmulatingOffline:
			self.emulation_command_return()
		else:
			self.emulation_command_go(self.currentRoom.vnum)
		return args

	def emulate_leave(self, direction: str, *args: str) -> tuple[str, ...]:
		"""Emulates leaving the room into a neighbouring room"""
		if direction not in self.emulationRoom.exits:
			self.output("Alas, you cannot go that way...")
			return args
		vnum: str = self.emulationRoom.exits[direction].to
		if vnum == "death":
			self.output("deathtrap!")
		elif vnum == "undefined":
			self.output("undefined")
		else:
			self.emulation_command_go(vnum, isJump=False)
		return args

	def user_command_emu(self, inputText: str, *args: str) -> None:
		if not inputText:
			self.output("What command do you want to emulate?")
			return
		words: tuple[str, ...] = tuple(inputText.strip().split())
		while words:
			words = self.emulateCommands(*words)

	def emulateCommands(self, *words: str) -> tuple[str, ...]:
		userCommand: str = words[0].lower()
		userArgs: tuple[str, ...] = words[1:]
		# Get the full name of the user's command.
		for command in [*DIRECTIONS, *self.emulationCommands]:
			if command.startswith(userCommand):
				remainingArgs: tuple[str, ...]
				if command in DIRECTIONS:
					remainingArgs = self.emulate_leave(command, *userArgs)
				else:
					remainingArgs = getattr(self, f"emulation_command_{command}")(*userArgs)
				return remainingArgs
		# Else try to execute the user command as a regular mapper command.
		if userCommand in self.userCommands:
			# Call the user command from the emulation room.
			oldRoom: Room = self.currentRoom
			self.currentRoom = self.emulationRoom
			getattr(self, f"user_command_{userCommand}")(" ".join(userArgs))
			self.currentRoom = oldRoom
			return ()
		# Otherwise, treat userCommand as a potential vnum or room label to jump to.
		return self.emulation_command_go(userCommand, *userArgs)

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
		matchPattern: str = rf"^\s*(?P<action>.+?)(?:\s+(?P<direction>{regex_fuzzy(DIRECTIONS)}))?$"
		match: ReMatchType = re.match(matchPattern, args[0].strip().lower())
		if match is None:
			self.sendPlayer(f"Syntax: 'secretaction [action] [{' | '.join(DIRECTIONS)}]'.")
			return
		matchDict: dict[str, str] = match.groupdict()
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

	def user_command_farea(self, *args: str) -> None:
		self.sendPlayer(self.farea(self.findFormat, *args))

	def user_command_fsid(self, *args: str) -> None:
		self.sendPlayer(self.fsid(self.findFormat, *args))

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

	def user_command_rsundeath(self, *args: str) -> None:
		self.sendPlayer(self.rsundeath(*args))

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

	def user_command_wordwrap(self, *args: str) -> None:
		try:
			value: bool = not self.gmcpRemoteEditing.isWordWrapping
			self.gmcpRemoteEditing.isWordWrapping = value
			cfg["wordwrap"] = value
			cfg.save()
			self.sendPlayer(f"Word Wrap {'enabled' if value else 'disabled'}.")
		except LookupError as e:
			self.sendPlayer(f"Unable to toggle word wrapping: {', '.join(e.args)}.")

	def user_command_secret(self, *args: str) -> None:
		self.sendPlayer(self.secret(*args))

	def user_command_rlink(self, *args: str) -> None:
		self.sendPlayer(self.rlink(*args))

	def user_command_rinfo(self, *args: str) -> None:
		self.sendPlayer(self.rinfo(*args))

	def user_command_vnum(self, *args: str) -> None:
		"""States the vnum of the current room"""
		self.sendPlayer(f"Vnum: {self.currentRoom.vnum}.")

	def user_command_tvnum(self, *args: str) -> None:
		"""Tells a given char the vnum of your room"""
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
			return
		self.stopRun()
		match: ReMatchType
		destination: str
		argString: str = args[0].strip()
		if argString.lower() == "t" or argString.lower().startswith("t "):
			argString = argString[2:].strip()
			if not argString and self.lastPathFindQuery:
				self.sendPlayer(
					f"Run target set to '{self.lastPathFindQuery}'. Use 'run t [rlabel|vnum]' to change it."
				)
				return
			if not argString:
				self.sendPlayer("Please specify a VNum or room label to target.")
				return
			self.lastPathFindQuery = argString
			self.sendPlayer(f"Setting run target to '{self.lastPathFindQuery}'")
			return
		if argString.lower() == "c":
			if self.lastPathFindQuery:
				match = RUN_DESTINATION_REGEX.match(self.lastPathFindQuery)
				if match is None:
					return
				destination = match.group("destination")
				self.sendPlayer(destination)
			else:
				self.sendPlayer("Error: no previous path to continue.")
				return
		else:
			match = RUN_DESTINATION_REGEX.match(argString)
			if match is None:
				return
			destination = match.group("destination")
		flags: str = match.group("flags")
		result: Union[list[str], None] = self.pathFind(
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
			return
		self.autoWalkDirections.clear()
		argString: str = args[0].strip()
		match: ReMatchType = RUN_DESTINATION_REGEX.match(argString)
		if match is not None:
			destination: str = match.group("destination")
			flags: str = match.group("flags")
			result: Union[list[str], None] = self.pathFind(
				destination=destination, flags=flags.split("|") if flags else None
			)
			if result is not None:
				self.autoWalkDirections.extend(result)
				self.walkNextDirection()
				return
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
		helpTexts: list[tuple[str, str]] = [
			(funcName, getattr(self, "user_command_" + funcName).__doc__ or "")
			for funcName in self.userCommands
		]
		documentedFuncs: list[tuple[str, str]] = [
			(name, format_docstring(docString, prefix=" " * 8).strip())
			for name, docString in helpTexts
			if docString.strip()
		]
		undocumentedFuncs: list[tuple[str, str]] = [text for text in helpTexts if not text[1].strip()]
		result: list[str] = [
			"Mapper Commands",
			"The following commands are used for viewing and editing map data:",
			"\n".join(starmap("    {}: {}".format, documentedFuncs)),
		]
		if undocumentedFuncs:
			undocumentedText: str = textwrap.indent(
				textwrap.fill(
					", ".join(helpText[0] for helpText in undocumentedFuncs),
					width=79,
					break_long_words=False,
					break_on_hyphens=False,
				),
				prefix="    ",
			)
			result.append(f"Undocumented Commands:\n{undocumentedText}")
		self.output("\n".join(result))

	def walkNextDirection(self) -> None:
		if not self.autoWalkDirections:
			return
		while self.autoWalkDirections:
			command: str = self.autoWalkDirections.pop()
			if not self.autoWalkDirections:
				self.sendPlayer("Arriving at destination.")
				self.autoWalk = False
			if command in DIRECTIONS:
				# Send the first character of the direction to Mume.
				self.sendGame(command[0])
				break
			# command is a non-direction such as 'lead' or 'ride'.
			self.sendGame(command)

	def stopRun(self) -> None:
		self.autoWalk = False
		self.autoWalkDirections.clear()

	def sync(
		self,
		name: Optional[str] = None,
		desc: Optional[str] = None,
		vnum: Optional[str] = None,
	) -> bool:
		if vnum is not None:
			roomObj: Union[Room, None] = self.getRoomFromLabel(vnum)
			if roomObj is not None:
				self.currentRoom = roomObj
				self.isSynced = True
				self.sendPlayer(f"Synced to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}")
		else:
			serverID: Union[str, None] = self.xmlRoomAttributes.get("id")
			serverIDVnum: str = ""
			nameVnums: set[str] = set()
			descVnums: set[str] = set()
			for roomVnum, roomObj in self.rooms.items():
				if serverID is not None and roomObj.serverID == serverID:
					serverIDVnum = roomVnum
					break
				if name and roomObj.name == name:
					nameVnums.add(roomVnum)
				if desc and roomObj.desc == desc:
					descVnums.add(roomVnum)
			nameDescIntersectionVnums: set[str] = nameVnums.intersection(descVnums)
			if serverIDVnum or len(nameDescIntersectionVnums) == 1:
				self.currentRoom = self.rooms[serverIDVnum or "".join(nameDescIntersectionVnums)]
				self.isSynced = True
				self.shouldNotifyNotSynced = True
				syncMethod: str = "server ID" if serverIDVnum else "name and desc"
				self.sendPlayer(
					f"Synced {syncMethod} to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}"
				)
			elif len(descVnums) == 1:
				self.currentRoom = self.rooms["".join(descVnums)]
				self.isSynced = True
				self.shouldNotifyNotSynced = True
				self.sendPlayer(
					f"Desc-only synced to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}"
				)
			elif len(nameVnums) == 1:
				self.currentRoom = self.rooms["".join(nameVnums)]
				self.isSynced = True
				self.shouldNotifyNotSynced = True
				self.sendPlayer(
					f"Name-only synced to room {self.currentRoom.name} with vnum {self.currentRoom.vnum}"
				)
			elif self.shouldNotifyNotSynced:
				self.shouldNotifyNotSynced = False
				reason: str = (
					"More than one room in the database matches current room."
					if nameVnums or descVnums
					else "Current room not in the database."
				)
				self.sendPlayer(f"{reason} Unable to sync.")
		return self.isSynced

	def roomDetails(self) -> None:
		doors: list[str] = []
		deathTraps: list[str] = []
		oneWays: list[str] = []
		undefineds: list[str] = []
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

	def updateRoomFlags(self) -> None:
		output: list[str] = []
		lightSymbol: Union[str, None] = self.gmcpCharacter.get("light")
		if lightSymbol is not None and lightSymbol in LIGHT_SYMBOLS:
			light: str = LIGHT_SYMBOLS[lightSymbol]
			if light == "lit" and self.currentRoom.light != light:
				# TODO: Orc can define sundeath, troll can define no_sundeath and lit/dark.
				# output.append(self.rlight("lit"))
				pass
		ridable: bool = bool(self.gmcpCharacter.get("ride") or self.gmcpCharacter.get("ridden"))
		if ridable and self.currentRoom.ridable != "ridable":
			output.append(self.rridable("ridable"))
		if output:
			self.sendPlayer("\n".join(output))

	def updateExitFlags(self, exits: str) -> None:
		if not exits:
			return
		output: list[str] = []
		exitsOutput: list[str] = []
		for door, road, climb, portal, direction in EXIT_TAGS_REGEX.findall(exits):
			# Portals aren't real exits.
			if portal:
				continue
			if direction not in self.currentRoom.exits:
				output.append(f"Adding exit '{direction}' to current room.")
				self.currentRoom.exits[direction] = self.getNewExit(direction)
				if self.autoLinking:
					currentRoomCoords: tuple[int, int, int] = (
						self.currentRoom.x,
						self.currentRoom.y,
						self.currentRoom.z,
					)
					vnums: list[str] = [
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
		output: list[str] = []
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

	def mud_event_gmcp_char_name(self, text: str) -> None:
		value: dict[str, Any] = json.loads(text)
		self.gmcpCharacter.update(value)

	def mud_event_gmcp_char_statusvars(self, text: str) -> None:
		value: dict[str, Any] = json.loads(text)
		self.gmcpCharacter.update(value)

	def mud_event_gmcp_char_vitals(self, text: str) -> None:
		value: dict[str, Any] = json.loads(text)
		self.gmcpCharacter.update(value)
		if self.autoMapping:
			self.updateRoomFlags()

	def mud_event_gmcp_event_darkness(self, text: str) -> None:  # NOQA: PLR6301
		value: dict[str, Any] = json.loads(text)
		if "what" in value and isinstance(value["what"], str):
			pass  # Do something.

	def mud_event_gmcp_event_sun(self, text: str) -> None:  # NOQA: PLR6301
		value: dict[str, Any] = json.loads(text)
		if "what" in value and isinstance(value["what"], str):
			pass  # Do something.

	def mud_event_gmcp_group_add(self, text: str) -> None:
		self.gmcpGroupUpdate(json.loads(text))

	def mud_event_gmcp_group_remove(self, text: str) -> None:
		char_id: int = json.loads(text)
		self.gmcpGroup.pop(char_id, None)

	def mud_event_gmcp_group_set(self, text: str) -> None:
		self.gmcpGroup.clear()
		for value in json.loads(text):
			self.gmcpGroupUpdate(value)

	def mud_event_gmcp_group_update(self, text: str) -> None:
		self.gmcpGroupUpdate(json.loads(text))

	def gmcpGroupUpdate(self, value: dict[str, Any]) -> None:
		if "id" not in value:
			logger.warning("No 'id' key in value.")
			return
		if value.get("type") == "you":
			self.gmcpCharacter.update(value)
		self.gmcpGroup.setdefault(value["id"], {}).update(value)

	def mud_event_gmcp_mume_client_canceledit(self, text: str) -> None:
		value = json.loads(text)
		# Result is either True or an error message.
		result = value["result"]
		if isinstance(result, str):
			self.output(result.strip())

	def mud_event_gmcp_mume_client_edit(self, text: str) -> None:
		value = json.loads(text)
		self.gmcpRemoteEditing.start(RemoteEditingCommand.EDIT, **value)

	def mud_event_gmcp_mume_client_error(self, text: str) -> None:
		value = json.loads(text)
		self.output(value["message"].strip())

	def mud_event_gmcp_mume_client_view(self, text: str) -> None:
		value = json.loads(text)
		self.gmcpRemoteEditing.start(RemoteEditingCommand.VIEW, **value)

	def mud_event_gmcp_mume_client_write(self, text: str) -> None:
		value = json.loads(text)
		# Result is either True or an error message.
		result = value["result"]
		if isinstance(result, str):
			self.output(result.strip())

	def mud_event_prompt(self, text: str) -> None:
		self.playerTelnetHandler.mpmEventSend({"prompt": text})
		self.prompt = text
		if self.isSynced:
			if self.autoMapping and self.moved:
				self.updateRoomFlags()
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
			return
		if text == "A huge clock is standing here.":
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
			if text == "It's too difficult to ride here." and self.currentRoom.ridable != "not_ridable":
				self.sendPlayer(self.rridable("not_ridable"))
			elif text == "You are already riding." and self.currentRoom.ridable != "ridable":
				self.sendPlayer(self.rridable("ridable"))

	def syncTime(self, text: str) -> None:
		clockMatch: ReMatchType = CLOCK_REGEX.match(text)
		timeMatch: ReMatchType = TIME_REGEX.match(text)
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
				if timeMatch.group("month") in {m["westron"], m["sindarin"]}:
					month = i
					break
			if self.timeEvent in {"dawn", "dusk"}:
				self.parsedHour = int(MONTHS[month][self.timeEvent]) + self.timeEventOffset
				self.parsedMinutes = 0
			self.clock.setTime(year, month, day, self.parsedHour, self.parsedMinutes)
			self.timeEvent = None
			self.timeEventOffset = 0
			self.timeSynchronized = True
			self.sendPlayer(f"Synchronized with epoch {self.clock.epoch}.", showPrompt=False)

	def mud_event_room(self, text: str) -> None:
		self.xmlRoomAttributes.clear()
		self.xmlRoomAttributes.update(get_xml_attributes(text))

	def mud_event_name(self, text: str) -> None:
		if text not in {"You just see a dense fog around you...", "It is pitch black..."}:
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

	def updateRooms(self) -> None:
		if self.roomName and self.currentRoom.name != self.roomName:
			self.currentRoom.name = self.roomName
			self.sendPlayer("Updating room name.")
		if self.description and self.currentRoom.desc != self.description:
			self.currentRoom.desc = self.description
			self.sendPlayer("Updating room description.")
		if self.dynamic and self.currentRoom.dynamicDesc != self.dynamic:
			self.currentRoom.dynamicDesc = self.dynamic
			self.sendPlayer("Updating room dynamic description.")
		terrain: Union[str, None] = self.xmlRoomAttributes.get("terrain")
		if terrain is not None and self.currentRoom.terrain != terrain:
			self.sendPlayer(self.rterrain(terrain))
		area: Union[str, None] = self.xmlRoomAttributes.get("area")
		if area is not None and self.currentRoom.area != area:
			self.currentRoom.area = area
			self.sendPlayer(f"Setting room area to '{area}'.")
		serverID: Union[str, None] = self.xmlRoomAttributes.get("id")
		if serverID is not None and serverID.isdigit() and self.currentRoom.serverID != serverID:
			self.currentRoom.serverID = serverID
			self.sendPlayer(f"Setting room server ID to '{serverID}'.")

	def mud_event_dynamic(self, text: str) -> None:
		self.dynamic = text.lstrip()
		self.moved = None
		addedNewRoomFrom: Union[str, None] = None
		if not self.isSynced or self.movement is None:
			return
		if self.validateMovement(self.movement):
			if self.autoMapping and (
				self.movement not in self.currentRoom.exits
				or self.currentRoom.exits[self.movement].to not in self.rooms
			):
				# Player has moved in a direction that either doesn't exist in the database
				# or links to an invalid vnum (E.G. undefined).
				duplicates: Union[list[Room], None]
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
				self.updateRooms()
		if self.autoMapping and self.isSynced and self.moved and self.exits:
			if addedNewRoomFrom and REVERSE_DIRECTIONS[self.moved] in self.exits:
				self.currentRoom.exits[REVERSE_DIRECTIONS[self.moved]] = self.getNewExit(
					REVERSE_DIRECTIONS[self.moved], to=addedNewRoomFrom
				)
			self.updateExitFlags(self.exits)
		self.exits = None

	def mud_event_exits(self, text: str) -> None:
		self.exits = text

	def handleUserInput(self, text: str) -> None:
		text = text.strip()
		if not text:
			return
		if self.isEmulatingOffline:
			self.user_command_emu(text)
		else:
			userCommand: str = text.split()[0]
			args: str = text.removeprefix(userCommand).strip()
			getattr(self, f"user_command_{userCommand}")(args)

	def handleMudEvent(self, event: str, text: str) -> None:
		text = strip_ansi(text)
		if event in self.mudEventHandlers:
			if not self.scouting or event in {"prompt", "movement"}:
				for handler in self.mudEventHandlers[event]:
					handler(text)
		elif event not in self.unknownMudEvents:
			self.unknownMudEvents.append(event)
			logger.debug(f"received data with an unknown event type of {event}")

	def registerMudEventHandler(self, event: str, handler: MUD_EVENT_HANDLER_TYPE) -> None:
		"""
		Registers a method to handle mud events of a given type.

		Args:
			event: The name of the event type, typically corresponding to the XML tag of the incoming data.
			handler: A method that takes a single argument, text, which is the text received from the mud.
		"""
		if event not in self.mudEventHandlers:
			self.mudEventHandlers[event] = set()
		if event in self.unknownMudEvents:
			self.unknownMudEvents.remove(event)
		self.mudEventHandlers[event].add(handler)

	def deregisterMudEventHandler(self, event: str, handler: MUD_EVENT_HANDLER_TYPE) -> None:
		"""
		Deregisters mud event handlers.
		params: same as registerMudEventHandler.
		"""
		if event in self.mudEventHandlers and handler in self.mudEventHandlers[event]:
			self.mudEventHandlers[event].remove(handler)
			if not self.mudEventHandlers[event]:
				del self.mudEventHandlers[event]

	def run(self) -> None:
		for item in iter(self.queue.get, None):
			try:
				event, data = item
				text = decode_bytes(data)
				if event == "userInput":
					self.handleUserInput(text)
				else:
					self.handleMudEvent(event, text)
			except Exception:  # NOQA: PERF203
				self.output(f"Error in mapper thread:\n{traceback.format_exc().strip()}")
				logger.exception("Error in mapper thread")
		self.sendPlayer("Exiting mapper thread.")
