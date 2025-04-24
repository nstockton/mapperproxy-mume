# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import json
import logging
from collections.abc import Iterable
from typing import Any, Union, cast

# Third-party Modules:
from mudproto.charset import CharsetMixIn
from mudproto.gmcp import GMCPMixIn
from mudproto.manager import Manager
from mudproto.mccp import MCCPMixIn
from mudproto.mpi import MPIProtocol
from mudproto.naws import UINT16_MAX, Dimensions, NAWSMixIn
from mudproto.telnet import TelnetProtocol, escape_iac
from mudproto.telnet_constants import CR_LF, GA, GMCP, IAC, NAWS, NEGOTIATION_BYTES, SB, SE
from mudproto.xml import XMLProtocol as _XMLProtocol

# Local Modules:
from . import __version__
from .typedef import GAME_WRITER_TYPE, MUD_EVENT_CALLER_TYPE, PLAYER_WRITER_TYPE


logger: logging.Logger = logging.getLogger(__name__)


class Telnet(TelnetProtocol):
	"""
	Attributes:
		name: The name of this side of the connection. Can be 'game' or 'player'.
		proxy: The proxy that spawned this object.
	"""

	def __init__(self, *args: Any, name: str, proxy: ProxyHandler, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		self.name: str = name
		if self.name not in {"player", "game"}:
			raise ValueError("Name must be 'player' or 'game'")
		self.proxy: ProxyHandler = proxy

	def on_command(self, command: bytes, option: Union[bytes, None]) -> None:
		if command in NEGOTIATION_BYTES and option not in self.subnegotiation_map:
			# Treat any unhandled negotiation options the same as unhandled commands, so
			# they are forwarded to the other end of the proxy.
			self.on_unhandled_command(command, option)
		else:
			super().on_command(command, option)

	def on_unhandled_command(self, command: bytes, option: Union[bytes, None]) -> None:
		# Forward unhandled commands to the other side of the proxy.
		writer = self.proxy.game.write if self.name == "player" else self.proxy.player.write
		if option is None:
			writer(IAC + command)
		else:
			writer(IAC + command + option)

	def on_unhandled_subnegotiation(self, option: bytes, data: bytes) -> None:
		# Forward unhandled subnegotiations to the other side of the proxy.
		writer = self.proxy.game.write if self.name == "player" else self.proxy.player.write
		writer(IAC + SB + option + escape_iac(data) + IAC + SE)


class Player(GMCPMixIn, Telnet):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="player", **kwargs)
		self._mpmGMCP: bool = False

	@property
	def game(self) -> Game:
		return cast(Game, self.proxy.game._handlers[0])

	def gmcp_send(self, *args: Any, **kwargs: Any) -> None:
		if self.is_gmcp_initialized:
			# Only send GMCP messages from game if player's client has enabled GMCP.
			super().gmcp_send(*args, **kwargs)

	def mpmMessageSend(self, value: Any) -> bool:
		if self._mpmGMCP:
			self.gmcp_send("mpm.message", value, is_serialized=False)
			return True
		return False

	def mpmEventSend(self, value: Any) -> bool:
		if self._mpmGMCP:
			self.gmcp_send("mpm.event", value, is_serialized=False)
			return True
		return False

	def on_gmcp_message(self, package: str, value: bytes) -> None:
		if package == "core.supports.set":
			# Player's client may append, but not replace packages.
			package = "core.supports.add"
		elif package == "core.supports.remove":
			# Player's client may not remove packages.
			# Change this in future to allow player's client to only remove packages it previously added.
			return
		if package == "core.supports.add":
			addedPackages: list[str] = []
			for item in json.loads(value):
				lowered: str = item.strip().lower()
				if lowered.startswith("mpm"):
					if not self._mpmGMCP:
						self._mpmGMCP = True
						self.mpmEventSend({"gmcp_enabled": True})
						continue
				elif lowered.startswith("mmapper"):
					continue
				addedPackages.append(item)
			value = bytes(
				json.dumps(addedPackages, ensure_ascii=False, indent=None, separators=(", ", ": ")), "utf-8"
			)
		if self.game.is_gmcp_initialized:
			self.game.gmcp_send(package, value, is_serialized=True)
		else:
			self.game._gmcpBuffer.append((package, value, True))

	def on_enable_local(self, option: bytes) -> bool:
		if option != GMCP and option in self.game.subnegotiation_map:
			return False
		return super().on_enable_local(option)


class Game(MCCPMixIn, GMCPMixIn, CharsetMixIn, NAWSMixIn, Telnet):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="game", gmcpClientInfo=("MPM", __version__), **kwargs)
		self._gmcpBuffer: list[tuple[str, bytes, bool]] = []
		self.command_map[GA] = self.on_ga

	@property
	def player(self) -> Player:
		return cast(Player, self.proxy.player._handlers[0])

	def on_ga(self, *args: Union[bytes, None]) -> None:
		"""Called when a Go Ahead command is received."""
		self.proxy.player.write(b"", prompt=True)

	def on_gmcp_message(self, package: str, value: bytes) -> None:
		supported: set[str] = {
			"char.name",
			"char.statusvars",
			"char.vitals",
			"event.darkness",
			"event.sun",
			"group.add",
			"group.remove",
			"group.set",
			"group.update",
		}
		if package in supported:
			self.proxy.eventCaller((f"gmcp_{package.replace('.', '_')}", value))
		self.player.gmcp_send(package, value, is_serialized=True)

	def on_option_enabled(self, option: bytes) -> None:
		super().on_option_enabled(option)  # pragma: no cover
		if option == NAWS:
			# NAWS was enabled.
			self.nawsDimensions = Dimensions(UINT16_MAX, UINT16_MAX)  # Max character width, max line hight.
		elif option == GMCP:
			# We just sent GMCP Hello to the game.
			supportedPackages: dict[str, int] = {
				"Char": 1,
				"Event": 1,
				"Group": 1,
			}
			self.gmcp_set_packages(supportedPackages)
			while self._gmcpBuffer:
				package, value, is_serialized = self._gmcpBuffer.pop(0)
				self.gmcp_send(package, value, is_serialized=is_serialized)


class XMLProtocol(_XMLProtocol):
	def __init__(self, *args: Any, eventCaller: MUD_EVENT_CALLER_TYPE, **kwargs: Any) -> None:
		self.eventCaller: MUD_EVENT_CALLER_TYPE = eventCaller
		super().__init__(*args, **kwargs)

	def on_xml_event(self, name: str, data: bytes) -> None:
		self.eventCaller((name, data))


class ProxyHandler:
	def __init__(
		self,
		playerWriter: PLAYER_WRITER_TYPE,
		gameWriter: GAME_WRITER_TYPE,
		*,
		outputFormat: str,
		promptTerminator: Union[bytes, None],
		isEmulatingOffline: bool,
		mapperCommands: Iterable[bytes],
		eventCaller: MUD_EVENT_CALLER_TYPE,
	) -> None:
		self.outputFormat: str = outputFormat
		self.isEmulatingOffline: bool = isEmulatingOffline
		self.mapperCommands: Iterable[bytes] = mapperCommands
		self.playerInputBuffer: bytearray = bytearray()
		self.eventCaller: MUD_EVENT_CALLER_TYPE = eventCaller
		self.player: Manager = Manager(
			playerWriter, self.on_playerReceived, is_client=False, prompt_terminator=promptTerminator
		)
		self.player.register(Player, proxy=self)
		self.game: Manager = Manager(
			gameWriter, self.on_gameReceived, is_client=True, prompt_terminator=promptTerminator
		)
		self.game.register(Game, proxy=self)
		self.game.register(MPIProtocol, output_format=self.outputFormat)
		self.game.register(
			XMLProtocol,
			output_format=self.outputFormat,
			eventCaller=self.eventCaller,
		)

	def close(self) -> None:
		self.disconnect()

	def connect(self) -> None:
		self.player.connect()
		self.game.connect()

	def disconnect(self) -> None:
		self.game.disconnect()
		self.player.disconnect()

	def on_playerReceived(self, data: bytes) -> None:
		if self.playerInputBuffer:
			data = bytes(self.playerInputBuffer + data)
			self.playerInputBuffer.clear()
		for line in data.splitlines(keepends=True):
			if line[-1] not in CR_LF:
				# Final line was incomplete.
				self.playerInputBuffer.extend(line)
				break
			if self.isEmulatingOffline or b"".join(line.strip().split()[:1]) in self.mapperCommands:
				self.eventCaller(("userInput", line))
			else:
				self.game.write(line, escape=True)

	def on_gameReceived(self, data: bytes) -> None:
		self.player.write(data, escape=True)
