# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import socket
from typing import Any, Callable, Dict, List, Tuple, Union

# Local Modules:
from .base import Protocol
from .manager import Manager
from .mpi import MPI_INIT, MPIProtocol
from .telnet import TelnetProtocol
from .telnet_constants import (
	CHARSET,
	CHARSET_ACCEPTED,
	CHARSET_REJECTED,
	CHARSET_REQUEST,
	CR,
	CR_LF,
	CR_NULL,
	GA,
	IAC,
	LF,
	NEGOTIATION_BYTES,
	SB,
	SE,
)
from .xml import XMLProtocol
from .. import EVENT_CALLER_TYPE
from ..utils import escapeIAC


logger: logging.Logger = logging.getLogger(__name__)


class Telnet(TelnetProtocol):
	"""
	Attributes:
		name: The name of this side of the connection. Can be 'game' or 'player'.
		proxy: The proxy that spawned this object.
	"""

	def __init__(self, *args: Any, name: str, proxy: ProxyHandler, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)  # type: ignore[misc]
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
		super().__init__(*args, name="player", **kwargs)  # type: ignore[misc]

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


class Game(Telnet):
	charsets: Tuple[bytes, ...] = (
		b"US-ASCII",
		b"ISO-8859-1",
		b"UTF-8",
	)
	"""Supported character sets."""

	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, name="game", **kwargs)  # type: ignore[misc]
		self.commandMap[GA] = self.on_ga
		self.subnegotiationMap[CHARSET] = self.on_charset
		self._charset: bytes = self.charsets[0]

	@property
	def charset(self) -> bytes:
		"""The character set to be used."""
		return self._charset

	@charset.setter
	def charset(self, value: bytes) -> None:
		if value not in self.charsets:
			raise ValueError(f"'{value!r}' not in {self.charsets!r}")
		self._charset = value

	def negotiateCharset(self, name: bytes) -> None:
		"""
		Negotiates changing the character set.

		Args:
			name: The name of the character set to use.
		"""
		self._oldCharset = self.charset
		try:
			self.charset = name
		except ValueError:
			logger.warning(f"Invalid charset {name!r}: falling back to {self.charset!r}.")
			name = self.charset
		separator = b";"
		logger.debug(f"Tell peer we would like to use the {name!r} charset.")
		self.requestNegotiation(CHARSET, CHARSET_REQUEST + separator + name)

	def on_charset(self, data: bytes) -> None:
		"""
		Called when a charset subnegotiation is received.

		Args:
			data: The payload.
		"""
		status, response = data[:1], data[1:]
		if status == CHARSET_ACCEPTED:
			logger.debug(f"Peer responds: Charset {response!r} accepted.")
		elif status == CHARSET_REJECTED:
			logger.warning("Peer responds: Charset rejected.")
			if self.charset == self._oldCharset:
				logger.warning(f"Unable to fall back to {self._oldCharset!r}. Old and new charsets match.")
			else:
				logger.debug(f"Falling back to {self._oldCharset!r}.")
				self.charset = self._oldCharset
		else:
			logger.warning(f"Unknown charset negotiation response from peer: {data!r}")
			self.charset = self._oldCharset
			self.wont(CHARSET)
		del self._oldCharset

	def on_ga(self, *args: Union[bytes, None]) -> None:
		"""Called when a Go Ahead command is received."""
		promptTerminator: bytes = self.proxy.promptTerminator
		self.proxy.player.write(promptTerminator)

	def on_connectionMade(self) -> None:
		super().on_connectionMade()
		# Offer to handle charset.
		self.will(CHARSET)
		# Tell the Mume server to put IAC-GA at end of prompts.
		self.write(MPI_INIT + b"P2" + LF + b"G" + LF)

	def on_unhandledCommand(self, command: bytes, option: Union[bytes, None]) -> None:
		if option is None:
			self.proxy.player.write(IAC + command)
		else:
			self.proxy.player.write(IAC + command + option)

	def on_unhandledSubnegotiation(self, option: bytes, data: bytes) -> None:
		self.proxy.player.write(IAC + SB + option + data + IAC + SE)

	def on_enableLocal(self, option: bytes) -> bool:
		if option == CHARSET:
			logger.debug("Peer acknowledges our request and tells us to begin charset sub-negotiation.")
			self.negotiateCharset(self.charset)
			return True
		return super().on_enableLocal(option)

	def on_disableLocal(self, option: bytes) -> None:
		if option == CHARSET:
			return None
		super().on_disableLocal(option)


class ProxyHandler(object):
	def __init__(
		self,
		playerSocket: socket.socket,
		gameSocket: socket.socket,
		*,
		outputFormat: str,
		promptTerminator: Union[bytes, None],
		isEmulatingOffline: bool,
		mapperCommands: List[bytes],
		eventCaller: Callable[[EVENT_CALLER_TYPE], None],
	) -> None:
		self.outputFormat: str = outputFormat
		self.promptTerminator: bytes
		if promptTerminator is None:
			self.promptTerminator = IAC + GA
		else:
			self.promptTerminator = (
				promptTerminator.replace(CR_LF, LF)
				.replace(CR_NULL, CR)
				.replace(CR_NULL, CR)
				.replace(LF, CR_LF)
			)
		self.isEmulatingOffline: bool = isEmulatingOffline
		self.mapperCommands: List[bytes] = mapperCommands
		self.eventCaller: Callable[[EVENT_CALLER_TYPE], None] = eventCaller
		self.player: Manager = Manager(playerSocket.sendall, self.on_playerReceived)
		self.player.register(Player, proxy=self)  # type: ignore[misc]
		self.game: Manager = Manager(gameSocket.sendall, self.on_gameReceived)
		self.game.register(Game, proxy=self)  # type: ignore[misc]
		self.game.register(MPIProtocol, outputFormat=self.outputFormat)  # type: ignore[misc]
		self.game.register(
			XMLProtocol,  # type: ignore[misc]
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
			self.game.write(escapeIAC(data).replace(CR, CR_NULL).replace(LF, CR_LF))

	def on_gameReceived(self, data: bytes) -> None:
		self.player.write(escapeIAC(data).replace(CR, CR_NULL).replace(LF, CR_LF))
