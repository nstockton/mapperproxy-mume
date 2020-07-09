# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase, mock

# Mapper Modules:
from mapper.protocols.base import Protocol
from mapper.protocols.manager import Manager
from mapper.protocols.telnet_constants import CR, CR_LF, CR_NULL, IAC, LF


class Protocol1(Protocol):
	pass


class Protocol2(Protocol):
	on_connectionMade = mock.Mock()
	on_connectionLost = mock.Mock()
	on_dataReceived = mock.Mock()

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._receiver = mock.Mock()


class TestManager(TestCase):
	def setUp(self):
		self.gameReceives = bytearray()
		self.playerReceives = bytearray()
		self.manager = Manager(self.gameReceives.extend, self.playerReceives.extend)

	def tearDown(self):
		self.manager.disconnect()
		del self.manager
		self.gameReceives.clear()
		self.playerReceives.clear()

	def parse(self, data):
		self.manager.parse(data)
		playerReceives = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives = bytes(self.gameReceives)
		self.gameReceives.clear()
		return playerReceives, gameReceives

	@mock.patch("mapper.protocols.manager.Manager.disconnect")
	@mock.patch("mapper.protocols.manager.Manager.connect")
	def testManagerAsContextManager(self, mockConnect, mockDisconnect):
		with self.manager:
			self.manager.connect.assert_called_once()
		self.manager.disconnect.assert_called_once()

	@mock.patch("mapper.protocols.manager.Manager.disconnect")
	def testManagerClose(self, mockDisconnect):
		self.manager.close()
		self.manager.disconnect.assert_called_once()

	def testManagerParse(self):
		data = b"Hello World!"
		bufferedData = b"Some buffered data."
		# Make sure that any data passed to Manager.parse before calling Manager.connect() gets buffered.
		self.assertEqual(self.parse(bufferedData), (b"", b""))
		self.manager.connect()
		# Make sure that any data passed to Manager.parse before registering a protocol gets buffered.
		self.assertEqual(self.parse(bufferedData), (b"", b""))
		self.manager.register(Protocol)
		self.assertEqual(self.parse(data), (bufferedData + bufferedData + data, b""))

	def testManagerWrite(self):
		data = b"Hello World!"
		bufferedData = b"Some buffered data."
		# Make sure that any data passed to Manager.write before calling Manager.connect() gets buffered.
		self.manager.write(bufferedData)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		self.manager.connect()
		# Make sure that any data passed to Manager.write before registering a protocol gets buffered.
		self.manager.write(bufferedData)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", b""))
		self.manager.register(Protocol)
		self.manager.write(data)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", bufferedData + bufferedData + data))
		self.gameReceives.clear()
		# Make sure IAC bytes are escaped and line endings are normalized if the escape argument is given.
		self.manager.write(data + IAC + LF + CR, escape=True)
		self.assertEqual((self.playerReceives, self.gameReceives), (b"", data + IAC + IAC + CR_LF + CR_NULL))

	def testManagerRegister(self):
		with self.assertRaises(ValueError):
			self.manager.register(Protocol1(lambda *args: None, lambda *args: None))
		self.manager.register(Protocol1)
		with self.assertRaises(ValueError):
			self.manager.register(Protocol1)
		self.assertIsNot(self.manager._handlers[0]._receiver, Protocol2.on_dataReceived)
		self.manager.register(Protocol2)
		self.assertIs(self.manager._handlers[0]._receiver, self.manager._handlers[1].on_dataReceived)
		self.manager._handlers[1].on_connectionMade.assert_called_once()

	def testManagerUnregister(self):
		self.manager.register(Protocol1)
		with self.assertRaises(ValueError):
			# Manager.unregister requires an instance.
			self.manager.unregister(Protocol1)
		with self.assertRaises(ValueError):
			# Calling Manager.unregister on an instance that was not registered.
			self.manager.unregister(Protocol2(lambda *args: None, lambda *args: None))
		self.manager.register(Protocol2)
		instance = self.manager._handlers[-1]
		self.assertIsNot(self.manager._handlers[0]._receiver, instance._receiver)
		self.manager.unregister(instance)
		self.assertIs(self.manager._handlers[0]._receiver, instance._receiver)
		instance.on_connectionLost.assert_called_once()
