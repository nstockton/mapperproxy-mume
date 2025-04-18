# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Literal, Union, get_args

# Third-party Modules:
from knickknacks.platforms import get_directory_path

# Local Modules:
from .config import Config
from .typedef import TypeAlias


LITERAL_INTERFACES: TypeAlias = Literal["text", "hc", "sighted"]
INTERFACES: tuple[LITERAL_INTERFACES, ...] = get_args(LITERAL_INTERFACES)
LITERAL_OUTPUT_FORMATS: TypeAlias = Literal["normal", "raw", "tintin"]
OUTPUT_FORMATS: tuple[LITERAL_OUTPUT_FORMATS, ...] = get_args(LITERAL_OUTPUT_FORMATS)


__version__: str = "0.0.0"
if not TYPE_CHECKING:
	with suppress(ImportError):
		from ._version import __version__


cfg: Config = Config()


def levelName(level: Union[str, int, None]) -> str:
	level = level.strip().upper() if isinstance(level, str) else level
	if isinstance(level, int):
		if level < 0 or level > 50:
			return str(logging.getLevelName(0))
		if level <= 5:
			return str(logging.getLevelName(level * 10))
		return str(logging.getLevelName(level - level % 10))
	if level is None or not isinstance(logging.getLevelName(level), int):
		return str(logging.getLevelName(0))
	return level


loggingLevel: str = levelName(cfg.get("logging_level"))
if loggingLevel == logging.getLevelName(0) and cfg.get("logging_level") not in {
	logging.getLevelName(0),
	0,
}:  # Invalid value in the configuration file.
	cfg["logging_level"] = loggingLevel
	cfg.save()

logFile = logging.FileHandler(get_directory_path("debug.log"), mode="a", encoding="utf-8")
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


__all__: list[str] = [
	"__version__",
	"cfg",
]
