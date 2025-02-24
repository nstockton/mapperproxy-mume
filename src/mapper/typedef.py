# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import sys
from collections.abc import Callable
from queue import SimpleQueue
from re import Match, Pattern
from typing import TYPE_CHECKING, Union

# Third-party Modules:
from knickknacks.typedef import BytesOrStrType, ReMatchType, RePatternType, TypeAlias


if TYPE_CHECKING:  # pragma: no cover
	# Prevent cyclic import.
	from .roomdata.objects import Room


COORDINATES_TYPE: TypeAlias = tuple[int, int, int]
GAME_WRITER_TYPE: TypeAlias = Callable[[bytes], None]
PLAYER_WRITER_TYPE: TypeAlias = Callable[[bytes], None]
MUD_EVENT_HANDLER_TYPE: TypeAlias = Callable[[str], None]
MUD_EVENT_TYPE: TypeAlias = tuple[str, bytes]
MUD_EVENT_CALLER_TYPE: TypeAlias = Callable[[MUD_EVENT_TYPE], None]
MAPPER_QUEUE_EVENT_TYPE: TypeAlias = Union[MUD_EVENT_TYPE, None]
MAPPER_QUEUE_TYPE: TypeAlias = SimpleQueue[MAPPER_QUEUE_EVENT_TYPE]
GUI_QUEUE_EVENT_TYPE: TypeAlias = "Union[tuple[str], tuple[str, Room], None]"
GUI_QUEUE_TYPE: TypeAlias = SimpleQueue[GUI_QUEUE_EVENT_TYPE]


__all__: list[str] = [
	"COORDINATES_TYPE",
	"GAME_WRITER_TYPE",
	"GUI_QUEUE_EVENT_TYPE",
	"GUI_QUEUE_TYPE",
	"MAPPER_QUEUE_EVENT_TYPE",
	"MAPPER_QUEUE_TYPE",
	"MUD_EVENT_CALLER_TYPE",
	"MUD_EVENT_HANDLER_TYPE",
	"MUD_EVENT_TYPE",
	"PLAYER_WRITER_TYPE",
	"BytesOrStrType",
	"ReMatchType",
	"RePatternType",
	"TypeAlias",
]
