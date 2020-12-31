# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import socket
import unittest
from unittest.mock import Mock

# Mapper Modules:
from mapper.mapper import Mapper
from mapper.mudevents import Handler


class DummieHandler(Handler):
	event = "testEvent"

	def handle(self, data):
		self.mapper.queue.put("I received " + data)


class HandlerWithoutType(Handler):
	def handle(self, data):
		pass


class TestHandler(unittest.TestCase):
	def setUp(self):
		Mapper.loadRooms = Mock()  # to speed execution of tests
		self.mapper = Mapper(
			playerSocket=Mock(spec=socket.socket),
			gameSocket=Mock(spec=socket.socket),
			outputFormat="normal",
			interface="text",
			promptTerminator=None,
			gagPrompts=False,
			findFormat="",
			isEmulatingOffline=False,
		)
		self.mapper.daemon = (
			True  # this allows unittest to quit if the mapper thread does not close properly.
		)

	def testMapper_handle(self):
		self.mapper.queue = Mock()
		queue = self.mapper.queue
		dummieHandler = DummieHandler(self.mapper)

		self.mapper.handleMudEvent(dummieHandler.event, b"Hello world")
		queue.put.assert_called_once_with("I received Hello world")
		queue.put.reset_mock()

		self.mapper.handleMudEvent("testEvent", b"I am here.")
		queue.put.assert_called_once_with("I received I am here.")
		queue.put.reset_mock()

		dummieHandler.__del__()
		self.mapper.handleMudEvent("testEvent", b"Goodbye world")
		queue.put.assert_not_called()

	def test_init_raisesValueErrorWhenNoEventTypeIsProvided(self):
		self.assertRaises(ValueError, HandlerWithoutType, self.mapper)
