# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re
import time

# Local Modules:
from .config import Config, config_lock


CLOCK_REGEX = re.compile(
	r"^The current time is (?P<hour>[1-9]|1[0-2])\:(?P<minutes>[0-5]\d) (?P<am_pm>[ap]m)\.$"
)
TIME_REGEX = re.compile(
	r"^(?:(?:It is )?(?P<hour>[1-9]|1[0-2]) (?P<am_pm>[ap]m)(?: on ))?\w+\, the (?P<day>\d+)(?:st|[nr]d|th) "
	r"of (?P<month>\w+)\, [yY]ear (?P<year>\d{4}) of the Third Age\.$"
)
DAWN_REGEX = re.compile(r"^Light gradually filters in\, proclaiming a new sunrise(?: outside)?\.$")
DAY_REGEX = re.compile(
	r"^(?:It seems as if )?[Tt]he day has begun\.(?: You feel so weak under the cruel light\!)?$"
)
DUSK_REGEX = re.compile(r"^The deepening gloom announces another sunset(?: outside)?\.$")
NIGHT_REGEX = re.compile(
	r"^The last ray of light fades\, and all is swallowed up in darkness\.$|"
	r"^(?:It seems as if )?[Tt]he night has begun\.(?: You feel stronger in the dark\!)?$"
)

FIRST_YEAR = 2850
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR
MINUTES_PER_DAY = MINUTES_PER_HOUR * HOURS_PER_DAY
MINUTES_PER_MONTH = MINUTES_PER_DAY * DAYS_PER_MONTH
MINUTES_PER_YEAR = MINUTES_PER_DAY * DAYS_PER_YEAR
DAYS_PER_MOON_CYCLE = 24
HOURS_PER_MOON_CYCLE = HOURS_PER_DAY * DAYS_PER_MOON_CYCLE

# fmt: off
MONTHS = [
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

WEEKDAYS = [
	{"name": "Sunday", "sindarin": "Oranor", "westron": "Sunday"},
	{"name": "Monday", "sindarin": "Orithil", "westron": "Monday"},
	{"name": "Tuesday", "sindarin": "Orgaladhad", "westron": "Trewsday"},
	{"name": "Wednesday", "sindarin": "Ormenel", "westron": "Hevensday"},
	{"name": "Thursday", "sindarin": "Orbelain", "westron": "Mersday"},
	{"name": "Friday", "sindarin": "Oraearon", "westron": "Highday"},
	{"name": "Saturday", "sindarin": "Orgilion", "westron": "Sterday"},
]


def timeToEpoch(year, month, day, hour, minutes):
	"""Returns the epoch for the given game time."""
	epoch = int(time.time())
	epoch -= (year - FIRST_YEAR) * MINUTES_PER_YEAR
	epoch -= month * MINUTES_PER_MONTH
	epoch -= (day - 1) * MINUTES_PER_DAY
	epoch -= hour * MINUTES_PER_HOUR
	epoch -= minutes
	return epoch


class Clock(object):
	def __init__(self):
		self._epoch = None

	@property
	def epoch(self):
		if self._epoch is not None:
			return self._epoch
		with config_lock:
			cfg = Config()
			epoch = cfg.get("mume_epoch", 1517486489)
			del cfg
		return epoch

	@epoch.setter
	def epoch(self, value):
		self._epoch = value
		with config_lock:
			cfg = Config()
			cfg["mume_epoch"] = value
			cfg.save()
			del cfg

	def time(self, action=None):
		output = []
		minutes = int(time.time()) - self.epoch
		year = minutes // MINUTES_PER_YEAR + FIRST_YEAR
		minutes %= MINUTES_PER_YEAR
		month = minutes // MINUTES_PER_MONTH
		minutes %= MINUTES_PER_MONTH
		day = minutes // MINUTES_PER_DAY + 1
		minutes %= MINUTES_PER_DAY
		dayOfYear = month * DAYS_PER_MONTH + day
		hour = minutes // MINUTES_PER_HOUR
		minutes %= MINUTES_PER_HOUR
		ap = "am" if hour < 12 else "pm"
		output.append(
			f"Game time {hour % 12 or 12}:{minutes:02d} {ap}: "
			+ f"Dawn: {MONTHS[month]['dawn']} am, "
			+ f"Dusk: {MONTHS[month]['dusk'] - 12} pm."
		)
		if action == "pull":
			return f"pull lever {day}\npull lever {MONTHS[month]['westron']}"
		elif action is not None:
			return f"{action} {output[0]}"
		weekday = WEEKDAYS[(dayOfYear + (year - FIRST_YEAR) * DAYS_PER_YEAR) % 7]["name"]
		if hour < MONTHS[month]["dawn"]:
			state = "NIGHT"
			nextState = "DAY"
			untilNextState = MONTHS[month]["dawn"] - hour + 1
		elif hour >= MONTHS[month]["dusk"]:
			state = "NIGHT"
			nextState = "DAY"
			untilNextState = 25 + MONTHS[month]["dawn"] - hour
		elif hour > MONTHS[month]["dawn"] and hour < MONTHS[month]["dusk"]:
			state = "DAY"
			nextState = "NIGHT"
			untilNextState = MONTHS[month]["dusk"] - hour
		elif hour == MONTHS[month]["dawn"]:
			state = "DAWN"
			nextState = "DAY"
			untilNextState = 1
		output.append(
			f"It is currently {state}, on {weekday}, {MONTHS[month]['name']} {day} "
			+ f"({MONTHS[month]['westron']} / {MONTHS[month]['sindarin']}), "
			+ f"({MONTHS[month]['season']}), year {year} of the third age."
		)
		output.append(
			f"Time left until {nextState} is less than {untilNextState} tick{'s' if untilNextState != 1 else '!'}"
		)
		nextSeasonInGameDays = (((month + 1) // 3 * 3 + 3) - (month + 1) - 1) * DAYS_PER_MONTH
		nextSeasonInGameDays += (DAYS_PER_MONTH - day) + (1 - (hour // HOURS_PER_DAY))
		nextSeasonInRlHours = nextSeasonInGameDays * HOURS_PER_DAY // MINUTES_PER_HOUR
		output.append(
			f"{MONTHS[month]['season'][-6:]} ends in "
			+ f"{nextSeasonInGameDays} mume day{'s' if nextSeasonInGameDays != 1 else ''} or "
			+ f"{nextSeasonInRlHours} real-life hour{'s' if nextSeasonInRlHours != 1 else ''}."
		)
		nextWinterInGameDays = (MONTHS_PER_YEAR - (month + 1) % 12 - 1) * DAYS_PER_MONTH
		nextWinterInGameDays += (DAYS_PER_MONTH - day) + (1 - hour // HOURS_PER_DAY)
		nextWinterInRlDays = nextWinterInGameDays * HOURS_PER_DAY // MINUTES_PER_HOUR // HOURS_PER_DAY
		nextWinterInRlHours = (nextWinterInGameDays * HOURS_PER_DAY // MINUTES_PER_HOUR) % HOURS_PER_DAY
		output.append(
			f"Next winter starts in {nextWinterInRlDays} real-life day{'s' if nextWinterInRlDays != 1 else ''} "
			+ f"and {nextWinterInRlHours} hour{'s' if nextWinterInRlHours != 1 else ''}."
		)
		moonRiseOffset = 11
		moonRiseHour = (dayOfYear + moonRiseOffset) % DAYS_PER_MOON_CYCLE
		if hour == moonRiseHour:
			output.append("Moon is up now!")
		else:
			if hour > moonRiseHour:
				moonRiseHour = (dayOfYear + moonRiseOffset + 1) % DAYS_PER_MOON_CYCLE
				moonRiseDay = "tomorrow"
			else:
				moonRiseDay = "today"
			output.append(
				f"Next moon rise {moonRiseDay} at {moonRiseHour % 12 or 12}:00 "
				+ f"{'am' if moonRiseHour < 12 else 'pm'} (game time)."
			)
		fullMoonOffset = DAYS_PER_MOON_CYCLE - 7  # First full moon rises on the 7th day of the year.
		fullMoonHour = (dayOfYear + fullMoonOffset) % DAYS_PER_MOON_CYCLE * HOURS_PER_DAY + hour
		if fullMoonHour < 31:
			ticksUntilFullMoon = 18 - fullMoonHour if fullMoonHour <= 18 else 0
		else:
			ticksUntilFullMoon = HOURS_PER_MOON_CYCLE - fullMoonHour + 18
		nextFullMoonInRlHours = ticksUntilFullMoon // MINUTES_PER_HOUR
		nextFullMoonInRlMinutes = ticksUntilFullMoon % MINUTES_PER_HOUR
		if not ticksUntilFullMoon:
			output.append("Full moon is up now!")
		else:
			output.append(
				"Next full moon rises in "
				+ f"{nextFullMoonInRlHours} real-life hour{'s' if nextFullMoonInRlHours != 1 else ''} "
				+ f"and {nextFullMoonInRlMinutes} minute{'s' if nextFullMoonInRlMinutes != 1 else ''}."
			)
		dkMoonOffset = DAYS_PER_MOON_CYCLE - 6  # First DK moon rises on the 6th day of the year.
		dkHour = (dayOfYear + dkMoonOffset) % DAYS_PER_MOON_CYCLE * HOURS_PER_DAY + hour
		nextDkDay = 1
		if dkHour < 20:
			ticksUntilDk = 17 - dkHour if dkHour <= 17 else 0
		elif dkHour < HOURS_PER_DAY + 21:
			ticksUntilDk = HOURS_PER_DAY + 18 - dkHour if dkHour <= HOURS_PER_DAY + 18 else 0
			nextDkDay = 2
		elif dkHour < HOURS_PER_DAY * 2 + 22:
			ticksUntilDk = HOURS_PER_DAY * 2 + 19 - dkHour if dkHour <= HOURS_PER_DAY * 2 + 19 else 0
			nextDkDay = 3
		else:
			ticksUntilDk = HOURS_PER_MOON_CYCLE - dkHour + 17
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
