# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from unittest import TestCase, mock

# Mapper Modules:
from mapper.clock import FIRST_YEAR, Clock, MumeTime, deltaToTime, timeToDelta


YEAR: int = FIRST_YEAR + 5
MONTH: int = 4
DAY: int = 3
HOUR: int = 2
MINUTES: int = 1
DELTA: int = 2767801
TIME_OUTPUT: str = (
	"Game time 2:01 am: Dawn: 6 am, Dusk: 8 pm.\n"
	+ "It is currently NIGHT, on Friday, May 3 (Forelithe / Norui), "
	+ "(Late-Spring), year 2855 of the third age.\n"
	+ "Time left until DAY is less than 5 ticks\n"
	+ "Spring ends in 28 mume days or 11 real-life hours.\n"
	+ "Next winter starts in 3 real-life days and 11 hours.\n"
	+ "Next moon rise today at 2:00 pm (game time).\n"
	+ "Next full moon rises in 1 real-life hour and 52 minutes.\n"
	+ "DK opens in 1 real-life hour and 27 minutes (day 1 of 3)."
)


class TestToAndFromDelta(TestCase):
	def test_timeToDelta(self) -> None:
		self.assertEqual(timeToDelta(YEAR, MONTH, DAY, HOUR, MINUTES), DELTA)

	def test_deltaToTime(self) -> None:
		self.assertEqual(deltaToTime(DELTA), (YEAR, MONTH, DAY, HOUR, MINUTES))


class TestMumeTime(TestCase):
	def test_properties(self) -> None:
		mt: MumeTime
		mt = MumeTime(timeToDelta(YEAR, MONTH, DAY, HOUR, MINUTES))
		self.assertEqual(mt.year, YEAR)
		self.assertEqual(mt.month, MONTH)
		self.assertEqual(mt.day, DAY)
		self.assertEqual(mt.hour, HOUR)
		self.assertEqual(mt.minutes, MINUTES)
		self.assertEqual(mt.delta, DELTA)
		self.assertEqual(mt.dayOfYear, 123)
		self.assertEqual(mt.hourOfYear, 2930)
		self.assertEqual(mt.overallDay, 1923)
		self.assertEqual(mt.weekday, "Friday")
		self.assertEqual(mt.dawn, 6)
		self.assertEqual(mt.dusk, 20)
		self.assertEqual(mt.season, "Late-Spring")
		self.assertEqual(mt.monthName, "May")
		self.assertEqual(mt.monthWestron, "Forelithe")
		self.assertEqual(mt.monthSindarin, "Norui")
		self.assertEqual(mt.daysUntilSeason, 28)
		self.assertEqual(mt.rlHoursUntilSeason, 11)
		self.assertEqual(mt.daysUntilWinter, 208)
		self.assertEqual(mt.rlHoursUntilWinter, 83)
		self.assertEqual(mt.daysSinceMoonCycle, 10)
		self.assertEqual(mt.daysUntilMoonCycle, 14)
		self.assertEqual(mt.hourOfMoonRise, 14)
		self.assertEqual(mt.daysSinceFullMoon, 20)
		self.assertEqual(mt.daysUntilFullMoon, 4)
		self.assertEqual(mt.hoursSinceFullMoon, 464)
		self.assertEqual(mt.hoursUntilFullMoon, 112)
		self.assertEqual(mt.info, TIME_OUTPUT)
		self.assertEqual(mt.amPm, "am")
		mt = MumeTime(timeToDelta(YEAR, MONTH, DAY, 12, MINUTES))
		self.assertEqual(mt.amPm, "pm")
		mt = MumeTime(timeToDelta(YEAR, MONTH, DAY, HOUR, MINUTES))
		self.assertEqual(mt.dawnDuskState, ("NIGHT", "DAY", 5))
		mt = MumeTime(timeToDelta(YEAR, MONTH, DAY, 20, MINUTES))
		self.assertEqual(mt.dawnDuskState, ("NIGHT", "DAY", 11))
		mt = MumeTime(timeToDelta(YEAR, MONTH, DAY, 7, MINUTES))
		self.assertEqual(mt.dawnDuskState, ("DAY", "NIGHT", 13))
		mt = MumeTime(timeToDelta(YEAR, MONTH, DAY, 6, MINUTES))
		self.assertEqual(mt.dawnDuskState, ("DAWN", "DAY", 1))


class TestClock(TestCase):
	@mock.patch("mapper.clock.time")
	def test_setTime(self, mockTime: mock.Mock) -> None:
		mockTime.time.return_value = DELTA + 1
		mockEpoch: mock.Mock
		with mock.patch.object(Clock, "epoch", mock.PropertyMock()) as mockEpoch:
			clock: Clock = Clock()
			clock.setTime(YEAR, MONTH, DAY, HOUR, MINUTES)
			mockEpoch.assert_called_once_with(1)

	@mock.patch("mapper.clock.Clock.epoch", mock.PropertyMock(return_value=0))
	@mock.patch("mapper.clock.time")
	def test_time(self, mockTime: mock.Mock) -> None:
		mockTime.time.return_value = DELTA
		clock: Clock = Clock()
		self.assertEqual(clock.time("pull"), "pull lever 3\npull lever Forelithe")
		self.assertEqual(clock.time("say"), f"say {TIME_OUTPUT.splitlines()[0]}")
		self.assertEqual(clock.time(), TIME_OUTPUT)
