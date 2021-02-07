# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase
from unittest.mock import Mock, patch

# Mapper Modules:
from mapper.sockets.fakesocket import FakeSocket, FakeSocketEmpty


class TestFakeSocket(TestCase):
	def setUp(self) -> None:
		self.fakeSocket: FakeSocket = FakeSocket()

	def tearDown(self) -> None:
		del self.fakeSocket

	def testTimeout(self) -> None:
		self.fakeSocket.settimeout(5.0)
		self.assertEqual(self.fakeSocket.gettimeout(), 5.0)
		self.fakeSocket.settimeout(None)
		self.assertIsNone(self.fakeSocket.gettimeout())

	def testBlocking(self) -> None:
		self.fakeSocket.setblocking(True)
		self.assertTrue(self.fakeSocket.getblocking())
		self.fakeSocket.setblocking(False)
		self.assertFalse(self.fakeSocket.getblocking())

	def testGetpeercert(self) -> None:
		self.assertEqual(self.fakeSocket.getpeercert(), {"subject": [["commonName", "mume.org"]]})

	def testSend(self) -> None:
		self.assertIsNone(self.fakeSocket.inboundBuffer)
		self.assertEqual(self.fakeSocket.send(b"quit"), 4)
		self.assertEqual(self.fakeSocket.inboundBuffer, b"")

	@patch.object(FakeSocket, "send")
	def testSendall(self, mockSend: Mock) -> None:
		self.fakeSocket.sendall(b"hello")
		mockSend.assert_called_once_with(b"hello", 0)

	@patch("mapper.sockets.fakesocket.time")
	def testRecv(self, mockTime: Mock) -> None:
		self.fakeSocket.inboundBuffer = b"hello"
		self.assertEqual(self.fakeSocket.recv(4096), b"hello")
		mockTime.sleep.assert_called_once_with(0.005)
		mockTime.reset_mock()
		with self.assertRaises(FakeSocketEmpty):
			self.fakeSocket.inboundBuffer = None
			self.fakeSocket.recv(4096)
		mockTime.sleep.assert_called_once_with(0.005)
