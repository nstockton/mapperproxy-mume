# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import json
import logging
from collections.abc import Callable
from typing import Any, Union, cast

# Third-party Modules:
from mudproto.charset import CharsetMixIn
from mudproto.gmcp import GMCPMixIn
from mudproto.manager import Manager
from mudproto.mccp import MCCPMixIn
from mudproto.mpi import MPI_INIT, MPIProtocol
from mudproto.naws import NAWSMixIn
from mudproto.telnet import TelnetProtocol
from mudproto.telnet_constants import CR_LF, GA, GMCP, IAC, LF, NAWS, NEGOTIATION_BYTES, SB, SE
from mudproto.utils import escapeIAC
from mudproto.xml import XMLProtocol

# Local Modules:
from . import __version__
from .typedef import XML_EVENT_CALLER_TYPE


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
		if self.name not in ("player", "game"):
			raise ValueError("Name must be 'player' or 'game'")
		self.proxy: ProxyHandler = proxy

	def on_command(self, command: bytes, option: Union[bytes, None]) -> None:
		if command in NEGOTIATION_BYTES and option not in self.subnegotiationMap:
			# Treat any unhandled negotiation options the same as unhandled commands, so
			# they are forwarded to the other end of the proxy.
			self.on_unhandledCommand(command, option)
		else:
			super().on_command(command, option)

	def on_unhandledCommand(self, command: bytes, option: Union[bytes, None]) -> None:
		# Forward unhandled commands to the other side of the proxy.
		writer = self.proxy.game.write if self.name == "player" else self.proxy.player.write
		if option is None:
			writer(IAC + command)
		else:
			writer(IAC + command + option)

	def on_unhandledSubnegotiation(self, option: bytes, data: bytes) -> None:
		# Forward unhandled subnegotiations to the other side of the proxy.
		writer = self.proxy.game.write if self.name == "player" else self.proxy.player.write
		writer(IAC + SB + option + escapeIAC(data) + IAC + SE)


class Player(GMCPMixIn, Telnet):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="player", **kwargs)
		self._mpmGMCP: bool = False

	@property
	def game(self) -> Game:
		return cast(Game, self.proxy.game._handlers[0])

	def gmcpSend(self, *args: Any, **kwargs: Any) -> None:
		if self.isGMCPInitialized:
			# Only send GMCP messages from game if player's client has enabled GMCP.
			super().gmcpSend(*args, **kwargs)

	def mpmMessageSend(self, value: Any) -> bool:
		if self._mpmGMCP:
			self.gmcpSend("mpm.message", value, isSerialized=False)
			return True
		return False

	def mpmEventSend(self, value: Any) -> bool:
		if self._mpmGMCP:
			self.gmcpSend("mpm.event", value, isSerialized=False)
			return True
		return False

	def on_gmcpMessage(self, package: str, value: bytes) -> None:
		if package == "core.supports.set":
			# Player's client may append, but not replace packages.
			package = "core.supports.add"
		elif package == "core.supports.remove":
			# Player's client may not remove packages.
			# Change this in future to allow player's client to only remove packages it previously added.
			return None
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
		if self.game.isGMCPInitialized:
			self.game.gmcpSend(package, value, isSerialized=True)
		else:
			self.game._gmcpBuffer.append((package, value, True))

	def on_enableLocal(self, option: bytes) -> bool:
		if option != GMCP and option in self.game.subnegotiationMap:
			return False
		return super().on_enableLocal(option)


class Game(MCCPMixIn, GMCPMixIn, CharsetMixIn, NAWSMixIn, Telnet):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="game", gmcpClientInfo=("MPM", __version__), **kwargs)
		self._gmcpBuffer: list[tuple[str, bytes, bool]] = []
		self.commandMap[GA] = self.on_ga

	@property
	def player(self) -> Player:
		return cast(Player, self.proxy.player._handlers[0])

	def on_ga(self, *args: Union[bytes, None]) -> None:
		"""Called when a Go Ahead command is received."""
		self.proxy.player.write(b"", prompt=True)

	def on_gmcpMessage(self, package: str, value: bytes) -> None:
		if package == "char.vitals":
			self.proxy.eventCaller(("gmcp_char_vitals", value))
		self.player.gmcpSend(package, value, isSerialized=True)

	def on_connectionMade(self) -> None:
		super().on_connectionMade()
		# Tell the Mume server to put IAC-GA at end of prompts.
		self.write(MPI_INIT + b"P2" + LF + b"G" + LF)

	def on_optionEnabled(self, option: bytes) -> None:
		super().on_optionEnabled(option)  # pragma: no cover
		if option == NAWS:
			# NAWS was enabled.
			self.nawsDimensions = (80, 0xFFFF)  # 80 character width, max line hight.
		if option == GMCP:
			# We just sent GMCP Hello to the game.
			supportedPackages: dict[str, int] = {
				"Char": 1,
				"Event": 1,
			}
			self.gmcpSetPackages(supportedPackages)
			while self._gmcpBuffer:
				package, value, isSerialized = self._gmcpBuffer.pop(0)
				self.gmcpSend(package, value, isSerialized=isSerialized)


class ProxyHandler(object):
	def __init__(
		self,
		playerWriter: Callable[[bytes], None],
		gameWriter: Callable[[bytes], None],
		*,
		outputFormat: str,
		promptTerminator: Union[bytes, None],
		isEmulatingOffline: bool,
		mapperCommands: list[bytes],
		eventCaller: XML_EVENT_CALLER_TYPE,
	) -> None:
		self.outputFormat: str = outputFormat
		self.isEmulatingOffline: bool = isEmulatingOffline
		self.mapperCommands: list[bytes] = mapperCommands
		self.playerInputBuffer: bytearray = bytearray()
		self.eventCaller: XML_EVENT_CALLER_TYPE = eventCaller
		self.player: Manager = Manager(
			playerWriter, self.on_playerReceived, isClient=False, promptTerminator=promptTerminator
		)
		self.player.register(Player, proxy=self)
		self.game: Manager = Manager(
			gameWriter, self.on_gameReceived, isClient=True, promptTerminator=promptTerminator
		)
		self.game.register(Game, proxy=self)
		self.game.register(MPIProtocol, outputFormat=self.outputFormat)
		self.game.register(
			XMLProtocol,
			outputFormat=self.outputFormat,
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
		for line in data.splitlines(True):
			if line[-1] not in CR_LF:
				# Final line was incomplete.
				self.playerInputBuffer.extend(line)
				break
			elif self.isEmulatingOffline or b"".join(line.strip().split()[:1]) in self.mapperCommands:
				self.eventCaller(("userInput", line))
			else:
				self.game.write(line, escape=True)

	def on_gameReceived(self, data: bytes) -> None:
		self.player.write(data, escape=True)
