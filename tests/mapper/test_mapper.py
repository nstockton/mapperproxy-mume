# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import socket
from contextlib import ExitStack
from typing import Generator, Tuple
from unittest import TestCase
from unittest.mock import Mock, _CallList, call, patch

# Mapper Modules:
from mapper import MAPPER_QUEUE_TYPE, MUD_DATA, USER_DATA
from mapper.mapper import Mapper


class TestMapper(TestCase):
	@patch.object(Mapper, "loadRooms", Mock())  # Speedup test execution.
	def setUp(self) -> None:
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

	def testMapper_run(self) -> None:
		cm: ExitStack
		with ExitStack() as cm:
			mockHandleMudEvent: Mock = cm.enter_context(patch.object(self.mapper, "handleMudEvent"))
			mockHandleUserData: Mock = cm.enter_context(patch.object(self.mapper, "handleUserData"))
			self.mapper.start()
			# feed data into the mapper queue
			testMapperInput: Tuple[MAPPER_QUEUE_TYPE, ...] = (
				(MUD_DATA, ("line", b"Welcome to mume")),
				(MUD_DATA, ("prompt", b"hp:hurt mana:burning>")),
				(USER_DATA, b"rinfo"),
				(USER_DATA, b"emu go lorien"),
				(USER_DATA, b"not_a_user_command"),
				(MUD_DATA, ("movement", b"east")),
				(USER_DATA, b"run ingrove"),
				(MUD_DATA, ("not_an_event", b"good bype world")),
				(None, None),
			)
			for item in testMapperInput:
				self.mapper.queue.put(item)
			# insure that the mapper closes properly
			self.mapper.join(1)
			self.assertFalse(self.mapper.is_alive(), "mapper thread took longer than a second to quit")
			self.assertTrue(self.mapper.queue.empty(), "mapper queue is not empty after thread termination")
			# validate calls to handleUserData
			userCalls: _CallList = mockHandleUserData.mock_calls
			self.assertEqual(len(userCalls), 4)
			self.assertEqual(
				userCalls[0], call(b"rinfo"), "First call to handleUserData was not as expected."
			)
			self.assertEqual(
				userCalls[1], call(b"emu go lorien"), "Second call to handleUserData was not as expected."
			)
			self.assertEqual(
				userCalls[2], call(b"not_a_user_command"), "Third handleUserData was not as expected."
			)
			self.assertEqual(
				userCalls[3], call(b"run ingrove"), "Fourth call to handleUserData was not as expected."
			)
			# validate calls to handleMudEvent
			serverCalls: _CallList = mockHandleMudEvent.mock_calls
			self.assertEqual(len(serverCalls), 4)
			self.assertEqual(
				serverCalls[0], call("line", b"Welcome to mume"), "handleMudEvent #0 not expected."
			)
			self.assertEqual(
				serverCalls[1], call("prompt", b"hp:hurt mana:burning>"), "Second handleMudEvent"
			)
			self.assertEqual(
				serverCalls[2], call("movement", b"east"), "Third handleMudEvent not as expected"
			)
			self.assertEqual(
				serverCalls[3], call("not_an_event", b"good bype world"), "Fourth handleMudEvent"
			)

	def testMapper_handleUserData(self) -> None:
		validUserInput: Tuple[Tuple[bytes, str, str], ...] = (
			(b"rinfo", "user_command_rinfo", ""),
			(b"rlabel add here", "user_command_rlabel", "add here"),
			(b"emu go emoria", "user_command_emu", "go emoria"),
		)
		for command, handlerName, args in validUserInput:
			handler: Mock
			with patch.object(self.mapper, handlerName) as handler:
				self.mapper.handleUserData(command)
				handler.assert_called_with(args)
		junkUserInput: Tuple[bytes, ...] = (
			b"not_a_command",
			b"test failure",
			b"rinf",
		)
		for command in junkUserInput:
			with self.assertRaises(AttributeError):
				self.mapper.handleUserData(command)


class TestMapper_handleMudEvent(TestCase):
	@patch.object(Mapper, "loadRooms", Mock())  # Speedup test execution.
	def setUp(self) -> None:
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
		self.mapper.daemon = True  # Allow unittest to quit if mapper thread does not close properly.
		self.legacyHandlerNames: Generator[str, None, None] = (
			handlerName
			for handlerName in dir(self.mapper)
			if handlerName.startswith("mud_event_") and callable(getattr(Mapper, handlerName))
		)
		for handlerName in self.legacyHandlerNames:
			setattr(self.mapper, handlerName, Mock())

	def test_legacyMudEventHandlers(self) -> None:
		events: Generator[str, None, None] = (
			handlerName[len("mud_event_") :] for handlerName in self.legacyHandlerNames
		)
		handlers: Generator[Mock, None, None] = (
			getattr(self.mapper, handlerName) for handlerName in self.legacyHandlerNames
		)
		for event, handler in zip(events, handlers):
			sampleInput1: bytes = b"Helol oje"
			sampleInput2: bytes = b"no sir, away. a papaya war is on"
			sampleInput3: bytes = b"delting no sir, away. a papaya war is on"
			self.mapper.registerMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput1)
			handler.assert_called_once_with(sampleInput1.decode("us-ascii"))
			handler.reset_mock()
			self.mapper.handleMudEvent(event, sampleInput2)
			handler.assert_called_once_with(sampleInput2.decode("us-ascii"))
			handler.reset_mock()
			self.mapper.deregisterMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput3)
			handler.assert_not_called()

	def test_newMudEventHandlers(self) -> None:
		events: Tuple[str, ...] = (
			"sillyEvent",
			"room",
			"otherEvent",
		)
		for event in events:
			handler: Mock = Mock()
			sampleInput1: bytes = b"Helol oje"
			sampleInput2: bytes = b"no sir, away. a papaya war is on"
			sampleInput3: bytes = b"delting no sir, away. a papaya war is on"
			self.mapper.registerMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput1)
			handler.assert_called_once_with(sampleInput1.decode("us-ascii"))
			handler.reset_mock()
			self.mapper.handleMudEvent(event, sampleInput2)
			handler.assert_called_once_with(sampleInput2.decode("us-ascii"))
			handler.reset_mock()
			self.mapper.deregisterMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput3)
			handler.assert_not_called()

	def test_handleMudEvent_failsGracefullyWhenHandlingAnUnknownEvent(self) -> None:
		unknownEvents: Tuple[str, ...] = (
			"unkk",
			"New_game_event",
			"room",
			"<interesting-tag-<in>-a-tag>",
		)
		for unknownEvent in unknownEvents:
			# simply require this to execute without raising an exception
			self.mapper.handleMudEvent(unknownEvent, b"meaningless input")
