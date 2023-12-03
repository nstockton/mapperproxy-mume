# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import sys
from queue import SimpleQueue
from typing import TYPE_CHECKING, Tuple, Union

# Third-party Modules:
from mudproto.xml import EVENT_CALLER_TYPE as _XML_EVENT_TYPE


if TYPE_CHECKING:
	# Prevent cyclic import.
	from .roomdata.objects import Room

if sys.version_info < (3, 10):  # pragma: no cover
	from typing_extensions import TypeAlias
else:  # pragma: no cover
	from typing import TypeAlias

if sys.version_info < (3, 9):  # pragma: no cover
	from typing import Callable, Match, Pattern
else:  # pragma: no cover
	from collections.abc import Callable
	from re import Match, Pattern


REGEX_MATCH: TypeAlias = Union[Match[str], None]
REGEX_PATTERN: TypeAlias = Pattern[str]
COORDINATES_TYPE: TypeAlias = Tuple[int, int, int]
MUD_EVENT_HANDLER_TYPE: TypeAlias = Callable[[str], None]
XML_EVENT_TYPE: TypeAlias = _XML_EVENT_TYPE
XML_EVENT_CALLER_TYPE: TypeAlias = Callable[[XML_EVENT_TYPE], None]
MAPPER_QUEUE_EVENT_TYPE: TypeAlias = Union[XML_EVENT_TYPE, None]
MAPPER_QUEUE_TYPE: TypeAlias = "SimpleQueue[MAPPER_QUEUE_EVENT_TYPE]"  # Remove quotes after dropping Py38.
GUI_QUEUE_EVENT_TYPE: TypeAlias = "Union[Tuple[str], Tuple[str, Room], None]"
GUI_QUEUE_TYPE: TypeAlias = "SimpleQueue[GUI_QUEUE_EVENT_TYPE]"  # Remove quotes after dropping Py38.
