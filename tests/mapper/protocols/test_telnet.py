# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase

# Mapper Modules:
from mapper.protocols.telnet import TelnetProtocol
from mapper.protocols.telnet_constants import CR, CR_LF, CR_NULL, GA, IAC, LF


class TestTelnetProtocol(TestCase):
	def setUp(self):
		self.gameReceives = bytearray()
		self.playerReceives = bytearray()
		self.telnet = TelnetProtocol(self.gameReceives.extend, self.playerReceives.extend)

	def tearDown(self):
		self.telnet.on_connectionLost()
		del self.telnet
		self.gameReceives.clear()
		self.playerReceives.clear()

	def parse(self, data):
		self.telnet.on_dataReceived(data)
		playerReceives = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives = bytes(self.gameReceives)
		self.gameReceives.clear()
		state = self.telnet.state
		self.telnet.state = "data"
		return playerReceives, gameReceives, state

	def testTelnetDataReceived(self):
		data = b"Hello World!"
		self.assertEqual(self.playerReceives, b"")
		self.assertEqual(self.gameReceives, b"")
		self.assertEqual(self.telnet.state, "data")
		self.telnet.on_connectionMade()
		self.assertEqual(self.parse(data), (data, b"", "data"))
		self.assertEqual(self.parse(data + CR), (data, b"", "newline"))
		self.assertEqual(self.parse(data + CR_LF), (data + LF, b"", "data"))
		self.assertEqual(self.parse(data + CR_NULL), (data + CR, b"", "data"))
		self.assertEqual(self.parse(data + CR + IAC), (data + CR, b"", "command"))
		# Test if telnet negotiations are being properly filtered out.
		self.assertEqual(self.parse(IAC + GA + data + IAC + IAC + IAC + GA), (data + IAC, b"", "data"))
