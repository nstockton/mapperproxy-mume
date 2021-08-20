# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from typing import Any, Callable, Dict, List, Union

# Third-party Modules:
from mudproto.base import Protocol
from mudproto.charset import CharsetMixIn
from mudproto.manager import Manager
from mudproto.mccp import MCCPMixIn
from mudproto.mpi import MPI_INIT, MPIProtocol
from mudproto.telnet import TelnetProtocol
from mudproto.telnet_constants import GA, IAC, LF, NEGOTIATION_BYTES, SB, SE
from mudproto.xml import EVENT_CALLER_TYPE, XMLProtocol


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


class Player(Telnet):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="player", **kwargs)

	def on_unhandledCommand(self, command: bytes, option: Union[bytes, None]) -> None:
		# Forward unhandled commands to the game.
		if option is None:
			self.proxy.game.write(IAC + command)
		else:
			self.proxy.game.write(IAC + command + option)

	def on_unhandledSubnegotiation(self, option: bytes, data: bytes) -> None:
		# Forward unhandled subnegotiations to the game.
		self.proxy.game.write(IAC + SB + option + data + IAC + SE)

	def on_enableLocal(self, option: bytes) -> bool:
		gameSubnegotiationMap: Union[Dict[bytes, Callable[[bytes], None]], None]
		game: Protocol = self.proxy.game._handlers[0]
		gameSubnegotiationMap = getattr(game, "subnegotiationMap", None)
		if gameSubnegotiationMap is not None and option in gameSubnegotiationMap:
			return False
		return super().on_enableLocal(option)


class Game(MCCPMixIn, CharsetMixIn, Telnet):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="game", **kwargs)
		self.commandMap[GA] = self.on_ga

	def on_ga(self, *args: Union[bytes, None]) -> None:
		"""Called when a Go Ahead command is received."""
		self.proxy.player.write(b"", prompt=True)

	def on_connectionMade(self) -> None:
		super().on_connectionMade()
		# Tell the Mume server to put IAC-GA at end of prompts.
		self.write(MPI_INIT + b"P2" + LF + b"G" + LF)

	def on_unhandledCommand(self, command: bytes, option: Union[bytes, None]) -> None:
		if option is None:
			self.proxy.player.write(IAC + command)
		else:
			self.proxy.player.write(IAC + command + option)

	def on_unhandledSubnegotiation(self, option: bytes, data: bytes) -> None:
		self.proxy.player.write(IAC + SB + option + data + IAC + SE)


class ProxyHandler(object):
	def __init__(
		self,
		playerWriter: Callable[[bytes], None],
		gameWriter: Callable[[bytes], None],
		*,
		outputFormat: str,
		promptTerminator: Union[bytes, None],
		isEmulatingOffline: bool,
		mapperCommands: List[bytes],
		eventCaller: Callable[[EVENT_CALLER_TYPE], None],
	) -> None:
		self.outputFormat: str = outputFormat
		self.isEmulatingOffline: bool = isEmulatingOffline
		self.mapperCommands: List[bytes] = mapperCommands
		self.eventCaller: Callable[[EVENT_CALLER_TYPE], None] = eventCaller
		self.player: Manager = Manager(
			playerWriter, self.on_playerReceived, promptTerminator=promptTerminator
		)
		self.player.register(Player, proxy=self)
		self.game: Manager = Manager(gameWriter, self.on_gameReceived, promptTerminator=promptTerminator)
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
		if self.isEmulatingOffline or b"".join(data.strip().split()[:1]) in self.mapperCommands:
			self.eventCaller(("userInput", data))
		else:
			self.game.write(data, escape=True)

	def on_gameReceived(self, data: bytes) -> None:
		self.player.write(data, escape=True)
