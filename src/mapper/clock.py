# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re
import time
from typing import Optional, Union

# Local Modules:
from .config import Config
from .typedef import REGEX_PATTERN


CLOCK_REGEX: REGEX_PATTERN = re.compile(
	r"^The current time is (?P<hour>[1-9]|1[0-2])\:(?P<minutes>[0-5]\d) (?P<am_pm>[ap]m)\.$"
)
TIME_REGEX: REGEX_PATTERN = re.compile(
	r"^(?:(?:It is )?(?P<hour>[1-9]|1[0-2]) (?P<am_pm>[ap]m)(?: on ))?\w+\, the (?P<day>\d+)(?:st|[nr]d|th) "
	+ r"of (?P<month>\w+)\, [yY]ear (?P<year>\d{4}) of the Third Age\.$"
)
DAWN_REGEX: REGEX_PATTERN = re.compile(
	r"^Light gradually filters in\, proclaiming a new sunrise(?: outside)?\.$"
)
DAY_REGEX: REGEX_PATTERN = re.compile(
	r"^(?:It seems as if )?[Tt]he day has begun\.(?: You feel so weak under the cruel light\!)?$"
)
DUSK_REGEX: REGEX_PATTERN = re.compile(r"^The deepening gloom announces another sunset(?: outside)?\.$")
NIGHT_REGEX: REGEX_PATTERN = re.compile(
	r"^The last ray of light fades\, and all is swallowed up in darkness\.$|"
	+ r"^(?:It seems as if )?[Tt]he night has begun\.(?: You feel stronger in the dark\!)?$"
)

FIRST_YEAR: int = 2850
MINUTES_PER_HOUR: int = 60
HOURS_PER_DAY: int = 24
DAYS_PER_WEEK: int = 7
DAYS_PER_MONTH: int = 30
MONTHS_PER_YEAR: int = 12
SEASONS_PER_YEAR: int = 4
MONTHS_PER_SEASON: int = MONTHS_PER_YEAR // SEASONS_PER_YEAR
DAYS_PER_SEASON: int = DAYS_PER_MONTH * MONTHS_PER_SEASON
DAYS_PER_YEAR: int = DAYS_PER_MONTH * MONTHS_PER_YEAR
MINUTES_PER_DAY: int = MINUTES_PER_HOUR * HOURS_PER_DAY
MINUTES_PER_MONTH: int = MINUTES_PER_DAY * DAYS_PER_MONTH
MINUTES_PER_YEAR: int = MINUTES_PER_DAY * DAYS_PER_YEAR
DAYS_PER_MOON_CYCLE: int = 24
HOURS_PER_MOON_CYCLE: int = HOURS_PER_DAY * DAYS_PER_MOON_CYCLE
HOURS_PER_MOON_RISE: int = HOURS_PER_DAY + 1
FIRST_FULL_MOON_DAY: int = 7  # First full moon is on January 7.
FULL_MOON_HOUR: int = 18  # Full moon always rises at 6 PM.
FULL_MOON_OFFSET: int = 14  # Full moon day is always 14 days after the moon cycle starts.
FIRST_MOON_CYCLE_DAY: int = (FIRST_FULL_MOON_DAY - FULL_MOON_OFFSET) % DAYS_PER_MOON_CYCLE
FIRST_MOON_CYCLE_HOUR: int = (FULL_MOON_HOUR - FULL_MOON_OFFSET) % HOURS_PER_DAY
DK_OPEN_DURATION: int = 3  # The number of hours DK stays open.

# fmt: off
MONTHS: list[dict[str, Union[str, int]]] = [
	{
		"name": "January",
		"sindarin": "Ninui",
		"westron": "Solmath",
		"dawn": 9,
		"dusk": 17,
		"season": "Winter",
	},
	{
		"name": "February",
		"sindarin": "Gwaeron",
		"westron": "Rethe",
		"dawn": 8,
		"dusk": 18,
		"season": "Late-Winter",
	},
	{
		"name": "March",
		"sindarin": "Gwirith",
		"westron": "Astron",
		"dawn": 7,
		"dusk": 19,
		"season": "Early-Spring",
	},
	{
		"name": "April",
		"sindarin": "Lothron",
		"westron": "Thrimidge",
		"dawn": 7,
		"dusk": 20,
		"season": "Spring",
	},
	{
		"name": "May",
		"sindarin": "Norui",
		"westron": "Forelithe",
		"dawn": 6,
		"dusk": 20,
		"season": "Late-Spring",
	},
	{
		"name": "June",
		"sindarin": "Cerveth",
		"westron": "Afterlithe",
		"dawn": 5,
		"dusk": 21,
		"season": "Early-Summer",
	},
	{
		"name": "July",
		"sindarin": "Urui",
		"westron": "Wedmath",
		"dawn": 4,
		"dusk": 22,
		"season": "Summer",
	},
	{
		"name": "August",
		"sindarin": "Ivanneth",
		"westron": "Halimath",
		"dawn": 5,
		"dusk": 21,
		"season": "Late-Summer",
	},
	{
		"name": "September",
		"sindarin": "Narbeleth",
		"westron": "Winterfilth",
		"dawn": 6,
		"dusk": 20,
		"season": "Early-Autumn",
	},
	{
		"name": "October",
		"sindarin": "Hithui",
		"westron": "Blotmath",
		"dawn": 7,
		"dusk": 20,
		"season": "Autumn",
	},
	{
		"name": "November",
		"sindarin": "Girithron",
		"westron": "Foreyule",
		"dawn": 7,
		"dusk": 19,
		"season": "Late-Autumn",
	},
	{
		"name": "December",
		"sindarin": "Narwain",
		"westron": "Afteryule",
		"dawn": 8,
		"dusk": 18,
		"season": "Early-Winter",
	},
]
# fmt: on

WEEKDAYS: list[dict[str, str]] = [
	{"name": "Sunday", "sindarin": "Oranor", "westron": "Sunday"},
	{"name": "Monday", "sindarin": "Orithil", "westron": "Monday"},
	{"name": "Tuesday", "sindarin": "Orgaladhad", "westron": "Trewsday"},
	{"name": "Wednesday", "sindarin": "Ormenel", "westron": "Hevensday"},
	{"name": "Thursday", "sindarin": "Orbelain", "westron": "Mersday"},
	{"name": "Friday", "sindarin": "Oraearon", "westron": "Highday"},
	{"name": "Saturday", "sindarin": "Orgilion", "westron": "Sterday"},
]


def timeToDelta(year: int, month: int, day: int, hour: int, minutes: int) -> int:
	"""
	Calculates the delta of a given Mume time.

	The delta is the difference (in real seconds) between the last reset of Mume time and the given Mume time.

	Args:
		year: The year.
		month: Month of the year (0 - 11).
		day: Day of the month (1 - 30).
		hour: Hour of day (0 - 23).
		minutes: Minutes of the hour (0 - 59).

	Returns:
		The delta.
	"""
	return (
		(year - FIRST_YEAR) * MINUTES_PER_YEAR
		+ month * MINUTES_PER_MONTH
		+ (day - 1) * MINUTES_PER_DAY
		+ hour * MINUTES_PER_HOUR
		+ minutes
	)


def deltaToTime(delta: int) -> tuple[int, int, int, int, int]:
	"""
	Calculates the Mume time of a given delta.

	The delta is the difference (in real seconds) between the last reset of Mume time and the given Mume time.

	Args:
		delta: The delta.

	Returns:
		A tuple containing the Mume year, month, day, hour, and minutes.
	"""
	year = delta // MINUTES_PER_YEAR + FIRST_YEAR
	delta %= MINUTES_PER_YEAR
	month = delta // MINUTES_PER_MONTH  # 0 - 11.
	delta %= MINUTES_PER_MONTH
	day = delta // MINUTES_PER_DAY + 1  # 1 - 30.
	delta %= MINUTES_PER_DAY
	hour = delta // MINUTES_PER_HOUR  # 0 - 23.
	delta %= MINUTES_PER_HOUR
	minutes = delta  # 0 - 59.
	return year, month, day, hour, minutes


class MumeTime:
	def __init__(self, delta: int) -> None:
		self._year, self._month, self._day, self._hour, self._minutes = deltaToTime(delta)

	@property
	def year(self) -> int:
		"""The year."""
		return self._year

	@property
	def month(self) -> int:
		"""The month of the year (0 or more)."""
		return self._month

	@property
	def day(self) -> int:
		"""The day of the month (1 or more)."""
		return self._day

	@property
	def hour(self) -> int:
		"""The hour of the day (0 or more)."""
		return self._hour

	@property
	def minutes(self) -> int:
		"""The minutes of the hour (0 or more)."""
		return self._minutes

	@property
	def delta(self) -> int:
		"""The time as a delta."""
		return timeToDelta(self.year, self.month, self.day, self.hour, self.minutes)

	@property
	def amPm(self) -> str:
		"""The AM - PM value."""
		return "am" if self.hour < 12 else "pm"

	@property
	def dayOfYear(self) -> int:
		"""The day of the year (1 or more)."""
		return self.month * DAYS_PER_MONTH + self.day

	@property
	def hourOfYear(self) -> int:
		"""The hour of the year (0 or more)."""
		return (self.dayOfYear - 1) * HOURS_PER_DAY + self.hour

	@property
	def overallDay(self) -> int:
		"""The sum of all the elapsed years in days and the day of year (1 or more)."""
		return (self.year - FIRST_YEAR) * DAYS_PER_YEAR + self.dayOfYear

	@property
	def weekday(self) -> str:
		"""The name of the weekday."""
		return WEEKDAYS[self.overallDay % DAYS_PER_WEEK]["name"]

	@property
	def dawn(self) -> int:
		"""The hour of dawn."""
		return int(MONTHS[self.month]["dawn"])

	@property
	def dusk(self) -> int:
		"""The hour of dusk."""
		return int(MONTHS[self.month]["dusk"])

	@property
	def season(self) -> str:
		"""The name of the season."""
		return str(MONTHS[self.month]["season"])

	@property
	def monthName(self) -> str:
		"""The name of the month."""
		return str(MONTHS[self.month]["name"])

	@property
	def monthWestron(self) -> str:
		"""The name of the month in Westron."""
		return str(MONTHS[self.month]["westron"])

	@property
	def monthSindarin(self) -> str:
		"""The name of the month in Sindarin."""
		return str(MONTHS[self.month]["sindarin"])

	@property
	def dawnDuskState(self) -> tuple[str, str, int]:
		"""A tuple containing the current state name, the next state name, and the game hours until next state."""
		if self.hour < self.dawn:
			state = "NIGHT"
			nextState = "DAY"
			untilNextState = self.dawn - self.hour + 1
		elif self.hour >= self.dusk:
			state = "NIGHT"
			nextState = "DAY"
			untilNextState = HOURS_PER_DAY + self.dawn - self.hour + 1
		elif self.hour > self.dawn and self.hour < self.dusk:
			state = "DAY"
			nextState = "NIGHT"
			untilNextState = self.dusk - self.hour
		elif self.hour == self.dawn:
			state = "DAWN"
			nextState = "DAY"
			untilNextState = 1
		return state, nextState, untilNextState

	@property
	def daysUntilSeason(self) -> int:
		"""The days until next season (1 or more)."""
		monthsSinceLastSeason = (self.month + 1) % MONTHS_PER_SEASON
		daysSinceLastSeason = monthsSinceLastSeason * DAYS_PER_MONTH + (self.day - 1)
		return DAYS_PER_SEASON - daysSinceLastSeason

	@property
	def rlHoursUntilSeason(self) -> int:
		"""The real life hours until next season (1 or more)."""
		return self.daysUntilSeason * HOURS_PER_DAY // MINUTES_PER_HOUR

	@property
	def daysUntilWinter(self) -> int:
		"""The days until next winter (1 or more)."""
		monthsSinceLastWinter = (self.month + 1) % MONTHS_PER_YEAR
		daysSinceLastWinter = monthsSinceLastWinter * DAYS_PER_MONTH + (self.day - 1)
		return DAYS_PER_YEAR - daysSinceLastWinter

	@property
	def rlHoursUntilWinter(self) -> int:
		"""The real life hours until next winter (0 or more)."""
		return self.daysUntilWinter * HOURS_PER_DAY // MINUTES_PER_HOUR

	@property
	def daysSinceMoonCycle(self) -> int:
		"""The days since last moon cycle (0 or more)."""
		return (self.dayOfYear - FIRST_MOON_CYCLE_DAY) % DAYS_PER_MOON_CYCLE

	@property
	def daysUntilMoonCycle(self) -> int:
		"""The days until next moon cycle (1 or more)."""
		return DAYS_PER_MOON_CYCLE - self.daysSinceMoonCycle

	@property
	def hourOfMoonRise(self) -> int:
		"""The hour of day when the moon will rise (0 or more)."""
		return (FIRST_MOON_CYCLE_HOUR + self.daysSinceMoonCycle) % HOURS_PER_DAY

	@property
	def daysSinceFullMoon(self) -> int:
		"""The days since last full moon (0 or more)."""
		return (self.dayOfYear - FIRST_FULL_MOON_DAY) % DAYS_PER_MOON_CYCLE

	@property
	def daysUntilFullMoon(self) -> int:
		"""The days until next full moon (1 or more)."""
		return DAYS_PER_MOON_CYCLE - self.daysSinceFullMoon

	@property
	def hoursSinceFullMoon(self) -> int:
		"""The hours since last full moon (0 or more)."""
		return (self.daysSinceFullMoon * HOURS_PER_DAY + self.hour - FULL_MOON_HOUR) % HOURS_PER_MOON_CYCLE

	@property
	def hoursUntilFullMoon(self) -> int:
		"""The hours Until full moon (1 or more)."""
		return HOURS_PER_MOON_CYCLE - self.hoursSinceFullMoon

	@property
	def info(self) -> str:  # pragma: no cover
		"""A summery of information about this moment in Mume time."""
		output = []
		output.append(
			f"Game time {self.hour % 12 or 12}:{self.minutes:02d} {self.amPm}: "
			+ f"Dawn: {self.dawn} am, Dusk: {self.dusk - 12} pm."
		)
		state, nextState, untilNextState = self.dawnDuskState
		output.append(
			f"It is currently {state}, on {self.weekday}, {self.monthName} {self.day} "
			+ f"({self.monthWestron} / {self.monthSindarin}), ({self.season}), year {self.year} of the third age."
		)
		output.append(
			f"Time left until {nextState} is less than {untilNextState} tick{'s' if untilNextState != 1 else '!'}"
		)
		output.append(
			f"{self.season[-6:]} ends in "
			+ f"{self.daysUntilSeason} mume day{'s' if self.daysUntilSeason != 1 else ''} or "
			+ f"{self.rlHoursUntilSeason} real-life hour{'s' if self.rlHoursUntilSeason != 1 else ''}."
		)
		rlDaysUntilWinter = self.rlHoursUntilWinter // HOURS_PER_DAY
		rlHoursUntilWinter = self.rlHoursUntilWinter % HOURS_PER_DAY
		output.append(
			f"Next winter starts in {rlDaysUntilWinter} real-life day{'s' if rlDaysUntilWinter != 1 else ''} "
			+ f"and {rlHoursUntilWinter} hour{'s' if rlHoursUntilWinter != 1 else ''}."
		)
		hourOfMoonRise = self.hourOfMoonRise
		if self.hour == hourOfMoonRise:
			output.append("Moon is up now!")
		else:
			if self.hour > hourOfMoonRise:
				hourOfMoonRise = (hourOfMoonRise + 1) % HOURS_PER_DAY
				dayOfMoonRise = "tomorrow"
			else:
				dayOfMoonRise = "today"
			output.append(
				f"Next moon rise {dayOfMoonRise} at {hourOfMoonRise % 12 or 12}:00 "
				+ f"{'am' if hourOfMoonRise < 12 else 'pm'} (game time)."
			)
		nextFullMoonRlHours = self.hoursUntilFullMoon // MINUTES_PER_HOUR
		nextFullMoonRlMinutes = self.hoursUntilFullMoon % MINUTES_PER_HOUR
		if self.hoursSinceFullMoon < 13:
			output.append("Full moon is up now!")
		else:
			output.append(
				"Next full moon rises in "
				+ f"{nextFullMoonRlHours} real-life hour{'s' if nextFullMoonRlHours != 1 else ''} "
				+ f"and {nextFullMoonRlMinutes} minute{'s' if nextFullMoonRlMinutes != 1 else ''}."
			)
		if (
			self.hoursUntilFullMoon > HOURS_PER_MOON_RISE - DK_OPEN_DURATION
			and self.hoursSinceFullMoon >= HOURS_PER_MOON_RISE + DK_OPEN_DURATION
		):
			nextDkDay = 1
			ticksUntilDk = (
				self.hoursUntilFullMoon - HOURS_PER_MOON_RISE
				if self.hoursUntilFullMoon > HOURS_PER_MOON_RISE
				else 0
			)
		elif (
			self.hoursUntilFullMoon <= HOURS_PER_MOON_RISE - DK_OPEN_DURATION
			or self.hoursSinceFullMoon < DK_OPEN_DURATION
		):
			nextDkDay = 2
			ticksUntilDk = 0 if self.hoursSinceFullMoon < DK_OPEN_DURATION else self.hoursUntilFullMoon
		else:
			nextDkDay = 3
			ticksUntilDk = (
				HOURS_PER_MOON_RISE - self.hoursSinceFullMoon
				if self.hoursSinceFullMoon < HOURS_PER_MOON_RISE
				else 0
			)
		nextDkInRlHours = ticksUntilDk // MINUTES_PER_HOUR
		nextDkInRlMinutes = ticksUntilDk % MINUTES_PER_HOUR
		if not ticksUntilDk:
			output.append("DK is open now!")
		else:
			output.append(
				f"DK opens in {nextDkInRlHours} real-life hour{'s' if nextDkInRlHours != 1 else ''} and "
				+ f"{nextDkInRlMinutes} minute{'s' if nextDkInRlMinutes != 1 else ''} (day {nextDkDay} of 3)."
			)
		return "\n".join(output)


class Clock:
	def __init__(self) -> None:
		self._epoch: Optional[int] = None

	@property
	def epoch(self) -> int:  # pragma: no cover
		"""
		The Mume epoch.

		The Mume epoch is the real life time (in seconds) when Mume time was last reset.
		"""
		if self._epoch is None:
			cfg = Config()
			self._epoch = int(cfg.get("mume_epoch", 1517486451))
			del cfg
		return self._epoch

	@epoch.setter
	def epoch(self, value: int) -> None:  # pragma: no cover
		self._epoch = value
		cfg = Config()
		cfg["mume_epoch"] = int(value)
		cfg.save()
		del cfg

	def setTime(self, year: int, month: int, day: int, hour: int, minutes: int) -> None:
		"""
		Sets the Mume epoch from the current Mume time.

		Args:
			year: The year.
			month: Month of the year (0 - 11).
			day: Day of the month (1 - 30).
			hour: Hour of day (0 - 23).
			minutes: Minutes of the hour (0 - 59).
		"""
		delta = timeToDelta(year, month, day, hour, minutes)
		self.epoch = int(time.time()) - delta

	def time(self, action: Optional[str] = None) -> str:
		"""
		Outputs information about the current Mume time.

		Args:
			action: An action to perform.
				If 'pull', output commands for looting mystical.
				If not None, output first line of output, preceded by the action.
				Otherwise, output the full information.

		Returns:
			The requested output.
		"""
		mt = MumeTime(int(time.time()) - self.epoch)
		if action == "pull":
			return f"pull lever {mt.day}\npull lever {mt.monthWestron}"
		elif action is not None:
			return f"{action} {mt.info.splitlines()[0]}"
		return mt.info
