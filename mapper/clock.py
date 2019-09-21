# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import time

from .config import Config, config_lock


CLOCK_REGEX = re.compile(r"^The current time is (?P<hour>[1-9]|1[0-2])\:(?P<minutes>[0-5]\d)(?P<am_pm>[ap]m)\.$")
TIME_REGEX = re.compile(r"^(?:(?:It is )?(?P<hour>[1-9]|1[0-2])(?P<am_pm>[ap]m)(?: on ))?\w+\, the (?P<day>\d+)(?:st|[nr]d|th) of (?P<month>\w+)\, [yY]ear (?P<year>\d{4}) of the Third Age\.$")
DAWN_REGEX = re.compile(r"^Light gradually filters in\, proclaiming a new sunrise(?: outside)?\.$")
DAY_REGEX = re.compile(r"^(?:It seems as if )?[Tt]he day has begun\.(?: You feel so weak under the cruel light\!)?$")
DUSK_REGEX = re.compile(r"^The deepening gloom announces another sunset(?: outside)?\.$")
NIGHT_REGEX = re.compile(r"^The last ray of light fades\, and all is swallowed up in darkness\.$|^(?:It seems as if )?[Tt]he night has begun\.(?: You feel stronger in the dark\!)?$")

FIRST_YEAR = 2850
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR
MINUTES_PER_DAY = MINUTES_PER_HOUR * HOURS_PER_DAY
MINUTES_PER_MONTH = MINUTES_PER_DAY * DAYS_PER_MONTH
MINUTES_PER_YEAR = MINUTES_PER_DAY * DAYS_PER_YEAR

MONTHS = [
	{"name": "January", "sindarin": "Ninui", "westron": "Solmath", "dawn": 9, "dusk": 17, "season": "Winter"},
	{"name": "February", "sindarin": "Gwaeron", "westron": "Rethe", "dawn": 8, "dusk": 18, "season": "Late-Winter"},
	{"name": "March", "sindarin": "Gwirith", "westron": "Astron", "dawn": 7, "dusk": 19, "season": "Early-Spring"},
	{"name": "April", "sindarin": "Lothron", "westron": "Thrimidge", "dawn": 7, "dusk": 20, "season": "Spring"},
	{"name": "May", "sindarin": "Norui", "westron": "Forelithe", "dawn": 6, "dusk": 20, "season": "Late-Spring"},
	{"name": "June", "sindarin": "Cerveth", "westron": "Afterlithe", "dawn": 5, "dusk": 21, "season": "Early-Summer"},
	{"name": "July", "sindarin": "Urui", "westron": "Wedmath", "dawn": 4, "dusk": 22, "season": "Summer"},
	{"name": "August", "sindarin": "Ivanneth", "westron": "Halimath", "dawn": 5, "dusk": 21, "season": "Late-Summer"},
	{"name": "September", "sindarin": "Narbeleth", "westron": "Winterfilth", "dawn": 6, "dusk": 20, "season": "Early-Autumn"},
	{"name": "October", "sindarin": "Hithui", "westron": "Blotmath", "dawn": 7, "dusk": 20, "season": "Autumn"},
	{"name": "November", "sindarin": "Girithron", "westron": "Foreyule", "dawn": 7, "dusk": 19, "season": "Late-Autumn"},
	{"name": "December", "sindarin": "Narwain", "westron": "Afteryule", "dawn": 8, "dusk": 18, "season": "Early-Winter"}
]

WEEKDAYS = [
	{"name": "Sunday", "sindarin": "Oranor", "westron": "Sunday"},
	{"name": "Monday", "sindarin": "Orithil", "westron": "Monday"},
	{"name": "Tuesday", "sindarin": "Orgaladhad", "westron": "Trewsday"},
	{"name": "Wednesday", "sindarin": "Ormenel", "westron": "Hevensday"},
	{"name": "Thursday", "sindarin": "Orbelain", "westron": "Mersday"},
	{"name": "Friday", "sindarin": "Oraearon", "westron": "Highday"},
	{"name": "Saturday", "sindarin": "Orgilion", "westron": "Sterday"}
]


def timeToEpoch(year, month, day, hour, minutes):
	"""Returns the epoch for the given game time."""
	return int(time.time()) - ((year - FIRST_YEAR) * MINUTES_PER_YEAR) - (month * MINUTES_PER_MONTH) - ((day - 1) * MINUTES_PER_DAY) - (hour * MINUTES_PER_HOUR) - minutes


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
		day_of_year = month * DAYS_PER_MONTH + day
		hour = minutes // MINUTES_PER_HOUR
		minutes %= MINUTES_PER_HOUR
		ap = "am" if hour < 12 else "pm"
		output.append("Game time {}:{:02d} {}: Dawn: {} am, Dusk: {} pm.".format(hour % 12 if hour % 12 else 12, minutes, ap, MONTHS[month]["dawn"], MONTHS[month]["dusk"] - 12))
		if action == "pull":
			return "pull lever {}\npull lever {}".format(day, MONTHS[month]["westron"])
		elif action is not None:
			return "{} {}".format(action, output[0])
		weekday = WEEKDAYS[(day_of_year + (year - FIRST_YEAR) * DAYS_PER_YEAR) % 7]["name"]
		if hour < MONTHS[month]["dawn"]:
			state = "NIGHT"
			next_state = "DAY"
			till_next_state = MONTHS[month]["dawn"] - hour + 1
		elif hour >= MONTHS[month]["dusk"]:
			state = "NIGHT"
			next_state = "DAY"
			till_next_state = 25 + MONTHS[month]["dawn"] - hour
		elif hour > MONTHS[month]["dawn"] and hour < MONTHS[month]["dusk"]:
			state = "DAY"
			next_state = "NIGHT"
			till_next_state = MONTHS[month]["dusk"] - hour
		elif hour == MONTHS[month]["dawn"]:
			state = "DAWN"
			next_state = "DAY"
			till_next_state = 1
		output.append("It is currently {}, on {}, {} {} ({} / {}), ({}), year {} of the third age.".format(state, weekday, MONTHS[month]["name"], day, MONTHS[month]["westron"], MONTHS[month]["sindarin"], MONTHS[month]["season"], year))
		output.append("Time left until {} is less than {} tick{}".format(next_state, till_next_state, "s" if till_next_state != 1 else "!"))
		next_season_in_mume_days = ((((month + 1) // 3 * 3 + 3) - (month + 1) - 1) * DAYS_PER_MONTH) + (DAYS_PER_MONTH - day) + (1 - (hour // HOURS_PER_DAY))
		next_season_in_rl_hours = (next_season_in_mume_days * HOURS_PER_DAY // MINUTES_PER_HOUR)
		output.append("{} ends in {} mume day{} or {} real-life hour{}.".format(MONTHS[month]["season"][-6:], next_season_in_mume_days, "s" if next_season_in_mume_days != 1 else "", next_season_in_rl_hours, "s" if next_season_in_rl_hours != 1 else ""))
		next_winter_in_mume_days = ((MONTHS_PER_YEAR - (month + 1) % 12 - 1) * DAYS_PER_MONTH) + (DAYS_PER_MONTH - day) + (1 - hour // HOURS_PER_DAY)
		next_winter_in_rl_days = next_winter_in_mume_days * HOURS_PER_DAY // MINUTES_PER_HOUR // HOURS_PER_DAY
		next_winter_in_rl_hours = (next_winter_in_mume_days * HOURS_PER_DAY // MINUTES_PER_HOUR) % HOURS_PER_DAY
		output.append("Next winter starts in {} real-life day{} and {} hour{}.".format(next_winter_in_rl_days, "s" if next_winter_in_rl_days != 1 else "", next_winter_in_rl_hours, "s" if next_winter_in_rl_hours != 1 else ""))
		moon_rise = (day_of_year + 11) % 24
		if hour == moon_rise:
			output.append("Moon is up now!")
		else:
			if hour > moon_rise:
				moon_rise = (day_of_year + 12) % 24
				moon_rise_day = "tomorrow"
			else:
				moon_rise_day = "today"
			moon_rise_ap = "am" if moon_rise < 12 else "pm"
			output.append("Next moon rise {} at {}:00 {} (game time).".format(moon_rise_day, moon_rise % 12 if moon_rise % 12 else 12, moon_rise_ap))
		full_moon_cycle = HOURS_PER_DAY * 24 # Every 24 days
		moon_day = (day_of_year + DAYS_PER_MONTH + 12) % 24
		moon_hour = moon_day * 24 + hour % HOURS_PER_DAY
		next_dk_day = 1
		if moon_hour < 20:
			ticks_until_dk = 17 - moon_hour if moon_hour <= 17 else 0
		elif moon_hour < HOURS_PER_DAY + 21:
			ticks_until_dk = HOURS_PER_DAY + 18 - moon_hour if moon_hour <= HOURS_PER_DAY + 18 else 0
			next_dk_day = 2
		elif moon_hour < HOURS_PER_DAY * 2 + 22:
			ticks_until_dk = HOURS_PER_DAY * 2 + 19 - moon_hour if moon_hour <= HOURS_PER_DAY * 2 + 19 else 0
			next_dk_day = 3
		else:
			ticks_until_dk = full_moon_cycle - moon_hour + 17
		next_dk_in_rl_hours = ticks_until_dk // MINUTES_PER_HOUR
		next_dk_in_rl_minutes = ticks_until_dk % MINUTES_PER_HOUR
		if not ticks_until_dk:
			output.append("DK is open now!")
		else:
			output.append("DK opens in {} real-life hour{} and {} minute{} (day {} of 3).".format(next_dk_in_rl_hours, "s" if next_dk_in_rl_hours != 1 else "", next_dk_in_rl_minutes, "s" if next_dk_in_rl_minutes != 1 else "", next_dk_day))
		return "\n".join(output)
