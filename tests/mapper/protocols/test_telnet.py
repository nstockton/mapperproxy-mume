# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from typing import Tuple
from unittest import TestCase
from unittest.mock import Mock, patch

# Mapper Modules:
from mapper.protocols.telnet import TelnetProtocol
from mapper.protocols.telnet_constants import (
	COMMAND_BYTES,
	CR,
	CR_LF,
	CR_NULL,
	DO,
	DONT,
	ECHO,
	GA,
	IAC,
	LF,
	NEGOTIATION_BYTES,
	NULL,
	SB,
	SE,
	WILL,
	WONT,
)
from mapper.utils import escapeIAC


class TestTelnetProtocol(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.telnet: TelnetProtocol = TelnetProtocol(self.gameReceives.extend, self.playerReceives.extend)

	def tearDown(self) -> None:
		self.telnet.on_connectionLost()
		del self.telnet
		self.gameReceives.clear()
		self.playerReceives.clear()

	def newMockedOptionState(self) -> Mock:
		state: Mock = Mock()
		state.us.enabled = False
		state.us.negotiating = False
		state.him.enabled = False
		state.him.negotiating = False
		return state

	def parse(self, data: bytes) -> Tuple[bytes, bytes, str]:
		self.telnet.on_dataReceived(data)
		playerReceives: bytes = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives: bytes = bytes(self.gameReceives)
		self.gameReceives.clear()
		state: str = self.telnet.state
		self.telnet.state = "data"
		return playerReceives, gameReceives, state

	def testTelnetState(self) -> None:
		with self.assertRaises(ValueError):
			self.telnet.state = "**junk**"

	@patch("mapper.protocols.telnet.logger")
	def testTelnetWill(self, mockLogger: Mock) -> None:
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		usNegotiatingWarning: str = (
			f"We are offering to enable option {ECHO!r}, "
			+ "but the option is already being negotiated by us."
		)
		himNegotiatingWarning: str = (
			f"We are offering to enable option {ECHO!r}, "
			+ "but the option is already being negotiated by peer."
		)
		state.us.negotiating = True
		self.telnet.will(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(usNegotiatingWarning)
		mockLogger.reset_mock()
		state.us.negotiating = False
		state.him.negotiating = True
		self.telnet.will(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(himNegotiatingWarning)
		mockLogger.reset_mock()
		state.him.negotiating = False
		state.us.enabled = True
		self.telnet.will(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(
			f"Attempting to enable an already enabled option {ECHO!r}."
		)
		mockLogger.reset_mock()
		state.us.enabled = False
		self.telnet.will(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + WILL + ECHO))
		self.assertTrue(state.us.negotiating)

	@patch("mapper.protocols.telnet.logger")
	def testTelnetWont(self, mockLogger: Mock) -> None:
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		usNegotiatingWarning: str = (
			f"We are refusing to enable option {ECHO!r}, "
			+ "but the option is already being negotiated by us."
		)
		himNegotiatingWarning: str = (
			f"We are refusing to enable option {ECHO!r}, "
			+ "but the option is already being negotiated by peer."
		)
		state.us.negotiating = True
		self.telnet.wont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(usNegotiatingWarning)
		mockLogger.reset_mock()
		state.us.negotiating = False
		state.him.negotiating = True
		self.telnet.wont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(himNegotiatingWarning)
		mockLogger.reset_mock()
		state.him.negotiating = False
		state.us.enabled = False
		self.telnet.wont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(
			f"Attempting to disable an already disabled option {ECHO!r}."
		)
		mockLogger.reset_mock()
		state.us.enabled = True
		self.telnet.wont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + WONT + ECHO))
		self.assertTrue(state.us.negotiating)

	@patch("mapper.protocols.telnet.logger")
	def testTelnetDo(self, mockLogger: Mock) -> None:
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		usNegotiatingWarning: str = (
			f"We are requesting that peer enable option {ECHO!r}, "
			+ "but the option is already being negotiated by us."
		)
		himNegotiatingWarning: str = (
			f"We are requesting that peer enable option {ECHO!r}, "
			+ "but the option is already being negotiated by peer."
		)
		state.us.negotiating = True
		self.telnet.do(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(usNegotiatingWarning)
		mockLogger.reset_mock()
		state.us.negotiating = False
		state.him.negotiating = True
		self.telnet.do(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(himNegotiatingWarning)
		mockLogger.reset_mock()
		state.him.negotiating = False
		state.him.enabled = True
		self.telnet.do(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(
			f"Requesting that peer enable an already enabled option {ECHO!r}."
		)
		mockLogger.reset_mock()
		state.him.enabled = False
		self.telnet.do(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + DO + ECHO))
		self.assertTrue(state.him.negotiating)

	@patch("mapper.protocols.telnet.logger")
	def testTelnetDont(self, mockLogger: Mock) -> None:
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		usNegotiatingWarning: str = (
			f"We are requesting that peer disable option {ECHO!r}, "
			+ "but the option is already being negotiated by us."
		)
		himNegotiatingWarning: str = (
			f"We are requesting that peer disable option {ECHO!r}, "
			+ "but the option is already being negotiated by peer."
		)
		state.us.negotiating = True
		self.telnet.dont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(usNegotiatingWarning)
		mockLogger.reset_mock()
		state.us.negotiating = False
		state.him.negotiating = True
		self.telnet.dont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(himNegotiatingWarning)
		mockLogger.reset_mock()
		state.him.negotiating = False
		state.him.enabled = False
		self.telnet.dont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		mockLogger.warning.assert_called_once_with(
			f"Requesting that peer disable an already disabled option {ECHO!r}."
		)
		mockLogger.reset_mock()
		state.him.enabled = True
		self.telnet.dont(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + DONT + ECHO))
		self.assertTrue(state.him.negotiating)

	def testTelnetGetOptionState(self) -> None:
		self.assertNotIn(ECHO, self.telnet._options)
		self.telnet.getOptionState(ECHO)
		self.assertIn(ECHO, self.telnet._options)
		del self.telnet._options[ECHO]

	def testTelnetRequestNegotiation(self) -> None:
		data: bytes = IAC + b"hello"
		expected: bytes = IAC + SB + ECHO + escapeIAC(data) + IAC + SE
		self.telnet.requestNegotiation(ECHO, data)
		self.assertEqual(self.playerReceives, b"")
		self.assertEqual(self.gameReceives, expected)
		self.gameReceives.clear()
		self.assertEqual(self.telnet.state, "data")

	@patch("mapper.protocols.telnet.logger")
	@patch("mapper.protocols.telnet.TelnetProtocol.on_subnegotiation")
	@patch("mapper.protocols.telnet.TelnetProtocol.on_command")
	def testTelnetOn_dataReceived(
		self,
		mockOn_command: Mock,
		mockOn_subnegotiation: Mock,
		mockLogger: Mock,
	) -> None:
		# 'data' state:
		data: bytes = b"Hello World!"
		self.telnet.on_connectionMade()
		self.assertEqual(self.parse(data), (data, b"", "data"))
		self.assertEqual(self.parse(data + IAC), (data, b"", "command"))
		self.assertEqual(self.parse(data + CR), (data, b"", "newline"))
		self.assertEqual(self.parse(data + CR_LF), (data + LF, b"", "data"))
		self.assertEqual(self.parse(data + CR_NULL), (data + CR, b"", "data"))
		self.assertEqual(self.parse(data + CR + IAC), (data + CR, b"", "command"))
		# 'command' and 'negotiation' states:
		self.assertEqual(self.parse(data + IAC + IAC), (data + IAC, b"", "data"))
		self.assertEqual(self.parse(data + IAC + SE), (data, b"", "data"))
		mockLogger.warning.assert_called_once_with("IAC SE received outside of subnegotiation.")
		mockLogger.reset_mock()
		self.assertEqual(self.parse(data + IAC + SB), (data, b"", "subnegotiation"))
		for byte in COMMAND_BYTES:
			self.assertEqual(self.parse(data + IAC + byte), (data, b"", "data"))
			mockOn_command.assert_called_once_with(byte, None)
			mockOn_command.reset_mock()
		for byte in NEGOTIATION_BYTES:
			self.assertEqual(self.parse(data + IAC + byte), (data, b"", "negotiation"))
			self.assertEqual(self.parse(data + IAC + byte + ECHO), (data, b"", "data"))
			mockOn_command.assert_called_once_with(byte, ECHO)
			mockOn_command.reset_mock()
		self.assertEqual(self.parse(data + IAC + NULL), (data, b"", "data"))
		mockLogger.warning.assert_called_once_with(f"Unknown Telnet command received {NULL!r}.")
		mockLogger.reset_mock()
		# 'newline' state:
		# This state is entered when a packet ends in CR (I.E. when new lines are broken over two packets).
		self.telnet.on_dataReceived(data + CR)
		self.assertEqual(self.parse(LF), (data + LF, b"", "data"))
		self.telnet.on_dataReceived(data + CR)
		self.assertEqual(self.parse(NULL), (data + CR, b"", "data"))
		self.telnet.on_dataReceived(data + CR)
		self.assertEqual(self.parse(IAC), (data + CR, b"", "command"))
		self.telnet.on_dataReceived(data + CR)
		self.assertEqual(self.parse(ECHO), (data + CR + ECHO, b"", "data"))
		# 'subnegotiation' state:
		self.assertEqual(self.parse(data + IAC + SB + IAC), (data, b"", "subnegotiation-escaped"))
		self.assertEqual(self.parse(data + IAC + SB + b"something"), (data, b"", "subnegotiation"))
		self.assertEqual(b"".join(self.telnet._commands), b"something")
		del self.telnet._commands
		# 'subnegotiation-escaped' state:
		self.assertEqual(self.parse(data + IAC + SB + ECHO + b"something" + IAC + SE), (data, b"", "data"))
		mockOn_subnegotiation.assert_called_once_with(ECHO, b"something")
		mockOn_subnegotiation.reset_mock()
		self.assertEqual(
			self.parse(data + IAC + SB + ECHO + b"something" + IAC + IAC + IAC + SE), (data, b"", "data")
		)
		mockOn_subnegotiation.assert_called_once_with(ECHO, b"something" + IAC)
		# Invalid state: This should never happen.
		self.telnet._state = "**junk**"
		self.assertEqual(self.parse(data), (data, b"", "data"))
		mockLogger.warning.assert_called_once_with("Invalid Telnet state '**junk**'. How'd you do this?")

	@patch("mapper.protocols.telnet.TelnetProtocol.on_unhandledCommand")
	def testTelnetOn_command(self, mockOn_unhandledCommand: Mock) -> None:
		mockCommandMapGA = Mock()
		self.telnet.commandMap[GA] = mockCommandMapGA
		self.telnet.on_command(GA, NULL)
		mockCommandMapGA.assert_called_once_with(NULL)
		self.telnet.on_command(ECHO, NULL)
		mockOn_unhandledCommand.assert_called_once_with(ECHO, NULL)

	@patch("mapper.protocols.telnet.TelnetProtocol.on_unhandledSubnegotiation")
	def testTelnetOn_subnegotiation(self, mockOn_unhandledSubnegotiation: Mock) -> None:
		mockSubnegotiationMapGA = Mock()
		self.telnet.subnegotiationMap[GA] = mockSubnegotiationMapGA
		self.telnet.on_subnegotiation(GA, NULL)
		mockSubnegotiationMapGA.assert_called_once_with(NULL)
		self.telnet.on_subnegotiation(ECHO, NULL)
		mockOn_unhandledSubnegotiation.assert_called_once_with(ECHO, NULL)

	@patch("mapper.protocols.telnet.TelnetProtocol.on_enableRemote")
	def testTelnetOn_will(self, mockOn_enableRemote: Mock) -> None:
		with self.assertRaises(AssertionError):
			self.telnet.on_will(None)
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		# --------------------
		# not state.him.enabled and not state.him.negotiating:
		# --------------------
		self.assertFalse(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		mockOn_enableRemote.return_value = True
		self.telnet.on_will(ECHO)
		self.assertTrue(state.him.enabled)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + DO + ECHO))
		self.gameReceives.clear()
		state.him.enabled = False
		mockOn_enableRemote.return_value = False
		self.telnet.on_will(ECHO)
		self.assertFalse(state.him.enabled)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + DONT + ECHO))
		self.gameReceives.clear()
		# --------------------
		# not state.him.enabled and state.him.negotiating:
		# --------------------
		state.him.negotiating = True
		mockOn_enableRemote.return_value = True
		self.telnet.on_will(ECHO)
		self.assertTrue(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		state.him.enabled = False
		state.him.negotiating = True
		mockOn_enableRemote.return_value = False
		with self.assertRaises(AssertionError):
			self.telnet.on_will(ECHO)
		self.assertTrue(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# state.him.enabled and not state.him.negotiating:
		# --------------------
		self.telnet.on_will(ECHO)
		self.assertTrue(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# state.him.enabled and state.him.negotiating:
		# --------------------
		state.him.negotiating = True
		with self.assertRaises(AssertionError):
			self.telnet.on_will(ECHO)

	@patch("mapper.protocols.telnet.logger")
	@patch("mapper.protocols.telnet.TelnetProtocol.on_disableRemote")
	def testTelnetOn_wont(self, mockOn_disableRemote: Mock, mockLogger: Mock) -> None:
		with self.assertRaises(AssertionError):
			self.telnet.on_wont(None)
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		# --------------------
		# not state.him.enabled and not state.him.negotiating:
		# --------------------
		self.assertFalse(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		self.telnet.on_wont(ECHO)
		self.assertFalse(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# not state.him.enabled and state.him.negotiating:
		# --------------------
		state.him.negotiating = True
		self.telnet.on_wont(ECHO)
		self.assertFalse(state.him.negotiating)
		mockLogger.debug.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# state.him.enabled and not state.him.negotiating:
		# --------------------
		state.him.enabled = True
		self.telnet.on_wont(ECHO)
		self.assertFalse(state.him.enabled)
		mockOn_disableRemote.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + DONT + ECHO))
		self.gameReceives.clear()
		# --------------------
		# state.him.enabled and state.him.negotiating:
		# --------------------
		state.him.enabled = True
		state.him.negotiating = True
		mockOn_disableRemote.reset_mock()
		self.telnet.on_wont(ECHO)
		self.assertFalse(state.him.enabled)
		self.assertFalse(state.him.negotiating)
		mockOn_disableRemote.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	@patch("mapper.protocols.telnet.TelnetProtocol.on_enableLocal")
	def testTelnetOn_do(self, mockOn_enableLocal: Mock) -> None:
		with self.assertRaises(AssertionError):
			self.telnet.on_do(None)
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		# --------------------
		# not state.us.enabled and not state.us.negotiating:
		# --------------------
		self.assertFalse(state.us.enabled)
		self.assertFalse(state.us.negotiating)
		mockOn_enableLocal.return_value = True
		self.telnet.on_do(ECHO)
		self.assertTrue(state.us.enabled)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + WILL + ECHO))
		self.gameReceives.clear()
		state.us.enabled = False
		mockOn_enableLocal.return_value = False
		self.telnet.on_do(ECHO)
		self.assertFalse(state.us.enabled)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + WONT + ECHO))
		self.gameReceives.clear()
		# --------------------
		# not state.us.enabled and state.us.negotiating:
		# --------------------
		state.us.negotiating = True
		mockOn_enableLocal.reset_mock()
		self.telnet.on_do(ECHO)
		self.assertTrue(state.us.enabled)
		self.assertFalse(state.us.negotiating)
		mockOn_enableLocal.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# state.us.enabled and not state.us.negotiating:
		# --------------------
		self.telnet.on_do(ECHO)
		self.assertTrue(state.us.enabled)
		self.assertFalse(state.us.negotiating)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# state.us.enabled and state.us.negotiating:
		# --------------------
		state.us.negotiating = True
		with self.assertRaises(AssertionError):
			self.telnet.on_do(ECHO)

	@patch("mapper.protocols.telnet.logger")
	@patch("mapper.protocols.telnet.TelnetProtocol.on_disableLocal")
	def testTelnetOn_dont(self, mockOn_disableLocal: Mock, mockLogger: Mock) -> None:
		with self.assertRaises(AssertionError):
			self.telnet.on_dont(None)
		state: Mock = self.newMockedOptionState()
		self.telnet._options[ECHO] = state
		# --------------------
		# not state.us.enabled and not state.us.negotiating:
		# --------------------
		self.assertFalse(state.us.enabled)
		self.assertFalse(state.us.negotiating)
		self.telnet.on_dont(ECHO)
		self.assertFalse(state.us.enabled)
		self.assertFalse(state.us.negotiating)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# not state.us.enabled and state.us.negotiating:
		# --------------------
		state.us.negotiating = True
		self.telnet.on_dont(ECHO)
		self.assertFalse(state.us.negotiating)
		mockLogger.debug.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		# --------------------
		# state.us.enabled and not state.us.negotiating:
		# --------------------
		state.us.enabled = True
		self.telnet.on_dont(ECHO)
		self.assertFalse(state.us.enabled)
		mockOn_disableLocal.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", IAC + WONT + ECHO))
		self.gameReceives.clear()
		# --------------------
		# state.us.enabled and state.us.negotiating:
		# --------------------
		state.us.enabled = True
		state.us.negotiating = True
		mockOn_disableLocal.reset_mock()
		self.telnet.on_dont(ECHO)
		self.assertFalse(state.us.enabled)
		self.assertFalse(state.us.negotiating)
		mockOn_disableLocal.assert_called_once()
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	def testTelnetOn_unhandledCommand(self) -> None:
		self.telnet.on_unhandledCommand(ECHO, NULL)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	def testTelnetOn_unhandledSubnegotiation(self) -> None:
		self.telnet.on_unhandledSubnegotiation(ECHO, NULL)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	def testTelnetOn_enableLocal(self) -> None:
		self.assertFalse(self.telnet.on_enableLocal(ECHO))
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	def testTelnetOn_enableRemote(self) -> None:
		self.assertFalse(self.telnet.on_enableRemote(ECHO))
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	def testTelnetOn_disableLocal(self) -> None:
		with self.assertRaises(NotImplementedError):
			self.telnet.on_disableLocal(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))

	def testTelnetOn_disableRemote(self) -> None:
		with self.assertRaises(NotImplementedError):
			self.telnet.on_disableRemote(ECHO)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
