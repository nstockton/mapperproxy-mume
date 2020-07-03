# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
from io import StringIO
import os
import sys
import textwrap
import unittest
from unittest import mock

# Local Modules:
from mapper import utils
from mapper.utils import IAC


class TestUtils(unittest.TestCase):
	def test_iterBytes(self):
		sent = b"hello"
		expected = (b"h", b"e", b"l", b"l", b"o")
		self.assertEqual(tuple(utils.iterBytes(sent)), expected)

	def test_minIndent(self):
		self.assertEqual(utils.minIndent("hello\nworld"), "")
		self.assertEqual(utils.minIndent("\thello\n\t\tworld"), "\t")

	def test_formatDocString(self):
		docString = (
			"\nTest Doc String\n"
			+ "This is the first line below the title.\n"
			+ "\tThis is an indented line below the first. "
			+ "Let's make it long so we can check if word wrapping works.\n"
			+ "This is the final line, which should be at indention level 0.\n"
		)
		expectedOutput = (
			"Test Doc String\n"
			+ "This is the first line below the title.\n"
			+ "\tThis is an indented line below the first. Let's make it long so we can check\n"
			+ "\tif word wrapping works.\n"
			+ "This is the final line, which should be at indention level 0."
		)
		testFunction = lambda: None  # NOQA: E731
		testFunction.__docstring__ = docString
		expectedOutputIndentTwoSpace = "\n".join(
			"  " + line.replace("\t", "  ") for line in expectedOutput.splitlines()
		)
		width = 79
		for item in (docString, testFunction):
			self.assertEqual(utils.formatDocString(item, width, prefix=""), expectedOutput)
			self.assertEqual(utils.formatDocString(item, width, prefix="  "), expectedOutputIndentTwoSpace)

	def test_escapeIAC(self):
		sent = b"hello" + IAC + b"world"
		expected = b"hello" + IAC + IAC + b"world"
		self.assertEqual(utils.escapeIAC(sent), expected)
		with self.assertRaises(TypeError):
			utils.escapeIAC(sent.decode("us-ascii", "ignore"))

	def test_stripAnsi(self):
		sent = "\x1b[32mhello\x1b[0m"
		expected = "hello"
		self.assertEqual(utils.stripAnsi(sent), expected)
		with self.assertRaises(TypeError):
			utils.stripAnsi(sent.encode("us-ascii"))

	def test_simplified(self):
		sent = "Hello world\r\nThis  is\ta\r\n\r\ntest."
		expected = "Hello world This is a test."
		self.assertEqual(utils.simplified(sent), expected)
		with self.assertRaises(TypeError):
			utils.simplified(sent.encode("us-ascii"))

	@mock.patch("mapper.utils.os")
	def test_removeFile(self, mockOs):
		# Argument can be a file name as a string.
		utils.removeFile("path_1")
		mockOs.remove.assert_called_with("path_1")
		# Argument can also be a file object.
		fileObj = StringIO()
		fileObj.name = "path_2"
		self.assertFalse(fileObj.closed)
		utils.removeFile(fileObj)
		mockOs.remove.assert_called_with("path_2")
		self.assertTrue(fileObj.closed)

	@mock.patch("mapper.utils.open", mock.mock_open(read_data="data"))
	@mock.patch("mapper.utils.os")
	def test_touch(self, mockOs):
		utils.touch("path_1", None)
		mockOs.utime.assert_called_once_with("path_1", None)

	def test_padList(self):
		lst = [1, 2, 3, 4, 5, 6, 7, 8, 9]
		padding = 0
		# Non-fixed padding with 0's on the right.
		# Returned list will be of length >= *count*.
		self.assertEqual(utils.padList([], padding, count=12, fixed=False, left=False), [0] * 12)
		self.assertEqual(utils.padList(lst, padding, count=12, fixed=False, left=False), lst + [0] * 3)
		self.assertEqual(utils.padList(lst, padding, count=5, fixed=False, left=False), lst)
		# Non-fixed padding with 0's on the left.
		# Returned list will be of length >= *count*.
		self.assertEqual(utils.padList([], padding, count=12, fixed=False, left=True), [0] * 12)
		self.assertEqual(utils.padList(lst, padding, count=12, fixed=False, left=True), [0] * 3 + lst)
		self.assertEqual(utils.padList(lst, padding, count=5, fixed=False, left=True), lst)
		# Fixed padding with 0's on the right.
		# Returned list will be of length == *count*.
		self.assertEqual(utils.padList([], padding, count=12, fixed=True, left=False), [0] * 12)
		self.assertEqual(utils.padList(lst, padding, count=12, fixed=True, left=False), lst + [0] * 3)
		self.assertEqual(utils.padList(lst, padding, count=5, fixed=True, left=False), lst[:5])
		# Fixed padding with 0's on the left.
		# Returned list will be of length == *count*.
		self.assertEqual(utils.padList([], padding, count=12, fixed=True, left=True), [0] * 12)
		self.assertEqual(utils.padList(lst, padding, count=12, fixed=True, left=True), [0] * 3 + lst)
		self.assertEqual(utils.padList(lst, padding, count=5, fixed=True, left=True), lst[:5])

	def test_roundHalfAwayFromZero(self):
		self.assertEqual(utils.roundHalfAwayFromZero(5.4), 5.0)
		self.assertEqual(utils.roundHalfAwayFromZero(5.5), 6.0)
		self.assertEqual(utils.roundHalfAwayFromZero(-5.4), -5.0)
		self.assertEqual(utils.roundHalfAwayFromZero(-5.5), -6.0)

	def test_humanSort(self):
		expectedOutput = [str(i) for i in range(1, 1001)]
		badlySorted = sorted(expectedOutput)
		self.assertEqual(badlySorted[:4], ["1", "10", "100", "1000"])
		self.assertEqual(utils.humanSort(badlySorted), expectedOutput)

	def test_regexFuzzy(self):
		self.assertEqual(utils.regexFuzzy(""), "")
		self.assertEqual(utils.regexFuzzy([]), "")
		self.assertEqual(utils.regexFuzzy([""]), "")
		self.assertEqual(utils.regexFuzzy(["", ""]), "|")
		self.assertEqual(utils.regexFuzzy("east"), "e(a(s(t)?)?)?")
		self.assertEqual(utils.regexFuzzy(["east"]), "e(a(s(t)?)?)?")
		expectedOutput = "e(a(s(t)?)?)?|w(e(s(t)?)?)?"
		self.assertEqual(utils.regexFuzzy(["east", "west"]), expectedOutput)

	@mock.patch("mapper.utils._imp")
	@mock.patch("mapper.utils.sys")
	def test_getFreezer(self, mockSys, mockImp):
		del mockSys.frozen
		del mockSys._MEIPASS
		del mockSys.importers
		mockImp.is_frozen.return_value = True
		self.assertEqual(utils.getFreezer(), "tools/freeze")
		mockImp.is_frozen.return_value = False
		self.assertIs(utils.getFreezer(), None)
		mockSys.importers = True
		self.assertEqual(utils.getFreezer(), "old_py2exe")
		del mockSys.importers
		for item in ("windows_exe", "console_exe", "dll"):
			mockSys.frozen = item
			self.assertEqual(utils.getFreezer(), "py2exe")
		mockSys.frozen = "macosx_app"
		self.assertEqual(utils.getFreezer(), "py2app")
		mockSys.frozen = True
		self.assertEqual(utils.getFreezer(), "cx_freeze")
		mockSys._MEIPASS = "."
		self.assertEqual(utils.getFreezer(), "pyinstaller")

	def test_isFrozen(self):
		self.assertIs(utils.isFrozen(), False)

	@mock.patch("mapper.utils.isFrozen")
	def test_getDirectoryPath(self, mockIsFrozen):
		subdirectory = ("level1", "level2")
		frozenDirName = os.path.dirname(sys.executable)
		frozenOutput = os.path.realpath(os.path.join(frozenDirName, *subdirectory))
		mockIsFrozen.return_value = True
		self.assertEqual(utils.getDirectoryPath(*subdirectory), frozenOutput)
		unfrozenDirName = os.path.join(os.path.dirname(utils.__file__), os.path.pardir)
		unfrozenOutput = os.path.realpath(os.path.join(unfrozenDirName, *subdirectory))
		mockIsFrozen.return_value = False
		self.assertEqual(utils.getDirectoryPath(*subdirectory), unfrozenOutput)

	def test_multiReplace(self):
		replacements = (("ll", "yy"), ("h", "x"), ("o", "z"))
		text = "hello world"
		expectedOutput = "xeyyz wzrld"
		for item in (replacements, dict(replacements)):
			self.assertEqual(utils.multiReplace(text, item), expectedOutput)
		for item in ((), {}):
			self.assertEqual(utils.multiReplace(text, item), text)

	def test_escapeXML(self):
		originalString = "<one&two>three"
		expectedString = "&lt;one&amp;two&gt;three"
		originalBytes = b"<one&two>three"
		expectedBytes = b"&lt;one&amp;two&gt;three"
		self.assertEqual(utils.escapeXML(originalString, False), expectedString)
		self.assertEqual(utils.escapeXML(originalBytes, True), expectedBytes)

	def test_unescapeXML(self):
		originalString = "&lt;one&amp;two&gt;three"
		expectedString = "<one&two>three"
		originalBytes = b"&lt;one&amp;two&gt;three"
		expectedBytes = b"<one&two>three"
		self.assertEqual(utils.unescapeXML(originalString, False), expectedString)
		self.assertEqual(utils.unescapeXML(originalBytes, True), expectedBytes)

	def test_decodeBytes(self):
		characters = "".join(chr(i) for i in range(256))
		self.assertEqual(utils.decodeBytes(characters.encode("latin-1")), characters)
		self.assertEqual(utils.decodeBytes(characters.encode("utf-8")), characters)
		self.assertEqual(utils.decodeBytes(characters), "")

	@mock.patch("mapper.utils.pager")
	@mock.patch("mapper.utils.shutil")
	def test_page(self, mockShutil, mockPager):
		cols, rows = 80, 24
		mockShutil.get_terminal_size.return_value = os.terminal_size((cols, rows))
		lines = [
			"This is the first line.",
			"this is the second line.",
			"123456789 " * 10,
			"123\n567\n9 " * 10,
			"This is the third and final line.",
		]
		lines = "\n".join(lines).splitlines()
		utils.page(lines)
		text = "\n".join(textwrap.fill(line.strip(), cols - 1) for line in lines)
		mockPager.assert_called_once_with(text)
