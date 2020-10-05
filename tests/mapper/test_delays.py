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
	def testBaseDelay(self):
		with self.assertRaises(ValueError):
			BaseDelay(1, -1, lambda *args: None)
		delay = BaseDelay(60, 10, lambda *args: None)
		delay._finished.wait = mock.Mock()
		delay.start()
		delay._finished.wait.assert_called_with(60)
		self.assertEqual(delay._finished.wait.call_count, 10)
		delay.stop()
		self.assertTrue(delay._finished.is_set())

	@mock.patch("mapper.delays.Delay.start")
	def testDelay(self, mockStart):
		Delay(60, 10, lambda *args: None)
		mockStart.assert_called_once()

	@mock.patch("mapper.delays.OneShot.start")
	def testOneShot(self, mockStart):
		delay = OneShot(60, lambda *args: None)
		self.assertEqual(delay._duration, 60)
		self.assertEqual(delay._count, 1)
		mockStart.assert_called_once()

	@mock.patch("mapper.delays.Repeating.start")
	def testRepeating(self, mockStart):
		delay = Repeating(60, lambda *args: None)
		self.assertEqual(delay._duration, 60)
		self.assertIsNone(delay._count)
		mockStart.assert_called_once()
