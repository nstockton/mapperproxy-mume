# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import _imp
import codecs
import math
import os
import re
import shutil
import statistics
import sys
import textwrap
from collections.abc import Callable, Container, Iterable, Sequence
from contextlib import suppress
from pydoc import pager
from typing import Any, Optional, Union


DATA_DIRECTORY: str = "mapper_data"
ANSI_COLOR_REGEX: re.Pattern[str] = re.compile(r"\x1b\[[\d;]+m")
WHITE_SPACE_REGEX: re.Pattern[str] = re.compile(r"\s+", flags=re.UNICODE)
INDENT_REGEX: re.Pattern[str] = re.compile(r"^(?P<indent>\s*)(?P<text>.*)", flags=re.UNICODE)
XML_ATTRIBUTE_REGEX: re.Pattern[str] = re.compile(r"([\w-]+)(\s*=+\s*('[^']*'|\"[^\"]*\"|(?!['\"])[^\s]*))?")
# Latin-1 replacement values taken from the MUME help page.
# https://mume.org/help/latin1
LATIN_ENCODING_REPLACEMENTS: dict[str, bytes] = {
	"\u00a0": b" ",
	"\u00a1": b"!",
	"\u00a2": b"c",
	"\u00a3": b"L",
	"\u00a4": b"$",
	"\u00a5": b"Y",
	"\u00a6": b"|",
	"\u00a7": b"P",
	"\u00a8": b'"',
	"\u00a9": b"C",
	"\u00aa": b"a",
	"\u00ab": b"<",
	"\u00ac": b",",
	"\u00ad": b"-",
	"\u00ae": b"R",
	"\u00af": b"-",
	"\u00b0": b"d",
	"\u00b1": b"+",
	"\u00b2": b"2",
	"\u00b3": b"3",
	"\u00b4": b"'",
	"\u00b5": b"u",
	"\u00b6": b"P",
	"\u00b7": b"*",
	"\u00b8": b",",
	"\u00b9": b"1",
	"\u00ba": b"o",
	"\u00bb": b">",
	"\u00bc": b"4",
	"\u00bd": b"2",
	"\u00be": b"3",
	"\u00bf": b"?",
	"\u00c0": b"A",
	"\u00c1": b"A",
	"\u00c2": b"A",
	"\u00c3": b"A",
	"\u00c4": b"A",
	"\u00c5": b"A",
	"\u00c6": b"A",
	"\u00c7": b"C",
	"\u00c8": b"E",
	"\u00c9": b"E",
	"\u00ca": b"E",
	"\u00cb": b"E",
	"\u00cc": b"I",
	"\u00cd": b"I",
	"\u00ce": b"I",
	"\u00cf": b"I",
	"\u00d0": b"D",
	"\u00d1": b"N",
	"\u00d2": b"O",
	"\u00d3": b"O",
	"\u00d4": b"O",
	"\u00d5": b"O",
	"\u00d6": b"O",
	"\u00d7": b"*",
	"\u00d8": b"O",
	"\u00d9": b"U",
	"\u00da": b"U",
	"\u00db": b"U",
	"\u00dc": b"U",
	"\u00dd": b"Y",
	"\u00de": b"T",
	"\u00df": b"s",
	"\u00e0": b"a",
	"\u00e1": b"a",
	"\u00e2": b"a",
	"\u00e3": b"a",
	"\u00e4": b"a",
	"\u00e5": b"a",
	"\u00e6": b"a",
	"\u00e7": b"c",
	"\u00e8": b"e",
	"\u00e9": b"e",
	"\u00ea": b"e",
	"\u00eb": b"e",
	"\u00ec": b"i",
	"\u00ed": b"i",
	"\u00ee": b"i",
	"\u00ef": b"i",
	"\u00f0": b"d",
	"\u00f1": b"n",
	"\u00f2": b"o",
	"\u00f3": b"o",
	"\u00f4": b"o",
	"\u00f5": b"o",
	"\u00f6": b"o",
	"\u00f7": b"/",
	"\u00f8": b"o",
	"\u00f9": b"u",
	"\u00fa": b"u",
	"\u00fb": b"u",
	"\u00fc": b"u",
	"\u00fd": b"y",
	"\u00fe": b"t",
	"\u00ff": b"y",
}
LATIN_DECODING_REPLACEMENTS: dict[int, str] = {
	ord(k): str(v, "us-ascii") for k, v in LATIN_ENCODING_REPLACEMENTS.items()
}


def latin2ascii(error: Any) -> tuple[Union[bytes, str], int]:
	if isinstance(error, UnicodeEncodeError):
		# Return value can be bytes or a string.
		return LATIN_ENCODING_REPLACEMENTS.get(error.object[error.start], b"?"), error.start + 1
	else:  # UnicodeDecodeError.
		# Return value must be a string.
		return LATIN_DECODING_REPLACEMENTS.get(error.object[error.start], "?"), error.start + 1


codecs.register_error("latin2ascii", latin2ascii)


def getXMLAttributes(text: str) -> dict[str, Union[str, None]]:
	"""
	Extracts XML attributes from a tag.

	The supplied string must only contain attributes, not the tag name.

		Note:
			Adapted from the html.parser module of the Python standard library.

	Args:
		text: The text to be parsed.

	Returns:
		The extracted attributes.
	"""
	attributes: dict[str, Union[str, None]] = {}
	for name, rest, value in XML_ATTRIBUTE_REGEX.findall(text):
		if not rest:
			value = None
		elif value[:1] == "'" == value[-1:] or value[:1] == '"' == value[-1:]:
			value = value[1:-1]
		attributes[name.lower()] = value
	return attributes


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
	multiplier = 10**decimals
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
	Decodes bytes into a string.

	If data contains Latin-1 characters, they will be replaced with ASCII equivalents.

	Args:
		data: The data to be decoded.

	Returns:
		The decoded string.
	"""
	if not isinstance(data, (bytes, bytearray)):
		raise TypeError("Data must be a bytes-like object.")
	with suppress(UnicodeDecodeError):
		return str(data, "us-ascii")
	try:
		# If UTF-8, re-encode the data before decoding because of multi-byte code points.
		return data.decode("utf-8").encode("us-ascii", "latin2ascii").decode("us-ascii")
	except UnicodeDecodeError:
		# Assume data is Latin-1.
		return str(data, "us-ascii", "latin2ascii")


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


def average(items: Iterable[float]) -> float:
	"""
	Calculates the average item length of an iterable.

	Args:
		items: The iterable of items.

	Returns:
		The average item length.
	"""
	try:
		return statistics.mean(items)
	except statistics.StatisticsError:
		# No items.
		return 0


class ContainerEmptyMixin:
	"""
	A mixin class to be used in unit tests.
	"""

	assertIsInstance: Callable[..., Any]
	assertTrue: Callable[..., Any]
	assertFalse: Callable[..., Any]

	def assertContainerEmpty(self, obj: Container[Any]) -> None:
		"""
		Asserts whether the given object is an empty container.

		Args:
			obj: The object to test.
		"""
		self.assertIsInstance(obj, Container)
		self.assertFalse(obj)

	def assertContainerNotEmpty(self, obj: Container[Any]) -> None:
		"""
		Asserts whether the given object is a non-empty container.

		Args:
			obj: The object to test.
		"""
		self.assertIsInstance(obj, Container)
		self.assertTrue(obj)
