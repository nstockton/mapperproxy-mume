# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import _imp
import math
import os
import re
import shutil
import sys
import textwrap
from collections.abc import ByteString, Callable, Sequence
from pydoc import pager
from typing import Any, Optional, Union


DATA_DIRECTORY: str = "mapper_data"
ANSI_COLOR_REGEX: re.Pattern[str] = re.compile(r"\x1b\[[\d;]+m")
WHITE_SPACE_REGEX: re.Pattern[str] = re.compile(r"\s+", flags=re.UNICODE)
INDENT_REGEX: re.Pattern[str] = re.compile(r"^(?P<indent>\s*)(?P<text>.*)", flags=re.UNICODE)


def camelCase(text: str, delimiter: str) -> str:
	"""
	converts text to camel case.

	Args:
		text: The text to be converted.
		delimiter: The delimiter between words.

	Returns:
		The text in camel case.
	"""
	words = text.split(delimiter)
	return "".join((*map(str.lower, words[:1]), *map(str.title, words[1:])))


def minIndent(text: str) -> str:
	"""
	Retrieves the indention characters from the line with the least indention.

	Args:
		text: the text to process.

	Returns:
		The indention characters of the line with the least amount of indention.
	"""
	lines = []
	for line in text.splitlines():
		if line.strip("\r\n"):
			match = INDENT_REGEX.search(line)
			if match is not None:
				lines.append(match.group("indent"))
	return min(lines, default="", key=len)


def formatDocString(
	functionOrString: Union[str, Callable[..., Any]], width: int = 79, prefix: Optional[str] = None
) -> str:
	"""
	Formats a docstring for displaying.

	Args:
		functionOrString: The function containing the docstring, or the docstring its self.
		width: The number of characters to word wrap each line to.
		prefix: One or more characters to use for indention.

	Returns:
		The formatted docstring.
	"""
	if callable(functionOrString):  # It's a function.
		docString = getattr(functionOrString, "__doc__") or ""
	else:  # It's a string.
		docString = functionOrString
	# Remove any empty lines from the beginning, while keeping indention.
	docString = docString.lstrip("\r\n")
	match = INDENT_REGEX.search(docString)
	if match is not None and not match.group("indent"):
		# The first line was not indented.
		# Prefix the first line with the white space from the subsequent, non-empty
		# line with the least amount of indention.
		# This is needed so that textwrap.dedent will work.
		docString = minIndent("\n".join(docString.splitlines()[1:])) + docString
	docString = textwrap.dedent(docString)  # Remove common indention from lines.
	docString = docString.rstrip()  # Remove trailing white space from the end of the docstring.
	# Word wrap long lines, while maintaining existing structure.
	wrappedLines = []
	indentLevel = 0
	lastIndent = ""
	for line in docString.splitlines():
		match = INDENT_REGEX.search(line)
		if match is None:  # pragma: no cover
			continue
		indent, text = match.groups()
		if len(indent) > len(lastIndent):
			indentLevel += 1
		elif len(indent) < len(lastIndent):
			indentLevel -= 1
		lastIndent = indent
		linePrefix = prefix * indentLevel if prefix else indent
		lines = textwrap.wrap(
			text, width=width - len(linePrefix), break_long_words=False, break_on_hyphens=False
		)
		wrappedLines.append(linePrefix + f"\n{linePrefix}".join(lines))
	docString = "\n".join(wrappedLines)
	docString = textwrap.indent(
		docString, prefix=prefix if prefix is not None else ""
	)  # Indent docstring lines with the prefix.
	return docString


def stripAnsi(text: str) -> str:
	"""
	Strips ANSI escape sequences from text.

	Args:
		text: The text to strip ANSI sequences from.

	Returns:
		The text with ANSI escape sequences stripped.
	"""
	return ANSI_COLOR_REGEX.sub("", text)


def simplified(text: str) -> str:
	"""
	Replaces one or more consecutive white space characters with a single space.

	Args:
		text: The text to process.

	Returns:
		The simplified version of the text.
	"""
	return WHITE_SPACE_REGEX.sub(" ", text).strip()


def touch(name: str) -> None:
	"""
	Touches a file.

	I.E. creates the file if it doesn't exist, or updates the modified time of the file if it does.

	Args:
		name: the file name to touch.
	"""
	with open(name, "a"):
		os.utime(name, None)


def padList(lst: Sequence[Any], padding: Any, count: int, fixed: bool = False) -> list[Any]:
	"""
	Pad the right side of a list.

	Args:
		lst: The list to be padded.
		padding: The item to use for padding.
		count: The minimum size of the returned list.
		fixed: True if the maximum size of the returned list should be restricted to count, False otherwise.

	Returns:
		A padded copy of the list.
	"""
	if fixed:
		return [*lst, *[padding] * (count - len(lst))][:count]
	else:
		return [*lst, *[padding] * (count - len(lst))]


def lpadList(lst: Sequence[Any], padding: Any, count: int, fixed: bool = False) -> list[Any]:
	"""
	Pad the left side of a list.

	Args:
		lst: The list to be padded.
		padding: The item to use for padding.
		count: The minimum size of the returned list.
		fixed: True if the maximum size of the returned list should be restricted to count, False otherwise.

	Returns:
		A padded copy of the list.
	"""
	if fixed:
		return [*[padding] * (count - len(lst)), *lst][:count]
	else:
		return [*[padding] * (count - len(lst)), *lst]


def roundHalfAwayFromZero(number: float, decimals: int = 0) -> float:
	"""
	Rounds a float away from 0 if the fractional is 5 or more.

	Note:
		https://realpython.com/python-rounding

	Args:
		number: The number to round.
		decimals: The number of fractional decimal places to round to.

	Returns:
		The number after rounding.
	"""
	multiplier = 10 ** decimals
	return math.copysign(math.floor(abs(number) * multiplier + 0.5) / multiplier, number)


def humanSort(lst: Sequence[str]) -> list[str]:
	"""
	Sorts a list of strings, with numbers sorted according to their numeric value.

	Args:
		lst: The list of strings to be sorted.

	Returns:
		The items of the list, with strings containing numbers sorted according to their numeric value.
	"""
	return sorted(
		lst,
		key=lambda item: [
			int(text) if text.isdigit() else text for text in re.split(r"(\d+)", item, re.UNICODE)
		],
	)


def regexFuzzy(text: Union[str, Sequence[str]]) -> str:
	"""
	Creates a regular expression matching all or part of a string or sequence.

	Args:
		text: The text to be converted.

	Returns:
		A regular expression string matching all or part of the text.
	"""
	if not isinstance(text, (str, Sequence)):
		raise TypeError("Text must be either a string or sequence of strings.")
	elif not text:
		return ""
	elif isinstance(text, str):
		return "(".join(list(text)) + ")?" * (len(text) - 1)
	else:
		return "|".join("(".join(list(item)) + ")?" * (len(item) - 1) for item in text)


def getFreezer() -> Union[str, None]:
	"""
	Determines the name of the library used to freeze the code.

	Note:
		https://github.com/blackmagicgirl/ktools/blob/master/ktools/utils.py

	Returns:
		The name of the library or None.
	"""
	frozen: Union[str, bool, None] = getattr(sys, "frozen", None)
	if frozen and hasattr(sys, "_MEIPASS"):
		return "pyinstaller"
	elif frozen is True:
		return "cx_freeze"
	elif frozen in ("windows_exe", "console_exe", "dll"):
		return "py2exe"
	elif frozen == "macosx_app":
		return "py2app"
	elif hasattr(sys, "importers"):
		return "old_py2exe"
	elif _imp.is_frozen("__main__"):
		return "tools/freeze"
	elif isinstance(frozen, str):
		return f"unknown {frozen}"
	return None


def isFrozen() -> bool:
	"""
	Determines whether the program is running from a frozen copy or from source.

	Returns:
		True if frozen, False otherwise.
	"""
	return bool(getFreezer())


def getDirectoryPath(*args: str) -> str:
	"""
	Retrieves the path of the directory where the program is located.

	Args:
		*args: Positional arguments to be passed to os.join after the directory path.

	Returns:
		The path.
	"""
	if isFrozen():
		path = os.path.dirname(sys.executable)
	else:
		path = os.path.join(os.path.dirname(__file__), os.path.pardir)
	return os.path.realpath(os.path.join(path, *args))


def getDataPath(*args: str) -> str:
	"""
	Retrieves the path of the data directory.

	Args:
		*args: Positional arguments to be passed to os.join after the data path.

	Returns:
		The path.
	"""
	return os.path.realpath(os.path.join(getDirectoryPath(DATA_DIRECTORY), *args))


def decodeBytes(data: bytes) -> str:
	"""
	Decodes UTF-8 or Latin-1 bytes into a string.

	Args:
		data: The data to be decoded.

	Returns:
		The decoded string.
	"""
	if not isinstance(data, ByteString):
		raise TypeError("Data must be a bytes-like object.")
	try:
		return data.decode("utf-8")
	except UnicodeDecodeError:
		return data.decode("latin-1")


def page(lines: Sequence[str]) -> None:
	"""
	Displays lines using the pager if necessary.

	Args:
		lines: The lines to be displayed.
	"""
	# This is necessary in order for lines with embedded new line characters to be properly handled.
	lines = "\n".join(lines).splitlines()
	width, height = shutil.get_terminal_size()
	# Word wrapping to 1 less than the terminal width is necessary to prevent
	# occasional blank lines in the terminal output.
	text = "\n".join(textwrap.fill(line.strip(), width - 1) for line in lines)
	pager(text)