# Copyright (c) 2025 Nick Stockton and contributors
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

# Mapper Modules:
from mapper.mapper import Mapper
from mapper.mudevents import Handler


class DummyHandler(Handler):
	event: str = "testEvent"
	handleText: Mock = Mock()

	def handle(self, text: str) -> None:
		self.handleText(f"I received {text}")


class HandlerWithoutType(Handler):
	def handle(self, text: str) -> None:
		pass


class TestHandler(TestCase):
	@patch.object(Mapper, "loadRooms", Mock())  # Speedup test execution.
	def setUp(self) -> None:
		logging.disable(logging.CRITICAL)
		self.mapper: Mapper = Mapper(
			playerSocket=Mock(spec=socket.socket),
			gameSocket=Mock(spec=socket.socket),
			outputFormat="normal",
			interface="text",
			promptTerminator=None,
			gagPrompts=False,
			findFormat="",
			isEmulatingOffline=False,
		)
		self.mapper.daemon = True  # Allow unittest to quit if mapper thread does not close properly.

	def tearDown(self) -> None:
		logging.disable(logging.NOTSET)

	def testMapper_handle(self) -> None:
		dummy: DummyHandler = DummyHandler(self.mapper)
		self.mapper.handleMudEvent(dummy.event, "Hello world")
		dummy.handleText.assert_called_once_with("I received Hello world")
		dummy.handleText.reset_mock()
		self.mapper.handleMudEvent(dummy.event, "I am here.")
		dummy.handleText.assert_called_once_with("I received I am here.")
		dummy.handleText.reset_mock()
		dummy.__del__()
		self.mapper.handleMudEvent(dummy.event, "Goodbye world")
		dummy.handleText.assert_not_called()

	def test_init_raisesValueErrorWhenNoEventTypeIsProvided(self) -> None:
		with self.assertRaises(ValueError):
			HandlerWithoutType(self.mapper)
