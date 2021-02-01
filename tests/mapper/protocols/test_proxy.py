# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import socket
from typing import Any, List, Tuple
from unittest import TestCase
from unittest.mock import Mock, patch

# Mapper Modules:
from mapper import USER_DATA
from mapper.protocols.mpi import MPI_INIT
from mapper.protocols.proxy import Game, Player, ProxyHandler, Telnet
from mapper.protocols.telnet_constants import (
	CHARSET,
	CHARSET_ACCEPTED,
	CHARSET_REJECTED,
	CHARSET_REQUEST,
	CR_LF,
	CR_NULL,
	ECHO,
	GA,
	IAC,
	LF,
	SB,
	SE,
	WILL,
)


EVENT_TYPE = Tuple[int, Tuple[str, bytes]]


class TestTelnet(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.proxy: Mock = Mock()
		self.telnet: Telnet = Telnet(
			self.playerReceives.extend, self.gameReceives.extend, name="game", proxy=self.proxy
		)

	def tearDown(self) -> None:
		del self.telnet
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()

	def testTelnet__init__(self) -> None:
		with self.assertRaises(ValueError):
			Telnet(Mock(), Mock(), name="**junk**", proxy=Mock())

	@patch("mapper.protocols.proxy.Telnet.on_unhandledCommand")
	@patch("mapper.protocols.proxy.TelnetProtocol.on_command")
	def testTelnetOn_command(self, mockOn_command: Mock, mockOn_unhandledCommand: Mock) -> None:
		self.assertNotIn(CHARSET, self.telnet.subnegotiationMap)
		self.telnet.subnegotiationMap[CHARSET] = Mock()
		self.telnet.on_command(WILL, ECHO)
		mockOn_unhandledCommand.assert_called_once_with(WILL, ECHO)
		self.telnet.on_command(WILL, CHARSET)
		mockOn_command.assert_called_once_with(WILL, CHARSET)
		del self.telnet.subnegotiationMap[CHARSET]


class TestPlayer(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.proxy: Mock = Mock()
		self.player: Player = Player(self.playerReceives.extend, self.gameReceives.extend, proxy=self.proxy)

	def tearDown(self) -> None:
		del self.player
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()

	def testPlayerOn_unhandledCommand(self) -> None:
		self.player.on_unhandledCommand(ECHO, None)
		self.proxy.game.write.assert_called_once_with(IAC + ECHO)
		self.proxy.game.write.reset_mock()
		self.player.on_unhandledCommand(WILL, ECHO)
		self.proxy.game.write.assert_called_once_with(IAC + WILL + ECHO)

	def testPlayerOn_unhandledSubnegotiation(self) -> None:
		self.player.on_unhandledSubnegotiation(ECHO, b"hello")
		self.proxy.game.write.assert_called_once_with(IAC + SB + ECHO + b"hello" + IAC + SE)

	@patch("mapper.protocols.proxy.Telnet.on_enableLocal")
	def testPlayerOn_enableLocal(self, mockOn_enableLocal: Mock) -> None:
		self.proxy.game._handlers = [Mock()]
		self.proxy.game._handlers[0].subnegotiationMap = {ECHO: None}
		self.assertFalse(self.player.on_enableLocal(ECHO))
		self.proxy.game._handlers[0].subnegotiationMap.clear()
		self.player.on_enableLocal(ECHO)
		mockOn_enableLocal.assert_called_once_with(ECHO)


class TestGame(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.proxy: Mock = Mock()
		self.game: Game = Game(self.gameReceives.extend, self.playerReceives.extend, proxy=self.proxy)

	def tearDown(self) -> None:
		del self.game
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()

	def testGameCharset(self) -> None:
		oldCharset: bytes = self.game.charset
		self.assertEqual(oldCharset, b"US-ASCII")
		with self.assertRaises(ValueError):
			self.game.charset = b"**junk**"
		self.assertEqual(self.game.charset, oldCharset)
		self.game.charset = b"UTF-8"
		self.assertEqual(self.game.charset, b"UTF-8")

	@patch("mapper.protocols.proxy.logger", Mock())
	def testGameNegotiateCharset(self) -> None:
		oldCharset: bytes = self.game.charset
		self.game.negotiateCharset(b"**junk**")
		self.assertEqual(
			self.gameReceives, IAC + SB + CHARSET + CHARSET_REQUEST + b";" + oldCharset + IAC + SE
		)
		self.gameReceives.clear()
		self.game.negotiateCharset(b"UTF-8")
		self.assertEqual(self.gameReceives, IAC + SB + CHARSET + CHARSET_REQUEST + b";" + b"UTF-8" + IAC + SE)

	@patch("mapper.protocols.proxy.Game.wont")
	@patch("mapper.protocols.proxy.logger")
	def testGameOn_charset(self, mockLogger: Mock, mockWont: Mock) -> None:
		# self.game.charset is the charset the user requested.
		self.game.charset = b"UTF-8"
		# self.game._oldCharset is the charset the user was using before the request.
		self.game._oldCharset = b"US-ASCII"
		# Charset accepted.
		self.game.on_charset(CHARSET_ACCEPTED + b"UTF-8")
		mockLogger.debug.assert_called_once_with("Peer responds: Charset b'UTF-8' accepted.")
		mockLogger.reset_mock()
		# Charset rejected, and _oldCharset and charset are the same.
		self.game._oldCharset = self.game.charset
		self.game.on_charset(CHARSET_REJECTED + b"UTF-8")
		mockLogger.warning.assert_called_with(
			f"Unable to fall back to {self.game.charset!r}. Old and new charsets match."
		)
		mockLogger.reset_mock()
		# Charset rejected, and _oldCharset and charset differ.
		self.game._oldCharset = b"US-ASCII"
		self.game.on_charset(CHARSET_REJECTED + b"UTF-8")
		mockLogger.debug.assert_called_once_with("Falling back to b'US-ASCII'.")
		self.assertEqual(self.game.charset, b"US-ASCII")
		self.game.charset = b"UTF-8"
		# Invalid response.
		self.game._oldCharset = b"US-ASCII"
		self.game.on_charset(b"**junk**")
		self.assertEqual(self.game.charset, b"US-ASCII")
		mockWont.assert_called_once_with(CHARSET)

	def testGameOn_ga(self) -> None:
		self.proxy.promptTerminator = CR_LF
		self.game.on_ga(None)
		self.proxy.player.write.assert_called_once_with(CR_LF)

	@patch("mapper.protocols.proxy.Telnet.on_connectionMade")
	def testGameOn_connectionMade(self, mockOn_connectionMade: Mock) -> None:
		self.game.on_connectionMade()
		mockOn_connectionMade.assert_called_once()
		self.assertEqual(self.gameReceives, IAC + WILL + CHARSET + MPI_INIT + b"P2" + LF + b"G" + LF)

	def testGameOn_unhandledCommand(self) -> None:
		self.game.on_unhandledCommand(ECHO, None)
		self.proxy.player.write.assert_called_once_with(IAC + ECHO)
		self.proxy.player.write.reset_mock()
		self.game.on_unhandledCommand(WILL, ECHO)
		self.proxy.player.write.assert_called_once_with(IAC + WILL + ECHO)

	def testGameOn_unhandledSubnegotiation(self) -> None:
		self.game.on_unhandledSubnegotiation(ECHO, b"hello")
		self.proxy.player.write.assert_called_once_with(IAC + SB + ECHO + b"hello" + IAC + SE)

	@patch("mapper.protocols.proxy.logger", Mock())
	@patch("mapper.protocols.proxy.Game.negotiateCharset")
	@patch("mapper.protocols.proxy.Telnet.on_enableLocal")
	def testGameOn_enableLocal(self, mockOn_enableLocal: Mock, mockNegotiateCharset: Mock) -> None:
		self.assertTrue(self.game.on_enableLocal(CHARSET))
		mockNegotiateCharset.assert_called_once_with(self.game.charset)
		self.game.on_enableLocal(ECHO)
		mockOn_enableLocal.assert_called_once_with(ECHO)

	@patch("mapper.protocols.proxy.Telnet.on_disableLocal")
	def testGameOn_disableLocal(self, mockOn_disableLocal: Mock) -> None:
		result: Any = getattr(self.game, "on_disableLocal")(CHARSET)  # Called like this to please MyPy.
		self.assertIsNone(result)
		self.game.on_disableLocal(ECHO)
		mockOn_disableLocal.assert_called_once_with(ECHO)


class TestProxyHandler(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.mapperEvents: List[EVENT_TYPE] = []
		playerSocket: Mock = Mock(spec=socket.socket)
		playerSocket.sendall.side_effect = lambda data: self.playerReceives.extend(data)
		gameSocket: Mock = Mock(spec=socket.socket)
		gameSocket.sendall.side_effect = lambda data: self.gameReceives.extend(data)
		self.proxy: ProxyHandler = ProxyHandler(
			playerSocket,
			gameSocket,
			outputFormat="normal",
			promptTerminator=IAC + GA,
			isEmulatingOffline=False,
			mapperCommands=[b"testCommand"],
			eventCaller=lambda *args: self.mapperEvents.append(*args),
		)
		self.proxy.connect()
		self.playerReceives.clear()
		self.gameReceives.clear()

	def tearDown(self) -> None:
		self.proxy.disconnect()
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()
		self.mapperEvents.clear()

	def parse(self, name: str, data: bytes) -> Tuple[bytes, bytes]:
		getattr(self.proxy, name).parse(data)
		playerReceives: bytes = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives: bytes = bytes(self.gameReceives)
		self.gameReceives.clear()
		return playerReceives, gameReceives

	@patch("mapper.protocols.proxy.ProxyHandler.disconnect")
	def testProxyHandlerClose(self, mockDisconnect: Mock) -> None:
		self.proxy.close()
		mockDisconnect.assert_called_once()

	def testProxyHandlerOn_playerReceived(self) -> None:
		data: bytes = b"Hello world!"
		self.proxy.isEmulatingOffline = False
		self.assertEqual(self.parse("player", data), (b"", data))
		self.assertFalse(self.mapperEvents)
		self.assertEqual(self.parse("player", b"testCommand " + data), (b"", b""))
		self.assertEqual(self.mapperEvents, [(USER_DATA, b"testCommand " + data)])
		self.mapperEvents.clear()
		self.proxy.isEmulatingOffline = True
		self.assertEqual(self.parse("player", data), (b"", b""))
		self.assertEqual(self.mapperEvents, [(USER_DATA, data)])

	def testProxyHandlerOn_gameReceived(self) -> None:
		data: bytes = b"Hello world!"
		self.assertEqual(
			self.parse("game", data + IAC + IAC + CR_LF + CR_NULL), (data + IAC + IAC + CR_LF + CR_NULL, b"")
		)
