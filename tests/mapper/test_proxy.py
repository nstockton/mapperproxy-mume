# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import socket
from unittest import TestCase
from unittest.mock import Mock, patch

# Third-party Modules:
from mudproto.mpi import MPI_INIT
from mudproto.telnet import IAC_IAC
from mudproto.telnet_constants import CR_LF, CR_NULL, ECHO, GA, IAC, LF, SB, SE, WILL

# Mapper Modules:
from mapper.proxy import Game, Player, ProxyHandler, Telnet
from mapper.typedef import MUD_EVENT_TYPE


class TestTelnet(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.proxy: Mock = Mock()
		self.telnet: Telnet = Telnet(
			self.playerReceives.extend, self.gameReceives.extend, name="game", proxy=self.proxy, isClient=True
		)

	def tearDown(self) -> None:
		del self.telnet
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()

	def testTelnet__init__(self) -> None:
		with self.assertRaises(ValueError):
			Telnet(Mock(), Mock(), name="**junk**", proxy=Mock(), isClient=True)

	@patch("mapper.proxy.Telnet.on_unhandledCommand")
	@patch("mapper.proxy.TelnetProtocol.on_command")
	def testTelnetOn_command(self, mockOn_command: Mock, mockOn_unhandledCommand: Mock) -> None:
		self.assertNotIn(ECHO, self.telnet.subnegotiationMap)
		self.telnet.on_command(WILL, ECHO)
		mockOn_unhandledCommand.assert_called_once_with(WILL, ECHO)
		self.telnet.subnegotiationMap[ECHO] = Mock()
		self.telnet.on_command(WILL, ECHO)
		mockOn_command.assert_called_once_with(WILL, ECHO)
		del self.telnet.subnegotiationMap[ECHO]

	def testTelnetOn_unhandledCommand(self) -> None:
		self.telnet.name = "game"
		self.telnet.on_unhandledCommand(ECHO, None)
		self.proxy.player.write.assert_called_once_with(IAC + ECHO)
		self.proxy.player.write.reset_mock()
		self.telnet.on_unhandledCommand(WILL, ECHO)
		self.proxy.player.write.assert_called_once_with(IAC + WILL + ECHO)
		self.telnet.name = "player"
		self.telnet.on_unhandledCommand(ECHO, None)
		self.proxy.game.write.assert_called_once_with(IAC + ECHO)
		self.proxy.game.write.reset_mock()
		self.telnet.on_unhandledCommand(WILL, ECHO)
		self.proxy.game.write.assert_called_once_with(IAC + WILL + ECHO)

	def testTelnetOn_unhandledSubnegotiation(self) -> None:
		self.telnet.name = "game"
		self.telnet.on_unhandledSubnegotiation(ECHO, b"hello" + IAC)
		self.proxy.player.write.assert_called_once_with(IAC + SB + ECHO + b"hello" + IAC_IAC + IAC + SE)
		self.telnet.name = "player"
		self.telnet.on_unhandledSubnegotiation(ECHO, b"hello" + IAC)
		self.proxy.game.write.assert_called_once_with(IAC + SB + ECHO + b"hello" + IAC_IAC + IAC + SE)


class TestPlayer(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.proxy: Mock = Mock()
		self.player: Player = Player(
			self.playerReceives.extend, self.gameReceives.extend, proxy=self.proxy, isClient=False
		)

	def tearDown(self) -> None:
		del self.player
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()

	@patch("mapper.proxy.Telnet.on_enableLocal")
	def testPlayerOn_enableLocal(self, mockOn_enableLocal: Mock) -> None:
		self.proxy.game._handlers = [Mock()]
		self.proxy.game._handlers[0].subnegotiationMap = {ECHO: None}
		self.assertFalse(self.player.on_enableLocal(ECHO))
		self.proxy.game._handlers[0].subnegotiationMap.clear()
		self.player.on_enableLocal(ECHO)
		mockOn_enableLocal.assert_called_once_with(ECHO)


class TestGame(TestCase):
	def setUp(self) -> None:
		logging.disable(logging.CRITICAL)
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.proxy: Mock = Mock()
		self.game: Game = Game(
			self.gameReceives.extend, self.playerReceives.extend, proxy=self.proxy, isClient=True
		)

	def tearDown(self) -> None:
		logging.disable(logging.NOTSET)
		del self.game
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()

	def testGameOn_ga(self) -> None:
		self.game.on_ga(None)
		self.proxy.player.write.assert_called_once_with(b"", prompt=True)

	@patch("mapper.proxy.Telnet.on_connectionMade")
	def testGameOn_connectionMade(self, mockOn_connectionMade: Mock) -> None:
		self.game.on_connectionMade()
		mockOn_connectionMade.assert_called_once()
		self.assertEqual(self.gameReceives, MPI_INIT + b"P2" + LF + b"G" + LF)


class TestProxyHandler(TestCase):
	def setUp(self) -> None:
		logging.disable(logging.CRITICAL)
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.mapperEvents: list[MUD_EVENT_TYPE] = []
		playerSocket: Mock = Mock(spec=socket.socket)
		playerSocket.sendall.side_effect = lambda data: self.playerReceives.extend(data)
		gameSocket: Mock = Mock(spec=socket.socket)
		gameSocket.sendall.side_effect = lambda data: self.gameReceives.extend(data)
		self.proxy: ProxyHandler = ProxyHandler(
			playerSocket.sendall,
			gameSocket.sendall,
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
		logging.disable(logging.NOTSET)
		self.proxy.disconnect()
		del self.proxy
		self.gameReceives.clear()
		self.playerReceives.clear()
		self.mapperEvents.clear()

	def parse(self, name: str, data: bytes) -> tuple[bytes, bytes]:
		getattr(self.proxy, name).parse(data)
		playerReceives: bytes = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives: bytes = bytes(self.gameReceives)
		self.gameReceives.clear()
		return playerReceives, gameReceives

	@patch("mapper.proxy.ProxyHandler.disconnect")
	def testProxyHandlerClose(self, mockDisconnect: Mock) -> None:
		self.proxy.close()
		mockDisconnect.assert_called_once()

	def testProxyHandlerOn_playerReceived(self) -> None:
		data: bytes = b"Hello world!"
		self.proxy.isEmulatingOffline = False
		self.assertEqual(self.parse("player", data), (b"", b""))
		self.assertEqual(self.parse("player", LF), (b"", data + CR_LF))
		self.assertFalse(self.mapperEvents)
		self.assertEqual(self.parse("player", b"testCommand " + data + LF), (b"", b""))
		self.assertEqual(self.mapperEvents, [("userInput", b"testCommand " + data + LF)])
		self.mapperEvents.clear()
		self.proxy.isEmulatingOffline = True
		self.assertEqual(self.parse("player", data + LF), (b"", b""))
		self.assertEqual(self.mapperEvents, [("userInput", data + LF)])

	def testProxyHandlerOn_gameReceived(self) -> None:
		data: bytes = b"Hello world!"
		self.assertEqual(
			self.parse("game", data + IAC + IAC + CR_LF + CR_NULL), (data + IAC + IAC + CR_LF + CR_NULL, b"")
		)
