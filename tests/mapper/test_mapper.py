# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import socket
from collections.abc import Generator
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import Mock, _CallList, call, patch

# Mapper Modules:
from mapper.mapper import Mapper
from mapper.typedef import MAPPER_QUEUE_EVENT_TYPE


class TestMapper(TestCase):
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

	def testMapper_run(self) -> None:
		cm: ExitStack
		with ExitStack() as cm:
			mockHandleMudEvent: Mock = cm.enter_context(patch.object(self.mapper, "handleMudEvent"))
			mockHandleUserInput: Mock = cm.enter_context(patch.object(self.mapper, "handleUserInput"))
			self.mapper.start()
			# feed data into the mapper queue
			testMapperInput: tuple[MAPPER_QUEUE_EVENT_TYPE, ...] = (
				("line", b"Welcome to mume"),
				("prompt", b"hp:hurt mana:burning>"),
				("userInput", b"rinfo"),
				("userInput", b"emu go lorien"),
				("userInput", b"not_a_user_command"),
				("movement", b"east"),
				("userInput", b"run ingrove"),
				("not_an_event", b"good bype world"),
				None,
			)
			for item in testMapperInput:
				self.mapper.queue.put(item)
			# insure that the mapper closes properly
			self.mapper.join(1)
			self.assertFalse(self.mapper.is_alive(), "mapper thread took longer than a second to quit")
			self.assertTrue(self.mapper.queue.empty(), "mapper queue is not empty after thread termination")
			# validate calls to handleUserInput
			userCalls: _CallList = mockHandleUserInput.mock_calls
			self.assertEqual(len(userCalls), 4)
			self.assertEqual(
				userCalls[0], call("rinfo"), "First call to handleUserInput was not as expected."
			)
			self.assertEqual(
				userCalls[1], call("emu go lorien"), "Second call to handleUserInput was not as expected."
			)
			self.assertEqual(
				userCalls[2], call("not_a_user_command"), "Third handleUserInput was not as expected."
			)
			self.assertEqual(
				userCalls[3], call("run ingrove"), "Fourth call to handleUserInput was not as expected."
			)
			# validate calls to handleMudEvent
			serverCalls: _CallList = mockHandleMudEvent.mock_calls
			self.assertEqual(len(serverCalls), 4)
			self.assertEqual(
				serverCalls[0], call("line", "Welcome to mume"), "handleMudEvent #0 not expected."
			)
			self.assertEqual(serverCalls[1], call("prompt", "hp:hurt mana:burning>"), "Second handleMudEvent")
			self.assertEqual(serverCalls[2], call("movement", "east"), "Third handleMudEvent not as expected")
			self.assertEqual(serverCalls[3], call("not_an_event", "good bype world"), "Fourth handleMudEvent")

	def testMapper_handleUserInput(self) -> None:
		validUserInput: tuple[tuple[str, str, str], ...] = (
			("rinfo", "user_command_rinfo", ""),
			("rlabel add here", "user_command_rlabel", "add here"),
			("emu go emoria", "user_command_emu", "go emoria"),
		)
		for command, handlerName, args in validUserInput:
			handler: Mock
			with patch.object(self.mapper, handlerName) as handler:
				self.mapper.handleUserInput(command)
				handler.assert_called_with(args)
		junkUserInput: tuple[str, ...] = (
			"not_a_command",
			"test failure",
			"rinf",
		)
		for command in junkUserInput:
			with self.assertRaises(AttributeError):
				self.mapper.handleUserInput(command)


class TestMapper_handleMudEvent(TestCase):
	@patch.object(Mapper, "loadRooms", Mock())  # Speedup test execution.
	def setUp(self) -> None:
		logging.disable(logging.CRITICAL)
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

	def tearDown(self) -> None:
		logging.disable(logging.NOTSET)

	def test_legacyMudEventHandlers(self) -> None:
		events: Generator[str, None, None] = (
			handlerName[len("mud_event_") :] for handlerName in self.legacyHandlerNames
		)
		handlers: Generator[Mock, None, None] = (
			getattr(self.mapper, handlerName) for handlerName in self.legacyHandlerNames
		)
		for event, handler in zip(events, handlers):
			sampleInput1: str = "Helol oje"
			sampleInput2: str = "no sir, away. a papaya war is on"
			sampleInput3: str = "delting no sir, away. a papaya war is on"
			self.mapper.registerMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput1)
			handler.assert_called_once_with(sampleInput1)
			handler.reset_mock()
			self.mapper.handleMudEvent(event, sampleInput2)
			handler.assert_called_once_with(sampleInput2)
			handler.reset_mock()
			self.mapper.deregisterMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput3)
			handler.assert_not_called()

	def test_newMudEventHandlers(self) -> None:
		events: tuple[str, ...] = (
			"sillyEvent",
			"room",
			"otherEvent",
		)
		for event in events:
			handler: Mock = Mock()
			sampleInput1: str = "Helol oje"
			sampleInput2: str = "no sir, away. a papaya war is on"
			sampleInput3: str = "delting no sir, away. a papaya war is on"
			self.mapper.registerMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput1)
			handler.assert_called_once_with(sampleInput1)
			handler.reset_mock()
			self.mapper.handleMudEvent(event, sampleInput2)
			handler.assert_called_once_with(sampleInput2)
			handler.reset_mock()
			self.mapper.deregisterMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput3)
			handler.assert_not_called()

	def test_handleMudEvent_failsGracefullyWhenHandlingAnUnknownEvent(self) -> None:
		unknownEvents: tuple[str, ...] = (
			"unkk",
			"New_game_event",
			"room",
			"<interesting-tag-<in>-a-tag>",
		)
		for unknownEvent in unknownEvents:
			# simply require this to execute without raising an exception
			self.mapper.handleMudEvent(unknownEvent, "meaningless input")
