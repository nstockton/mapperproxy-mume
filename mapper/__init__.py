# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging

# Local Modules:
from .config import Config


INTERFACES: tuple[str, str, str] = ("text", "hc", "sighted")
OUTPUT_FORMATS: tuple[str, str, str] = ("normal", "raw", "tintin")


def levelName(level: str | int | None) -> str:
	level = level.strip().upper() if isinstance(level, str) else level
	if isinstance(level, int):
		if level < 0 or level > 50:
			return str(logging.getLevelName(0))
		elif level <= 5:
			return str(logging.getLevelName(level * 10))
		else:
			return str(logging.getLevelName(level - level % 10))
	elif level is None or not isinstance(logging.getLevelName(level), int):
		return str(logging.getLevelName(0))
	return level


cfg: Config = Config()
loggingLevel: str = levelName(cfg.get("logging_level"))
if loggingLevel == logging.getLevelName(0) and cfg.get("logging_level") not in (
	logging.getLevelName(0),
	0,
):  # Invalid value in the configuration file.
	cfg["logging_level"] = loggingLevel
	cfg.save()
del cfg

logFile = logging.FileHandler("debug.log", mode="a", encoding="utf-8")
logFile.setLevel(loggingLevel)
formatter = logging.Formatter(
	'{levelname}: from {name} in {threadName}: "{message}" @ {asctime}.{msecs:0f}',
	datefmt="%m/%d/%Y %H:%M:%S",
	style="{",
)
logFile.setFormatter(formatter)

# Define a Handler which writes INFO messages or higher to sys.stderr.
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('{levelname}: from {name} in {threadName}: "{message}"', style="{")
console.setFormatter(formatter)

logging.basicConfig(level=logging.getLevelName(0), handlers=[logFile, console])
