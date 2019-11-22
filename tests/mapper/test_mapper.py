# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import unittest
from unittest.mock import call, Mock, patch

from mapper.mapper import Mapper, MUD_DATA, USER_DATA


class TestMapper(unittest.TestCase):
	def setUp(self):
		Mapper.loadRooms = Mock()  # to speed execution of tests
		self.mapper = Mapper(
			client=Mock(),
			server=None,
			outputFormat=None,
			interface="text",
			promptTerminator=None,
			gagPrompts=None,
			findFormat=None,
			isEmulatingOffline=None,
		)
		self.mapper.daemon = True  # this allows unittest to quit if the mapper thread does not close properly.

	def testMapper_run(self):
		self.mapper.handleUserData = Mock()
		self.mapper.handleMudData = Mock()
		self.mapper.clientSend = Mock()
		self.mapper.start()

		# feed data into the mapper queue
		for dataType, data in [
			(MUD_DATA, ("line", b"Welcome to mume")),
			(MUD_DATA, ("prompt", b"hp:hurt mana:burning>")),
			(USER_DATA, b"rinfo"),
			(MUD_DATA, ("iac_ga", b"")),
			(USER_DATA, b"emu go lorien"),
			(USER_DATA, b"not_a_user_command"),
			(MUD_DATA, ("movement", b"east")),
			(USER_DATA, b"run ingrove"),
			(MUD_DATA, ("not_an_event", b"good bype world")),
			(None, None),
		]:
			self.mapper.queue.put((dataType, data))

		# insure that the mapper closes properly
		self.mapper.join(1)
		self.assertFalse(self.mapper.is_alive(), "mapper thread took longer than a second to quit")
		self.assertTrue(self.mapper.queue.empty(), "mapper queue is not empty after thread termination")

		# validate calls to handleUserData
		userCalls = self.mapper.handleUserData.mock_calls
		self.assertEqual(len(userCalls), 4)
		self.assertEqual(userCalls[0], call(b"rinfo"), "First call to handleUserData was not as expected.")
		self.assertEqual(userCalls[1], call(b"emu go lorien"), "Second call to handleUserData was not as expected.")
		self.assertEqual(userCalls[2], call(b"not_a_user_command"), "Third handleUserData was not as expected.")
		self.assertEqual(userCalls[3], call(b"run ingrove"), "Fourth call to handleUserData was not as expected.")

		# validate calls to handleMudData
		serverCalls = self.mapper.handleMudData.mock_calls
		self.assertEqual(len(serverCalls), 5)
		self.assertEqual(serverCalls[0], call("line", b"Welcome to mume"), "handleMudData #0 not expected.")
		self.assertEqual(serverCalls[1], call("prompt", b"hp:hurt mana:burning>"), "Second handleMudData")
		self.assertEqual(serverCalls[2], call("iac_ga", b""), "Third call to handleMudData")
		self.assertEqual(serverCalls[3], call("movement", b"east"), "Fourth handleMudData not as expected")
		self.assertEqual(serverCalls[4], call("not_an_event", b"good bype world"), "Fifth handleMudData")

	def testMapper_handleUserData(self):
		handleUserData = self.mapper.handleUserData

		for command, handlerName, args in [
			(b"rinfo", "user_command_rinfo", ""),
			(b"rlabel add here", "user_command_rlabel", "add here"),
			(b"emu go emoria", "user_command_emu", "go emoria"),
		]:
			with patch.object(self.mapper, handlerName) as handler:
				handleUserData(command)
				handler.assert_called_with(args)

		for command in [
			b"not_a_command",
			b"test failure",
			b"rinf",
		]:
			with self.assertRaises(AttributeError):
				self.mapper.handleUserData(command)

	def testMapper_handleMudData(self):
		for event, data, handlerName, args in [
			("line", b"Welcome to mume", "mud_event_line", "Welcome to mume"),
			("dynamic", b"A beautiful room", "mud_event_dynamic", "A beautiful room"),
			("exits", b"north, east, south", "mud_event_exits", "north, east, south"),
			("prompt", b"hp:hurt", "mud_event_prompt", "hp:hurt"),
		]:
			with patch.object(self.mapper, handlerName) as handler:
				self.mapper.mudEventHandlers[event] = [handler]
				self.mapper.handleMudData(event, data)
				handler.assert_called_with(args)

	def test_handleMudEvent_issuesDebugMessageWhenTryingToHandleAnUnregisteredEvent(self):
		for unknownEvent in [
			"unkk",
			"New_game_event",
			"room",
			"<interesting-tag-<in>-a-tag>",
		]:
			self.assertFalse(unknownEvent in self.mapper.unknownMudEvents)
			self.mapper.handleMudData(unknownEvent, "meaningless input")
			self.assertTrue(unknownEvent in self.mapper.unknownMudEvents)

	def test_init_RegistersLegacyHandlers(self):
		legacyHandlers = [
			getattr(self.mapper, handlerName) for handlerName in dir(self.mapper)
			if handlerName.startswith("mud_event_") and callable(getattr(self.mapper, handlerName))
		]
		for event in self.mapper.mudEventHandlers:
			for handler in self.mapper.mudEventHandlers[event]:
				if handler in legacyHandlers:
					legacyHandlers.remove(handler)
		self.assertFalse(legacyHandlers)

	def test_registerMudEventHandler_addsTheHandler(self):
		for event, sampleInput in [
			("sillyEvent", b"hello world"),
			("room", b"We start playing a game"),
			("otherEvent", b"<unknown>mystery</unknown>"),
		]:
			handler = Mock()
			self.mapper.registerMudEventHandler(event, handler)
			self.assertTrue(event in self.mapper.mudEventHandlers)
			self.assertTrue(handler in self.mapper.mudEventHandlers[event])
			self.mapper.handleMudData(event, sampleInput)
			handler.assert_called_with(str(sampleInput, "US-ASCII"))
