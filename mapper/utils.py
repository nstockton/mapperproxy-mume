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
from pydoc import pager
from telnetlib import IAC


ANSI_COLOR_REGEX = re.compile(r"\x1b\[[\d;]+m")
WHITE_SPACE_REGEX = re.compile(r"\s+", flags=re.UNICODE)
INDENT_REGEX = re.compile(r"^(?P<indent>\s*)(?P<text>.*)", flags=re.UNICODE)
ESCAPE_XML_STR_ENTITIES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))
UNESCAPE_XML_STR_ENTITIES = tuple((second, first) for first, second in ESCAPE_XML_STR_ENTITIES)
ESCAPE_XML_BYTES_ENTITIES = tuple(
	(first.encode("us-ascii"), second.encode("us-ascii")) for first, second in ESCAPE_XML_STR_ENTITIES
)
UNESCAPE_XML_BYTES_ENTITIES = tuple((second, first) for first, second in ESCAPE_XML_BYTES_ENTITIES)


def iterBytes(data):
	"""Yield each byte in a bytes-like object."""
	for i in range(len(data)):
		yield data[i : i + 1]


def minIndent(text):
	"""Return the white space used to indent the line with the least amount of indention."""
	return min(
		(INDENT_REGEX.search(line).group("indent") for line in text.splitlines() if line.strip("\r\n")),
		default="",
		key=len,
	)


def formatDocString(functionOrString, width=79, prefix=""):
	"""Format a docstring for displaying."""
	if callable(functionOrString):  # It's a function.
		docString = functionOrString.__docstring__ if functionOrString.__docstring__ is not None else ""
	else:  # It's a string.
		docString = functionOrString
	docString = docString.lstrip("\r\n")  # Remove any empty lines from the beginning, while keeping indention.
	if not INDENT_REGEX.search(docString).group("indent"):
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
		indent, text = INDENT_REGEX.search(line).groups()
		if len(indent) > len(lastIndent):
			indentLevel += 1
		elif len(indent) < len(lastIndent):
			indentLevel -= 1
		lastIndent = indent
		linePrefix = prefix * indentLevel if prefix else indent
		lines = textwrap.wrap(text, width=width - len(linePrefix), break_long_words=False, break_on_hyphens=False)
		wrappedLines.append(linePrefix + f"\n{linePrefix}".join(lines))
	docString = "\n".join(wrappedLines)
	docString = textwrap.indent(docString, prefix=prefix)  # Indent docstring lines with the prefix.
	return docString


def escapeIAC(dataBytes):
	"""Double IAC characters in a bytes or bytearray object to escape them."""
	return dataBytes.replace(IAC, IAC + IAC)


def stripAnsi(data):
	return ANSI_COLOR_REGEX.sub("", data)


def simplified(data):
	return WHITE_SPACE_REGEX.sub(" ", data).strip()


def removeFile(toRemove):
	"""Remove a file, ignoring any errors."""
	try:
		if not toRemove.closed:
			toRemove.close()
		os.remove(toRemove.name)
	except AttributeError:
		os.remove(toRemove)


def touch(name, times=None):
	"""
	Touches a file.
	I.E. creates the file if it doesn't exist, or updates the modified time of the file if it does.
	"""
	with open(name, "a"):
		os.utime(name, times)


def padList(lst, padding, count, fixed=False, left=False):
	"""
	Pad a list with the value of 'padding' so that the list is *at least* 'count' number of items.
	If 'fixed' is True, the number of items in the returned list will be *restricted* to 'count'.
	If 'left' is True, the list will be padded at the left (top), rather than the right (bottom).
	"""
	if left and fixed:
		return ([padding] * (count - len(lst)) + lst)[:count]
	elif left:
		return [padding] * (count - len(lst)) + lst
	elif fixed:
		return (lst + [padding] * (count - len(lst)))[:count]
	else:
		return lst + [padding] * (count - len(lst))


def roundHalfAwayFromZero(n, decimals=0):
	# https://realpython.com/python-rounding
	multiplier = 10 ** decimals
	return math.copysign(math.floor(abs(n) * multiplier + 0.5) / multiplier, n)


def humanSort(listToSort):
	return sorted(
		listToSort,
		key=lambda item: [int(text) if text.isdigit() else text for text in re.split(r"(\d+)", item, re.UNICODE)],
	)


def regexFuzzy(data):
	if not data:
		return ""
	elif isinstance(data, str):
		return "(".join(list(data)) + ")?" * (len(data) - 1)
	elif isinstance(data, list):
		return "|".join("(".join(list(item)) + ")?" * (len(item) - 1) for item in data)


def getFreezer():
	"""Return the name of the package used to freeze the running code or None."""
	# https://github.com/blackmagicgirl/ktools/blob/master/ktools/utils.py
	frozen = getattr(sys, "frozen", None)
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
	return frozen


def isFrozen():
	return bool(getFreezer())


def getDirectoryPath(*subdirectory):
	"""Return the location where the program is running."""
	if isFrozen():
		path = os.path.dirname(sys.executable)
	else:
		path = os.path.join(os.path.dirname(__file__), os.path.pardir)
	return os.path.realpath(os.path.join(path, *subdirectory))


def multiReplace(data, replacements):
	try:
		replacements = replacements.items()
	except AttributeError:
		# replacements is a list of tuples.
		pass
	for pattern, substitution in replacements:
		data = data.replace(pattern, substitution)
	return data


def escapeXML(data, isbytes=False):
	return multiReplace(data, ESCAPE_XML_BYTES_ENTITIES if isbytes else ESCAPE_XML_STR_ENTITIES)


def unescapeXML(data, isbytes=False):
	return multiReplace(data, UNESCAPE_XML_BYTES_ENTITIES if isbytes else UNESCAPE_XML_STR_ENTITIES)


def decodeBytes(data):
	try:
		return data.decode("utf-8")
	except UnicodeDecodeError:
		return data.decode("latin-1")
	except AttributeError:
		return ""


def page(lines):
	"""Output word wrapped lines using the 'more' shell command if necessary."""
	# This is necessary in order for lines with embedded new line characters to be properly handled.
	lines = "\n".join(lines).splitlines()
	width, height = shutil.get_terminal_size()
	# Word wrapping to 1 less than the terminal width is necessary to prevent
	# occasional blank lines in the terminal output.
	text = "\n".join(textwrap.fill(line.strip(), width - 1) for line in lines)
	pager(text)
