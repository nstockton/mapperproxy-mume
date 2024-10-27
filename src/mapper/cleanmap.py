# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re

# Local Modules:
from .mudevents import Handler
from .roomdata.objects import DIRECTIONS, Room
from .typedef import REGEX_MATCH, REGEX_PATTERN


DIRECTION_TITLES: str = "|".join(d.title() for d in DIRECTIONS)
EXIT_REGEX: REGEX_PATTERN = re.compile(rf".*?(?<![#(])(?P<dir>{DIRECTION_TITLES})(?![#)]).*?[ ]+[-] .+")


class ExitsCleaner(Handler):
	"""
	Implements an event handler that cleans erroneously hidden exits.

	This handler uses the output of the 'exits' command in MUME to Check
	if any visible exits are erroneously marked as hidden in the map database.
	Any exits which are found to be erroneously marked as hidden are then cleaned (marked as visible).
	"""

	event: str = "exits"

	def handle(self, text: str) -> None:
		"""
		Handles the incoming text from MUME.

		Args:
			text: The received text from the game.
		"""
		if not self.mapper.autoUpdateRooms or text.startswith("Exits:"):
			return
		for line in text.splitlines():
			match: REGEX_MATCH = EXIT_REGEX.match(line)
			if match is not None:
				room: Room = self.mapper.currentRoom
				direction: str = match.group("dir").lower()
				if (
					self.mapper.isSynced
					and direction in room.exits
					and "hidden" in room.exits[direction].doorFlags
				):
					self.mapper.user_command_secret(f"remove {direction}")
