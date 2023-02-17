# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase, mock

# Mapper Modules:
from mapper.delays import BaseDelay, Delay, OneShot, Repeating


class TestDelays(TestCase):
	def testBaseDelay(self) -> None:
		with self.assertRaises(ValueError):
			BaseDelay(1, -1, lambda *args: None)
		delay: BaseDelay = BaseDelay(60, 10, lambda *args: None)
		self.assertFalse(delay._finished.is_set())
		delay.stop()
		self.assertTrue(delay._finished.is_set())
		delay._finished.clear()
		self.assertFalse(delay._finished.is_set())
		mockWait: mock.Mock
		with mock.patch.object(delay._finished, "wait") as mockWait:
			delay.start()
		delay.join(timeout=1.0)
		self.assertFalse(delay.is_alive(), "BaseDelay thread failed to terminate.")
		mockWait.assert_called_with(60)
		self.assertEqual(mockWait.call_count, 10)
		self.assertTrue(delay._finished.is_set())

	@mock.patch("mapper.delays.Delay.start")
	def testDelay(self, mockStart: mock.Mock) -> None:
		Delay(60, 10, lambda *args: None)
		mockStart.assert_called_once()

	@mock.patch("mapper.delays.OneShot.start")
	def testOneShot(self, mockStart: mock.Mock) -> None:
		delay: OneShot = OneShot(60, lambda *args: None)
		self.assertEqual(delay._duration, 60)
		self.assertEqual(delay._count, 1)
		mockStart.assert_called_once()

	@mock.patch("mapper.delays.Repeating.start")
	def testRepeating(self, mockStart: mock.Mock) -> None:
		delay: Repeating = Repeating(60, lambda *args: None)
		self.assertEqual(delay._duration, 60)
		self.assertIsNone(delay._count)
		mockStart.assert_called_once()
