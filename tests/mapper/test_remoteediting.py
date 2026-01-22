# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import re
from collections.abc import Callable
from typing import cast
from unittest import TestCase
from unittest.mock import Mock, _Call, call, mock_open, patch
from uuid import uuid4

# Mapper Modules:
from mapper.remoteediting import GMCPRemoteEditing, RemoteEditingCommand


SESSION_ID: int = 123
TITLE: str = "Test title"
TEXT: str = "Test text"
SAMPLE_TEXTS: tuple[str, ...] = (
	"",
	".",
	"..",
	"....",
	"\n",
	"\n\n",
	"\t  \t \n \n",
	(
		"Long, wavey strands of grass flutter over the tops of wildly growing crops. A\n"
		+ "barren, rocky ridge rises southwards, casting a long, pointed shadow over this\n"
		+ "field. A decrepit stone wall appears to have been built over what was once the\n"
		+ "tail end of the ridge, but has now been reduced to little more than a bump in\n"
		+ "the field. To the east and north, the field continues, while in the west it\n"
		+ "comes to an abrupt end at an erradic line of scattered rocks and clumps of\n"
		+ "dirt.\n"
	),
	(
		"A round clearing, Measuring the length of a bow shot from one side to the other, is neatly trimmed "
		+ "out of a circle of hedges In the middle, the grass and soil, in turn, give way to a balding patch "
		+ "of rock swelling up from the Earth. Uncovered to the heights of the sky, the "
		+ "swelling mound peaks at an unusual shrine of stones that look as if they naturally grew "
		+ "out of the mound itself. Green, flowering ivy clothes the shrine, and "
		+ "drapes down the crevices in the rock like long, elaborate braids. "
		+ "Where the mound comes level with the clearing, a circle of majestic trees rises above, "
		+ "crowning the mound with a green ring of broad leaves."
	),
	(
		"A lightly wooded hill divides the Bree forest in the east from the \n"
		+ "road to\n"
		+ "Fornost in the west. Not quite rising to the heights of\n"
		+ " the trees at the base of the hill, "
		+ "this hill offers little view other than a passing glimps of those\n"
		+ "travelling the road directly to the west. Beyond the road, rising above \n"
		+ "the tree canapy, a barren ridge forms a straight line across the horizon. Remnents\n"
		+ "of food stuffs and miscellaneous trifles are scattered around the hilltop,\n"
		+ "although no sign of habitation can be seen.\n"
	),
	(
		"living thing protrudes. In the south, the ground continues without "
		+ "change before falling down to yet more fields, while in the west, the ground levels\n"
	),
	"#",
	"#x.",
	"  #x.",
	"..\n#x",
	"#x\ny",
	"\nt\n",
	"A\nB\n#C\n#d\ne\nf\ng\n#h\\#i\\j",
	"A\nB\nC\n#d\n#e\nf\\g\\#h\\#i\\j",
	(
		"Long, wavey strands of grass flutter over the tops of wildly growing crops. A\n"
		+ "barren, rocky ridge rises southwards, casting a long, pointed shadow over this\n"
		+ "#* eat food\n"
		+ "# you eat the mushroom\n"
		+ "field. A decrepit stone wall appears to have been built over what was once the\n"
		+ "tail end of the ridge, but has now been reduced to little more than a bump in\n"
		+ "the field. To the east and north, the field continues, while in the west it\n"
		+ "comes to an abrupt end at an erradic line of scattered rocks and clumps of\n"
		+ "dirt.\n"
	),
	(
		"A round clearing, Measuring the length of a bow shot from one side to the other, is neatly trimmed "
		+ "out of a circle of hedges In the middle, the grass and soil, in turn, give way to a balding patch "
		+ "of rock swelling up from the Earth. Uncovered to the heights of the sky, the "
		+ "swelling mound peaks at an unusual shrine of stones that look as if they naturally grew "
		+ "out of the mound itself. Green, flowering ivy clothes the shrine, and "
		+ "drapes down the crevices in the rock like long, elaborate braids. "
		+ "Where the mound comes level with the clearing, a circle of majestic trees rises above, "
		+ "crowning the mound with a green ring of broad leaves."
	),
	(
		"A lightly wooded hill divides the Bree forest in the east from the \n"
		+ "road to\n"
		+ "Fornost in the west. Not quite rising to the heights of\n"
		+ "# comment  the trees at the base of the hill, this hill offers little "
		+ "view other than a passing glimps of those\n"
		+ "travelling the road directly to the west. Beyond the road, rising above \n"
		+ "the tree canapy, a barren ridge forms a straight line across the horizon. Remnents\n"
		+ "# another comment of food stuffs and miscellaneous trifles are scattered around the hilltop,\n"
		+ "although no sign of habitation can be seen.\n"
	),
)


class MockStat:
	@property
	def st_mtime(self) -> int:
		"""Returns a different number representing modified time."""
		return uuid4().int


class TestRemoteEditing(TestCase):
	def setUp(self) -> None:
		self.oldLoggerValue = logging.getLogger().getEffectiveLevel()
		logging.disable(logging.CRITICAL)
		self.gmcpRemoteEditing = GMCPRemoteEditing(outputFormat="normal", gmcpSend=lambda *args: None)

	def tearDown(self) -> None:
		del self.gmcpRemoteEditing
		logging.disable(self.oldLoggerValue)

	@patch("mapper.remoteediting.Path.unlink")
	@patch("mapper.remoteediting.subprocess.run")
	@patch("mapper.remoteediting.tempfile.NamedTemporaryFile")
	@patch("mapper.remoteediting.print")
	def testRemoteEditingView(
		self,
		mockPrint: Mock,
		MockNamedTemporaryFile: Mock,
		mockSubprocess: Mock,
		mockUnlink: Mock,
	) -> None:
		tempFileName: str = "temp_file_name"
		MockNamedTemporaryFile.return_value.__enter__.return_value.name = tempFileName
		# Test outputFormat is 'tintin'.
		self.gmcpRemoteEditing.outputFormat = "tintin"
		self.gmcpRemoteEditing._view(TITLE, TEXT)
		MockNamedTemporaryFile.assert_called_once()
		mockPrint.assert_called_once_with(
			f"MPICOMMAND:{self.gmcpRemoteEditing.pager} {tempFileName}:MPICOMMAND"
		)
		MockNamedTemporaryFile.reset_mock()
		# Test outputFormat is *not* 'tintin'.
		self.gmcpRemoteEditing.outputFormat = "normal"
		self.gmcpRemoteEditing._view(TITLE, TEXT)
		MockNamedTemporaryFile.assert_called_once()
		mockSubprocess.assert_called_once_with((*self.gmcpRemoteEditing.pager.split(), tempFileName))
		mockUnlink.assert_called_once_with(missing_ok=True)

	@patch("mapper.remoteediting.Path.open", mock_open(read_data=TEXT))
	@patch("mapper.remoteediting.GMCPRemoteEditing._write")
	@patch("mapper.remoteediting.GMCPRemoteEditing._cancel")
	@patch("mapper.remoteediting.GMCPRemoteEditing.postprocess")
	@patch("mapper.remoteediting.Path.unlink")
	@patch("mapper.remoteediting.subprocess.run")
	@patch("mapper.remoteediting.tempfile.NamedTemporaryFile")
	@patch("mapper.remoteediting.Path.stat")
	@patch("mapper.remoteediting.input", return_value="")
	@patch("mapper.remoteediting.print")
	def testRemoteEditingEdit(
		self,
		mockPrint: Mock,
		mockInput: Mock,
		mockStat: Mock,
		MockNamedTemporaryFile: Mock,
		mockSubprocess: Mock,
		mockUnlink: Mock,
		mockPostprocessor: Mock,
		mock_cancel: Mock,
		mock_write: Mock,
	) -> None:
		tempFileName: str = "temp_file_name"
		MockNamedTemporaryFile.return_value.__enter__.return_value.name = tempFileName
		# Test a canceled session.
		# Same modified time means the file was *not* modified.
		mockStat.return_value.st_mtime = 1.0
		# Test outputFormat is 'tintin'.
		self.gmcpRemoteEditing.outputFormat = "tintin"
		self.gmcpRemoteEditing._edit(SESSION_ID, TITLE, TEXT)
		MockNamedTemporaryFile.assert_called_once()
		mockPrint.assert_called_once_with(
			f"MPICOMMAND:{self.gmcpRemoteEditing.editor} {tempFileName}:MPICOMMAND"
		)
		mockInput.assert_called_once_with("Continue:")
		mock_cancel.assert_called_once_with(SESSION_ID)
		mockUnlink.assert_called_once_with(missing_ok=True)
		MockNamedTemporaryFile.reset_mock()
		mockPrint.reset_mock()
		mockInput.reset_mock()
		mock_cancel.reset_mock()
		mockUnlink.reset_mock()
		# Test outputFormat is *not* 'tintin'.
		self.gmcpRemoteEditing.outputFormat = "normal"
		self.gmcpRemoteEditing._edit(SESSION_ID, TITLE, TEXT)
		MockNamedTemporaryFile.assert_called_once()
		mockSubprocess.assert_called_once_with((*self.gmcpRemoteEditing.editor.split(), tempFileName))
		mock_cancel.assert_called_once_with(SESSION_ID)
		mockUnlink.assert_called_once_with(missing_ok=True)
		MockNamedTemporaryFile.reset_mock()
		mockSubprocess.reset_mock()
		mock_cancel.reset_mock()
		mockUnlink.reset_mock()
		mockStat.reset_mock(return_value=True)
		# Test remote editing.
		# Different modified time means the file was modified.
		mockStat.return_value = MockStat()
		# Test outputFormat is 'tintin'.
		self.gmcpRemoteEditing.outputFormat = "tintin"
		self.gmcpRemoteEditing._edit(SESSION_ID, TITLE, TEXT)
		MockNamedTemporaryFile.assert_called_once()
		mockPrint.assert_called_once_with(
			f"MPICOMMAND:{self.gmcpRemoteEditing.editor} {tempFileName}:MPICOMMAND"
		)
		mockInput.assert_called_once_with("Continue:")
		mock_write.assert_called_once_with(SESSION_ID, TEXT)
		mockUnlink.assert_called_once_with(missing_ok=True)
		MockNamedTemporaryFile.reset_mock()
		mockPrint.reset_mock()
		mockInput.reset_mock()
		mock_write.reset_mock()
		mockUnlink.reset_mock()
		# Test outputFormat is *not* 'tintin'.
		self.gmcpRemoteEditing.outputFormat = "normal"
		self.gmcpRemoteEditing._edit(SESSION_ID, TITLE, TEXT)
		MockNamedTemporaryFile.assert_called_once()
		mockSubprocess.assert_called_once_with((*self.gmcpRemoteEditing.editor.split(), tempFileName))
		mock_write.assert_called_once_with(SESSION_ID, TEXT)
		mockUnlink.assert_called_once_with(missing_ok=True)
		# confirm pre and post processors were not called since wordwrapping was not defined
		mockPostprocessor.assert_not_called()
		# test given wordwrapping is enabled, processor methods are called
		self.gmcpRemoteEditing.isWordWrapping = True
		self.gmcpRemoteEditing._edit(SESSION_ID, TITLE, TEXT)
		mockPostprocessor.assert_called_once()
		mockPostprocessor.reset_mock()
		# test given wordwrapping is disabled, processor methods are not called
		self.gmcpRemoteEditing.isWordWrapping = False
		self.gmcpRemoteEditing._edit(SESSION_ID, TITLE, TEXT)
		mockPostprocessor.assert_not_called()

	def testRemoteEditing_cancel(self) -> None:
		with patch.object(self.gmcpRemoteEditing, "gmcpSend") as mockGMCPSend:
			self.gmcpRemoteEditing._cancel(SESSION_ID)
			mockGMCPSend.assert_called_once_with("MUME.Client.CancelEdit", {"id": SESSION_ID})

	def testRemoteEditing_write(self) -> None:
		with patch.object(self.gmcpRemoteEditing, "gmcpSend") as mockGMCPSend:
			self.gmcpRemoteEditing._write(SESSION_ID, TEXT)
			mockGMCPSend.assert_called_once_with("MUME.Client.Write", {"id": SESSION_ID, "text": TEXT})

	@patch("mapper.remoteediting.threading")
	def testRemoteEditingStartAndClose(self, mockThreading: Mock) -> None:
		kwargs = {"id": SESSION_ID, "title": TITLE, "text": TEXT}
		self.gmcpRemoteEditing.start(RemoteEditingCommand.VIEW, **kwargs)
		mockThreading.Thread.assert_called_once_with(
			target=self.gmcpRemoteEditing._view, args=(TITLE, TEXT), daemon=True
		)
		viewThread = cast(Mock, self.gmcpRemoteEditing._threads[-1])
		viewThread.start.assert_called_once()
		mockThreading.Thread.reset_mock()
		self.gmcpRemoteEditing.start(RemoteEditingCommand.EDIT, **kwargs)
		mockThreading.Thread.assert_called_once_with(
			target=self.gmcpRemoteEditing._edit, args=(SESSION_ID, TITLE, TEXT), daemon=True
		)
		editThread = cast(Mock, self.gmcpRemoteEditing._threads[-1])
		editThread.start.assert_called_once()
		mockThreading.Thread.reset_mock()
		self.gmcpRemoteEditing.close()
		viewThread.join.assert_called()
		editThread.join.assert_called()


class TestEditorPostprocessor(TestCase):
	def setUp(self) -> None:
		self.gmcpRemoteEditing = GMCPRemoteEditing(outputFormat="normal", gmcpSend=lambda *args: None)
		self.postprocess = self.gmcpRemoteEditing.postprocess
		self.getParagraphs = self.gmcpRemoteEditing.getParagraphs
		self.collapseSpaces = self.gmcpRemoteEditing.collapseSpaces
		self.capitalise = self.gmcpRemoteEditing.capitalise
		self.wordWrap = self.gmcpRemoteEditing.wordWrap

	def test_postprocessing(self) -> None:
		with patch.object(self.gmcpRemoteEditing, "collapseSpaces", Mock(wraps=str)) as collapseSpacesMock:
			for sampleText in SAMPLE_TEXTS:
				self.gmcpRemoteEditing.postprocess(sampleText)
				textWithoutComments: str = re.sub(r"(^|(?<=\n))\s*#.*(?=\n|$)", "\0", sampleText)
				textWithoutComments = textWithoutComments.replace("\0\n", "\0")
				paragraphs: list[str] = [paragraph.rstrip() for paragraph in textWithoutComments.split("\0")]
				expectedCalls: list[Callable[[str], _Call]] = [call(p) for p in paragraphs if p]
				self.assertListEqual(
					collapseSpacesMock.mock_calls,
					expectedCalls,
					f"from sample text {sampleText.encode('us-ascii')!r}",
				)
				collapseSpacesMock.reset_mock()

	def test_whenCollapsingSpaces_thenEachNewlineIsPreserved(self) -> None:
		for sampleText in SAMPLE_TEXTS:
			processedText: str = self.collapseSpaces(sampleText)
			self.assertEqual(
				processedText.count("\n"),
				sampleText.count("\n"),
				f"processed text:\n{processedText}\nsample text:\n{sampleText}\n",
			)

	def test_capitalisation(self) -> None:
		for sampleText in SAMPLE_TEXTS:
			processedText: str = self.capitalise(sampleText)
		for sentence in processedText.split(". "):
			self.assertTrue(
				sentence[0].isupper() or not sentence[0].isalpha(),
				(
					f"The sentence\n{sentence}\nfrom the sample text\n{sampleText}\n"
					+ "starts with an uncapitalized letter."
				),
			)

	def test_wordwrap(self) -> None:
		for sampleText in SAMPLE_TEXTS:
			processedText: str = self.wordWrap(sampleText)
			for line in processedText.split("\n"):
				self.assertLess(
					len(line),
					80,
					(
						f"The line\n{line}\nfrom the sample text\n{sampleText}\nis {len(line)} "
						+ "chars long, which is too long"
					),
				)
