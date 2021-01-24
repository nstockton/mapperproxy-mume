# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from typing import Tuple, Union

# Local Modules:
from .config import Config


INTERFACES: Tuple[str, str, str] = ("text", "hc", "sighted")
OUTPUT_FORMATS: Tuple[str, str, str] = ("normal", "raw", "tintin")
USER_DATA: int = 0
USER_DATA_TYPE = bytes
MUD_DATA: int = 1
MUD_DATA_TYPE = Tuple[str, bytes]
MAPPER_QUEUE_TYPE = Union[Tuple[None, None], Tuple[int, Union[MUD_DATA_TYPE, USER_DATA_TYPE]]]


cfg: Config = Config()
debugLevel: Union[str, int, None] = cfg.get("debug_level")
if isinstance(debugLevel, int):
	if debugLevel < 0 or debugLevel > 50:
		debugLevel = None
	elif debugLevel <= 5:
		debugLevel *= 10
	else:
		debugLevel -= debugLevel % 10
elif isinstance(debugLevel, str):
	if not isinstance(logging.getLevelName(debugLevel.upper()), int):
		debugLevel = None
else:
	debugLevel = None
if debugLevel is None and cfg.get("debug_level") is not None:  # Invalid value in the configuration file.
	cfg["debug_level"] = debugLevel
	cfg.save()
del cfg


if debugLevel is not None:
	logging.basicConfig(
		filename="debug.log",
		filemode="w",
		level=debugLevel,
		format='{levelname}: from {name} in {threadName}: "{message}" @ {asctime}.{msecs:0f}',
		style="{",
		datefmt="%m/%d/%Y %H:%M:%S",
	)
	logging.info("Initializing")
else:
	del logging
