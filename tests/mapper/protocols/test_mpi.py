# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import re
from typing import Tuple
from unittest import TestCase
from unittest.mock import Mock, call, mock_open, patch
from uuid import uuid4

# Mapper Modules:
from mapper.protocols.mpi import MPI_INIT, MPIProtocol
from mapper.protocols.telnet_constants import LF


BODY: bytes = b"Hello World!"
SAMPLE_TEXTS: Tuple[str, ...] = (
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
		+ " the trees at the base of the hill, this hill offers little view other than a passing glimps of those\n"
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


class TestMPIProtocol(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.mpi: MPIProtocol = MPIProtocol(
			self.gameReceives.extend, self.playerReceives.extend, outputFormat="normal"
		)

	def tearDown(self) -> None:
		self.mpi.on_connectionLost()
		del self.mpi
		self.gameReceives.clear()
		self.playerReceives.clear()

	def parse(self, data: bytes) -> Tuple[bytes, bytes, str]:
		self.mpi.on_dataReceived(data)
		playerReceives: bytes = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives: bytes = bytes(self.gameReceives)
		self.gameReceives.clear()
		state: str = self.mpi.state
		self.mpi.state = "data"
		self.mpi._MPIBuffer.clear()
		return playerReceives, gameReceives, state

	def testMPIState(self) -> None:
		with self.assertRaises(ValueError):
			self.mpi.state = "**junk**"

	# Mock the logger so warnings won't be printed to the console.
	@patch("mapper.protocols.mpi.logger", Mock())
	@patch("mapper.protocols.mpi.threading")
	def testMPIOn_dataReceived(self, mockThreading: Mock) -> None:
		data: bytes = BODY
		self.mpi.outputFormat = "normal"
		self.mpi.on_connectionMade()
		self.assertEqual(self.parse(data), (data, MPI_INIT + b"I" + LF, "data"))
		# When line feed is encountered, state becomes 'newline'.
		self.assertEqual(self.parse(data + LF), (data + LF, b"", "newline"))
		# If data follows line feed and MPI_INIT does not start with data, fall back to state 'data'.
		self.assertEqual(self.parse(data + LF + data), (data + LF + data, b"", "data"))
		# if some but not all of MPI_INIT was  received followed by a line feed, fall back to state 'newline'.
		self.assertEqual(self.parse(LF + MPI_INIT[:1] + LF), (LF + MPI_INIT[:1] + LF, b"", "newline"))
		# if some but not all of MPI_INIT was  received followed by data, fall back to state 'data'.
		self.assertEqual(self.parse(LF + MPI_INIT[:1] + data), (LF + MPI_INIT[:1] + data, b"", "data"))
		# if a line feed is followed by 1 or more bytes of MPI_INIT, but not the final byte, state becomes 'init'.
		# If a line feed is followed by part of MPI_INIT and then junk, state becomes 'data'.
		for i in range(1, len(MPI_INIT)):
			self.mpi.on_dataReceived(LF + MPI_INIT[:i])
			self.assertEqual((self.playerReceives, self.gameReceives, self.mpi.state), (LF, b"", "init"))
			self.mpi.on_dataReceived(b"**junk**")
			self.assertEqual(
				(self.playerReceives, self.gameReceives, self.mpi.state),
				(LF + MPI_INIT[:i] + b"**junk**", b"", "data"),
			)
			self.playerReceives.clear()
			self.mpi.state = "data"
			self.mpi._MPIBuffer.clear()
		# If a line feed is followed by all the bytes of MPI_INIT, state becomes 'command'.
		self.assertEqual(self.parse(LF + MPI_INIT), (LF, b"", "command"))
		# Command is a single byte after MPI_INIT. State then becomes 'length'.
		self.assertEqual(self.parse(LF + MPI_INIT + b"V"), (LF, b"", "length"))
		# Length is the length of the message body as one or more digits, terminated by a line feed.
		# Verify that an empty length or length containing non-digits is properly handled.
		self.assertEqual(self.parse(LF + MPI_INIT + b"V" + LF), (LF + MPI_INIT + b"V" + LF, b"", "newline"))
		self.assertEqual(
			self.parse(LF + MPI_INIT + b"V1t" + LF), (LF + MPI_INIT + b"V1t" + LF, b"", "newline")
		)
		# If length is valid, state becomes 'body'.
		# The body consists of the bytes following length and the line feed.
		# Once <length> bytes are received, state becomes 'data' and the appropriate
		# method is called to handle the MPI message.
		message: bytes = b"%d%b%b" % (len(data), LF, data)
		# Test invalid MPI commands are handled.
		self.assertEqual(
			self.parse(LF + MPI_INIT + b"A" + message), (LF + MPI_INIT + b"A" + message, b"", "data")
		)
		# test valid MPI commands are handled.
		self.assertEqual(self.parse(LF + MPI_INIT + b"V" + message), (LF, b"", "data"))
		mockThreading.Thread.assert_called_once_with(
			target=self.mpi.commandMap[b"V"], args=(data,), daemon=True
		)

	@patch("mapper.protocols.mpi.os.remove")
	@patch("mapper.protocols.mpi.subprocess.Popen")
	@patch("mapper.protocols.mpi.tempfile.NamedTemporaryFile")
	@patch("mapper.protocols.mpi.print")
	def testMPIView(
		self,
		mockPrint: Mock,
		MockNamedTemporaryFile: Mock,
		mockSubprocess: Mock,
		mockRemove: Mock,
	) -> None:
		tempFileName: str = "temp_file_name"
		MockNamedTemporaryFile.return_value.__enter__.return_value.name = tempFileName
		self.assertEqual(self.playerReceives, b"")
		self.assertEqual(self.gameReceives, b"")
		self.assertEqual(self.mpi.state, "data")
		self.mpi.on_connectionMade()
		self.assertEqual(self.parse(b""), (b"", MPI_INIT + b"I" + LF, "data"))
		# Test outputFormat is 'tintin'.
		self.mpi.outputFormat = "tintin"
		self.mpi.view(b"V" + BODY + LF)
		self.assertEqual((b"", b"", "data"), (self.playerReceives, self.gameReceives, self.mpi.state))
		MockNamedTemporaryFile.assert_called_once_with(prefix="mume_viewing_", suffix=".txt", delete=False)
		mockPrint.assert_called_once_with(f"MPICOMMAND:{self.mpi.pager} {tempFileName}:MPICOMMAND")
		MockNamedTemporaryFile.reset_mock()
		# Test outputFormat is *not* 'tintin'.
		self.mpi.outputFormat = "normal"
		self.mpi.view(b"V" + BODY + LF)
		self.assertEqual((b"", b"", "data"), (self.playerReceives, self.gameReceives, self.mpi.state))
		MockNamedTemporaryFile.assert_called_once_with(prefix="mume_viewing_", suffix=".txt", delete=False)
		mockSubprocess.assert_called_once_with((*self.mpi.pager.split(), tempFileName))
		mockSubprocess.return_value.wait.assert_called_once()
		mockRemove.assert_called_once_with(tempFileName)

	@patch("mapper.protocols.mpi.MPIProtocol.postprocess")
	@patch("mapper.protocols.mpi.Config")
	@patch("mapper.protocols.mpi.open", mock_open(read_data=BODY))
	@patch("mapper.protocols.mpi.os.remove")
	@patch("mapper.protocols.mpi.subprocess.Popen")
	@patch("mapper.protocols.mpi.tempfile.NamedTemporaryFile")
	@patch("mapper.protocols.mpi.os.path")
	@patch("mapper.protocols.mpi.input", return_value="")
	@patch("mapper.protocols.mpi.print")
	def testMPIEdit(
		self,
		mockPrint: Mock,
		mockInput: Mock,
		mockOsPath: Mock,
		MockNamedTemporaryFile: Mock,
		mockSubprocess: Mock,
		mockRemove: Mock,
		mockConfig: Mock,
		mockPostprocessor: Mock,
	) -> None:
		session: bytes = b"12345" + LF
		description: bytes = b"description" + LF
		tempFileName: str = "temp_file_name"
		expectedSent: bytes
		MockNamedTemporaryFile.return_value.__enter__.return_value.name = tempFileName
		cfg: dict[str, bool] = {}
		mockConfig.return_value = cfg
		# Make sure we are in the default state.
		self.assertEqual(self.playerReceives, b"")
		self.assertEqual(self.gameReceives, b"")
		self.assertEqual(self.mpi.state, "data")
		self.mpi.on_connectionMade()
		self.assertEqual(self.parse(b""), (b"", MPI_INIT + b"I" + LF, "data"))
		# Test a canceled session.
		expectedSent = MPI_INIT + b"E" + b"%d" % len(b"C" + session) + LF + b"C" + session
		# Same modified time means the file was *not* modified.
		mockOsPath.getmtime.return_value = 1.0
		# Test outputFormat is 'tintin'.
		self.mpi.outputFormat = "tintin"
		self.mpi.edit(b"E" + session + description + BODY + LF)
		self.assertEqual(
			(b"", expectedSent, "data"), (self.playerReceives, self.gameReceives, self.mpi.state)
		)
		self.gameReceives.clear()
		MockNamedTemporaryFile.assert_called_once_with(prefix="mume_editing_", suffix=".txt", delete=False)
		mockPrint.assert_called_once_with(f"MPICOMMAND:{self.mpi.editor} {tempFileName}:MPICOMMAND")
		mockInput.assert_called_once_with("Continue:")
		mockRemove.assert_called_once_with(tempFileName)
		MockNamedTemporaryFile.reset_mock()
		mockPrint.reset_mock()
		mockInput.reset_mock()
		mockRemove.reset_mock()
		# Test outputFormat is *not* 'tintin'.
		self.mpi.outputFormat = "normal"
		self.mpi.edit(b"E" + session + description + BODY + LF)
		self.assertEqual(
			(b"", expectedSent, "data"), (self.playerReceives, self.gameReceives, self.mpi.state)
		)
		self.gameReceives.clear()
		MockNamedTemporaryFile.assert_called_once_with(prefix="mume_editing_", suffix=".txt", delete=False)
		mockSubprocess.assert_called_once_with((*self.mpi.editor.split(), tempFileName))
		mockSubprocess.return_value.wait.assert_called_once()
		mockRemove.assert_called_once_with(tempFileName)
		MockNamedTemporaryFile.reset_mock()
		mockSubprocess.reset_mock()
		mockSubprocess.return_value.wait.reset_mock()
		mockRemove.reset_mock()
		mockOsPath.reset_mock(return_value=True)
		# Test remote editing.
		expectedSent = (
			MPI_INIT + b"E" + b"%d" % len(b"E" + session + BODY + LF) + LF + b"E" + session + BODY + LF
		)
		# Different modified time means the file was modified.
		mockOsPath.getmtime.side_effect = lambda *args: uuid4()
		# Test outputFormat is 'tintin'.
		self.mpi.outputFormat = "tintin"
		self.mpi.edit(b"E" + session + description + BODY + LF)
		self.assertEqual(
			(b"", expectedSent, "data"), (self.playerReceives, self.gameReceives, self.mpi.state)
		)
		self.gameReceives.clear()
		MockNamedTemporaryFile.assert_called_once_with(prefix="mume_editing_", suffix=".txt", delete=False)
		mockPrint.assert_called_once_with(f"MPICOMMAND:{self.mpi.editor} {tempFileName}:MPICOMMAND")
		mockInput.assert_called_once_with("Continue:")
		mockRemove.assert_called_once_with(tempFileName)
		MockNamedTemporaryFile.reset_mock()
		mockPrint.reset_mock()
		mockInput.reset_mock()
		mockRemove.reset_mock()
		# Test outputFormat is *not* 'tintin'.
		self.mpi.outputFormat = "normal"
		self.mpi.edit(b"E" + session + description + BODY + LF)
		self.assertEqual(
			(b"", expectedSent, "data"), (self.playerReceives, self.gameReceives, self.mpi.state)
		)
		self.gameReceives.clear()
		MockNamedTemporaryFile.assert_called_once_with(prefix="mume_editing_", suffix=".txt", delete=False)
		mockSubprocess.assert_called_once_with((*self.mpi.editor.split(), tempFileName))
		mockSubprocess.return_value.wait.assert_called_once()
		mockRemove.assert_called_once_with(tempFileName)
		# confirm pre and post processors were not called since wordwrapping was not defined
		mockPostprocessor.assert_not_called()
		# test given wordwrapping is enabled, processor methods are called
		cfg["wordwrap"] = True
		self.mpi.edit(b"E" + session + description + BODY + LF)
		mockPostprocessor.assert_called_once()
		mockPostprocessor.reset_mock()
		# test given wordwrapping is disabled, processor methods are not called
		cfg["wordwrap"] = False
		mockConfig.get = Mock(return_value=False)
		self.mpi.edit(b"E" + session + description + BODY + LF)
		mockPostprocessor.assert_not_called()


class TestEditorPostprocessor(TestCase):
	def setUp(self) -> None:
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.MPIProtocol = MPIProtocol(
			self.gameReceives.extend, self.playerReceives.extend, outputFormat="normal"
		)
		self.postprocess = self.MPIProtocol.postprocess
		self.getParagraphs = self.MPIProtocol.getParagraphs
		self.collapseSpaces = self.MPIProtocol.collapseSpaces
		self.capitalise = self.MPIProtocol.capitalise
		self.wordwrap = self.MPIProtocol.wordwrap

	def test_postprocessing(self) -> None:
		subfunctionsMock = self.MPIProtocol.collapseSpaces = Mock(wraps=str)  # type: ignore [assignment]
		for sampleText in SAMPLE_TEXTS:
			self.MPIProtocol.postprocess(sampleText)
			textWithoutComments = re.sub(r"(^|(?<=\n))\s*#.*(?=\n|$)", "\0", sampleText)
			textWithoutComments = textWithoutComments.replace("\0\n", "\0")
			paragraphs = [paragraph.rstrip() for paragraph in textWithoutComments.split("\0")]
			expectedCalls = [call(p) for p in paragraphs if p]
			self.assertListEqual(
				subfunctionsMock.mock_calls,
				expectedCalls,
				f"from sample text {bytes(sampleText, 'ANSI')}",  # type: ignore [str-bytes-safe]
			)
			subfunctionsMock.reset_mock()

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
				f"The sentence\n{sentence}\nfrom the sample text\n{sampleText}\nstarts with an uncapitalized letter.",
			)

	def test_wordwrap(self) -> None:
		for sampleText in SAMPLE_TEXTS:
			processedText: str = self.wordwrap(sampleText)
			for line in processedText.split("\n"):
				self.assertLess(
					len(line),
					80,
					f"The line\n{line}\nfrom the sample text\n{sampleText}\nis {len(line)} chars long, which is too long",
				)
