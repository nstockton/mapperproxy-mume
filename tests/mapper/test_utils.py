# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import os
import sys
import textwrap
from collections.abc import Callable
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

# Mapper Modules:
from mapper import utils


class MockTestCase(Mock):
	"""
	A mocked version of TestCase.
	"""

	def __init__(self, *args: Any, **kwargs: Any) -> None:
		kwargs["spec_set"] = TestCase
		kwargs["unsafe"] = True
		super().__init__(*args, **kwargs)


class ContainerEmpty(utils.ContainerEmptyMixin, MockTestCase):
	"""
	ContainerEmptyMixin with mocked TestCase.
	"""


class TestUtils(TestCase):
	def test_getXMLAttributes(self) -> None:
		self.assertEqual(
			utils.getXMLAttributes('test1=value1 test2="value2" test3 /'),
			{"test1": "value1", "test2": "value2", "test3": None},
		)

	def test_camelCase(self) -> None:
		self.assertEqual(utils.camelCase("", "_"), "")
		self.assertEqual(utils.camelCase("this_is_a_test", "_"), "thisIsATest")

	def test_clamp(self) -> None:
		self.assertEqual(utils.clamp(10, 5, 20), 10)
		self.assertEqual(utils.clamp(4, 5, 20), 5)
		self.assertEqual(utils.clamp(50, 5, 20), 20)

	def test_minIndent(self) -> None:
		self.assertEqual(utils.minIndent("hello\nworld"), "")
		self.assertEqual(utils.minIndent("\thello\n\t\tworld"), "\t")

	def test_formatDocString(self) -> None:
		docString: str = (
			"\nTest Doc String\n"
			+ "This is the first line below the title.\n"
			+ "\tThis is an indented line below the first. "
			+ "Let's make it long so we can check if word wrapping works.\n"
			+ "This is the final line, which should be at indention level 0.\n"
		)
		expectedOutput: str = (
			"Test Doc String\n"
			+ "This is the first line below the title.\n"
			+ "\tThis is an indented line below the first. Let's make it long so we can check\n"
			+ "\tif word wrapping works.\n"
			+ "This is the final line, which should be at indention level 0."
		)
		testFunction: Callable[[], None] = lambda: None  # NOQA: E731
		testFunction.__doc__ = docString
		expectedOutputIndentTwoSpace: str = "\n".join(
			"  " + line.replace("\t", "  ") for line in expectedOutput.splitlines()
		)
		width: int = 79
		self.assertEqual(utils.formatDocString(docString, width), expectedOutput)
		self.assertEqual(utils.formatDocString(docString, width, prefix=""), expectedOutput)
		self.assertEqual(utils.formatDocString(docString, width, prefix="  "), expectedOutputIndentTwoSpace)
		self.assertEqual(utils.formatDocString(testFunction, width), expectedOutput)
		self.assertEqual(utils.formatDocString(testFunction, width, prefix=""), expectedOutput)
		self.assertEqual(
			utils.formatDocString(testFunction, width, prefix="  "), expectedOutputIndentTwoSpace
		)

	def test_stripAnsi(self) -> None:
		sent: str = "\x1b[32mhello\x1b[0m"
		expected: str = "hello"
		self.assertEqual(utils.stripAnsi(sent), expected)

	def test_simplified(self) -> None:
		sent: str = "Hello world\r\nThis  is\ta\r\n\r\ntest."
		expected: str = "Hello world This is a test."
		self.assertEqual(utils.simplified(sent), expected)

	@patch("mapper.utils.open", mock_open(read_data="data"))
	@patch("mapper.utils.os")
	def test_touch(self, mockOs: Mock) -> None:
		utils.touch("path_1")
		mockOs.utime.assert_called_once_with("path_1", None)

	def test_padList(self) -> None:
		lst: list[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
		padding: int = 0
		# Non-fixed padding with 0's on the right.
		# Returned list will be of length >= *count*.
		self.assertEqual(utils.padList([], padding, count=12, fixed=False), [0] * 12)
		self.assertEqual(utils.padList(lst, padding, count=12, fixed=False), lst + [0] * 3)
		self.assertEqual(utils.padList(lst, padding, count=5, fixed=False), lst)
		# Fixed padding with 0's on the right.
		# Returned list will be of length == *count*.
		self.assertEqual(utils.padList([], padding, count=12, fixed=True), [0] * 12)
		self.assertEqual(utils.padList(lst, padding, count=12, fixed=True), lst + [0] * 3)
		self.assertEqual(utils.padList(lst, padding, count=5, fixed=True), lst[:5])

	def test_lpadList(self) -> None:
		lst: list[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
		padding: int = 0
		# Non-fixed padding with 0's on the left.
		# Returned list will be of length >= *count*.
		self.assertEqual(utils.lpadList([], padding, count=12, fixed=False), [0] * 12)
		self.assertEqual(utils.lpadList(lst, padding, count=12, fixed=False), [0] * 3 + lst)
		self.assertEqual(utils.lpadList(lst, padding, count=5, fixed=False), lst)
		# Fixed padding with 0's on the left.
		# Returned list will be of length == *count*.
		self.assertEqual(utils.lpadList([], padding, count=12, fixed=True), [0] * 12)
		self.assertEqual(utils.lpadList(lst, padding, count=12, fixed=True), [0] * 3 + lst)
		self.assertEqual(utils.lpadList(lst, padding, count=5, fixed=True), lst[:5])

	def test_roundHalfAwayFromZero(self) -> None:
		self.assertEqual(utils.roundHalfAwayFromZero(5.4), 5.0)
		self.assertEqual(utils.roundHalfAwayFromZero(5.5), 6.0)
		self.assertEqual(utils.roundHalfAwayFromZero(-5.4), -5.0)
		self.assertEqual(utils.roundHalfAwayFromZero(-5.5), -6.0)

	def test_humanSort(self) -> None:
		expectedOutput: list[str] = [str(i) for i in range(1, 1001)]
		badlySorted: list[str] = sorted(expectedOutput)
		self.assertEqual(badlySorted[:4], ["1", "10", "100", "1000"])
		self.assertEqual(utils.humanSort(badlySorted), expectedOutput)

	def test_regexFuzzy(self) -> None:
		with self.assertRaises(TypeError):
			utils.regexFuzzy(None)  # type: ignore[arg-type]
		self.assertEqual(utils.regexFuzzy(""), "")
		self.assertEqual(utils.regexFuzzy([]), "")
		self.assertEqual(utils.regexFuzzy([""]), "")
		self.assertEqual(utils.regexFuzzy(["", ""]), "|")
		self.assertEqual(utils.regexFuzzy("east"), "e(a(s(t)?)?)?")
		self.assertEqual(utils.regexFuzzy(["east"]), "e(a(s(t)?)?)?")
		self.assertEqual(utils.regexFuzzy(("east")), "e(a(s(t)?)?)?")
		expectedOutput: str = "e(a(s(t)?)?)?|w(e(s(t)?)?)?"
		self.assertEqual(utils.regexFuzzy(["east", "west"]), expectedOutput)
		self.assertEqual(utils.regexFuzzy(("east", "west")), expectedOutput)

	@patch("mapper.utils._imp")
	@patch("mapper.utils.sys")
	def test_getFreezer(self, mockSys: Mock, mockImp: Mock) -> None:
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
		mockSys.frozen = "some undefined freezer"
		self.assertEqual(utils.getFreezer(), "unknown some undefined freezer")
		mockSys._MEIPASS = "."
		self.assertEqual(utils.getFreezer(), "pyinstaller")

	def test_isFrozen(self) -> None:
		self.assertIs(utils.isFrozen(), False)

	@patch("mapper.utils.isFrozen")
	def test_getDirectoryPath(self, mockIsFrozen: Mock) -> None:
		subdirectory: tuple[str, ...] = ("level1", "level2")
		frozenDirName: str = os.path.dirname(sys.executable)
		frozenOutput: str = os.path.realpath(os.path.join(frozenDirName, *subdirectory))
		mockIsFrozen.return_value = True
		self.assertEqual(utils.getDirectoryPath(*subdirectory), frozenOutput)
		unfrozenDirName: str = os.path.join(os.path.dirname(utils.__file__), os.path.pardir)
		unfrozenOutput: str = os.path.realpath(os.path.join(unfrozenDirName, *subdirectory))
		mockIsFrozen.return_value = False
		self.assertEqual(utils.getDirectoryPath(*subdirectory), unfrozenOutput)

	def test_getDataPath(self) -> None:
		subdirectory: tuple[str, ...] = ("level1", "level2")
		output: str = os.path.realpath(
			os.path.join(utils.getDirectoryPath(utils.DATA_DIRECTORY), *subdirectory)
		)
		self.assertEqual(utils.getDataPath(*subdirectory), output)

	@patch("mapper.utils.pager")
	@patch("mapper.utils.shutil")
	def test_page(self, mockShutil: Mock, mockPager: Mock) -> None:
		cols: int = 80
		rows: int = 24
		mockShutil.get_terminal_size.return_value = os.terminal_size((cols, rows))
		lines: list[str] = [
			"This is the first line.",
			"this is the second line.",
			"123456789 " * 10,
			"123\n567\n9 " * 10,
			"This is the third and final line.",
		]
		lines = "\n".join(lines).splitlines()
		utils.page(lines)
		text: str = "\n".join(textwrap.fill(line.strip(), cols - 1) for line in lines)
		mockPager.assert_called_once_with(text)

	def test_average(self) -> None:
		self.assertEqual(utils.average(range(7)), 3)
		self.assertEqual(utils.average([]), 0)

	def test_removePrefix(self) -> None:
		self.assertEqual(utils.removePrefix("hello", "he"), "llo")
		self.assertEqual(utils.removePrefix("hello", "xx"), "hello")
		self.assertEqual(utils.removePrefix("hello", ""), "hello")

	def test_removeSuffix(self) -> None:
		self.assertEqual(utils.removeSuffix("hello", "lo"), "hel")
		self.assertEqual(utils.removeSuffix("hello", "xx"), "hello")
		self.assertEqual(utils.removeSuffix("hello", ""), "hello")

	def test_ContainerEmptyMixin(self) -> None:
		test = ContainerEmpty()
		test.assertContainerEmpty([])
		test.assertIsInstance.assert_called_once()
		test.assertFalse.assert_called_once()
		test.reset_mock()
		test.assertContainerNotEmpty([])
		test.assertIsInstance.assert_called_once()
		test.assertTrue.assert_called_once()
