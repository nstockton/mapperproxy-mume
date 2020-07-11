# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from typing import Sequence, Union

# Local Modules:
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
from .. import USER_DATA
from ..utils import escapeIAC


logger: logging.Logger = logging.getLogger(__name__)


class Telnet(TelnetProtocol):
	"""
	Attributes:
		name: The name of this side of the connection. Can be 'game' or 'player'.
		proxy: The proxy that spawned this object.
	"""

	def __init__(self, name: str, proxy: "ProxyHandler", *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.name: str = name.lower()
		if self.name not in ("player", "game"):
			raise ValueError("Name must be 'player' or 'game'")
		self.proxy: "ProxyHandler" = proxy

	def on_command(self, command: bytes, option: Union[bytes, None]) -> None:
		if command in NEGOTIATION_BYTES and option not in self.subnegotiationMap:
			# Treat any unhandled negotiation options the same as unhandled commands, so
			# they are forwarded to the other end of the proxy.
			self.on_unhandledCommand(command, option)
		else:
			super().on_command(command, option)


class Player(Telnet):
	def __init__(self, *args, **kwargs):
		super().__init__("player", *args, **kwargs)

	def on_unhandledCommand(self, command: bytes, option: Union[bytes, None]) -> None:
		if option is None:
			self.proxy.game.write(IAC + command)
		else:
			self.proxy.game.write(IAC + command + option)

	def on_unhandledSubnegotiation(self, option: bytes, data: bytes) -> None:
		self.proxy.game.write(IAC + SB + option + data + IAC + SE)

	def on_enableLocal(self, option: bytes) -> bool:
		if option in self.proxy.game._handlers[0].subnegotiationMap:
			return False
		return super().on_enableLocal(option)


class Game(Telnet):
	charsets: Sequence[bytes] = (
		b"US-ASCII",
		b"ISO-8859-1",
		b"UTF-8",
	)
	"""Supported character sets."""

	def __init__(self, *args, **kwargs):
		super().__init__("game", *args, **kwargs)
		self.commandMap[GA] = self.on_ga
		self.subnegotiationMap[CHARSET] = self.on_charset

	@property
	def charset(self) -> bytes:
		"""The character set to be used."""
		return getattr(self, "_charset", self.charsets[0])

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

	def on_ga(self, *args) -> None:
		"""Called when a Go Ahead command is received."""
		self.proxy.player.write(self.proxy.promptTerminator)

	def on_connectionMade(self):
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
			return
		super().on_disableLocal(option)


class ProxyHandler(object):
	def __init__(self, playerSocket, gameSocket, **kwargs):
		self.outputFormat = kwargs["outputFormat"]
		self.promptTerminator = kwargs["promptTerminator"] or IAC + GA
		self.promptTerminator = self.promptTerminator.replace(CR_LF, LF).replace(CR_NULL, CR)
		self.promptTerminator = self.promptTerminator.replace(CR_NULL, CR).replace(LF, CR_LF)
		self.isEmulatingOffline = kwargs["isEmulatingOffline"]
		self.mapperCommands = kwargs["mapperCommands"]
		self.eventCaller = kwargs["eventCaller"]
		self.player = Manager(playerSocket.sendall, self.on_playerReceived)
		self.player.register(Player, self)
		self.game = Manager(gameSocket.sendall, self.on_gameReceived)
		self.game.register(Game, self)
		self.game.register(MPIProtocol, outputFormat=self.outputFormat)
		self.game.register(XMLProtocol, outputFormat=self.outputFormat, eventCaller=self.eventCaller)

	def close(self):
		self.disconnect()

	def connect(self):
		self.player.connect()
		self.game.connect()

	def disconnect(self):
		self.game.disconnect()
		self.player.disconnect()

	def on_playerReceived(self, data):
		if self.isEmulatingOffline or b"".join(data.strip().split()[:1]) in self.mapperCommands:
			self.eventCaller((USER_DATA, data))
		else:
			self.game.write(escapeIAC(data).replace(CR, CR_NULL).replace(LF, CR_LF))

	def on_gameReceived(self, data):
		self.player.write(escapeIAC(data).replace(CR, CR_NULL).replace(LF, CR_LF))
