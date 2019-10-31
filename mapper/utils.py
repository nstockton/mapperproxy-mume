# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import math
import os
import re
import subprocess
import sys
import textwrap

from . import terminalsize


ANSI_COLOR_REGEX = re.compile(r"\x1b\[[\d;]+m")
WHITE_SPACE_REGEX = re.compile(r"\s+", flags=re.UNICODE)
ESCAPE_XML_STR_ENTITIES = (
	("&", "&amp;"),
	("<", "&lt;"),
	(">", "&gt;")
)
UNESCAPE_XML_STR_ENTITIES = tuple((second, first) for first, second in ESCAPE_XML_STR_ENTITIES)
ESCAPE_XML_BYTES_ENTITIES = tuple(
	(first.encode("us-ascii"), second.encode("us-ascii"))
	for first, second in ESCAPE_XML_STR_ENTITIES
)
UNESCAPE_XML_BYTES_ENTITIES = tuple((second, first) for first, second in ESCAPE_XML_BYTES_ENTITIES)


def formatDocString(func, width=79, prefix=""):
	"""
	Format a docstring to be displayed.
	This function requires that the first non-blank line of the docstring
	starts with the white space prefix to be stripped from each original
	line, such as the docstring for this function.
	"""
	if callable(func):
		docString = func.__docstring__ if func.__docstring__ is not None else ""
	else:
		docString = func
	docString = textwrap.dedent(docString)
	docString = "\n".join(textwrap.wrap(docString, width=width - len(prefix)))
	docString = textwrap.indent(docString, prefix=prefix)
	return docString


def stripAnsi(data):
	return ANSI_COLOR_REGEX.sub("", data)


def simplified(data):
	return WHITE_SPACE_REGEX.sub(" ", data).strip()


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
		return ([padding] * (count - len(lst)) + lst)
	elif fixed:
		return (lst + [padding] * (count - len(lst)))[:count]
	else:
		return (lst + [padding] * (count - len(lst)))


def round_half_away_from_zero(n, decimals=0):
	# https://realpython.com/python-rounding
	multiplier = 10 ** decimals
	return math.copysign(math.floor(abs(n) * multiplier + 0.5) / multiplier, n)


def humanSort(listToSort):
	return sorted(
		listToSort,
		key=lambda item: [
			int(text) if text.isdigit() else text
			for text in re.split(r"(\d+)", item, re.UNICODE)
		]
	)


def regexFuzzy(data):
	if not data:
		return ""
	elif isinstance(data, str):
		return "(".join(list(data)) + ")?" * (len(data) - 1)
	elif isinstance(data, list):
		return "|".join("(".join(list(item)) + ")?" * (len(item) - 1) for item in data)


def getDirectoryPath(directory):
	# This is needed for py2exe
	try:
		if sys.frozen or sys.importers:
			return os.path.join(os.path.dirname(sys.executable), directory)
	except AttributeError:
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", directory)


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
	lines = "\n".join(lines).splitlines()
	width, height = terminalsize.get_terminal_size()
	# Word wrapping to 1 less than the terminal width is necessary to prevent
	# occasional blank lines in the terminal output.
	text = "\n".join(textwrap.fill(line.strip(), width - 1) for line in lines)
	if text.count("\n") + 1 < height:
		print(text)
	else:
		more = subprocess.Popen("more", stdin=subprocess.PIPE, shell=True)
		more.stdin.write(text.encode("utf-8"))
		more.stdin.close()
		more.wait()
