# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mume remote editing over GMCP."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import os
import re
import shutil
import subprocess  # NOQA: S404
import sys
import tempfile
import textwrap
import threading
from collections.abc import Callable
from enum import Enum, auto
from typing import Any


logger: logging.Logger = logging.getLogger(__name__)


class RemoteEditingCommand(Enum):
	"""A remote editing command."""

	EDIT = auto()
	VIEW = auto()


class GMCPRemoteEditing:
	"""Implements support for remote editing over GMCP."""

	def __init__(self, *, outputFormat: str, gmcpSend: Callable[[str, Any], None]) -> None:
		"""
		Defines the constructor.

		Args:
			outputFormat: The output format to be used.
			gmcpSend: A reference to the gmcp_send method of proxy.Game.

		Raises:
			ValueError: Editor or pager not found.
		"""
		self.outputFormat: str = outputFormat
		self.gmcpSend: Callable[[str, Any], None] = gmcpSend
		self._threads: list[threading.Thread] = []
		editors: dict[str, str] = {
			"win32": "notepad.exe",
		}
		pagers: dict[str, str] = {
			"win32": "notepad.exe",
		}
		defaultEditor: str = editors.get(sys.platform, "nano")
		defaultPager: str = pagers.get(sys.platform, "less")
		editor: str | None = shutil.which(os.getenv("VISUAL", "") or os.getenv("EDITOR", defaultEditor))
		pager: str | None = shutil.which(os.getenv("PAGER", defaultPager))
		self._isWordWrapping: bool = False
		if editor is None:  # pragma: no cover
			raise ValueError("Remote editing editor executable not found.")
		if pager is None:  # pragma: no cover
			raise ValueError("Remote editing pager executable not found.")
		self.editor: str = editor
		"""The program to use for editing received text."""
		self.pager: str = pager
		"""The program to use for viewing received read-only text."""

	@property
	def isWordWrapping(self) -> bool:
		"""Specifies whether text should be word wrapped during editing or not."""
		return self._isWordWrapping

	@isWordWrapping.setter
	def isWordWrapping(self, value: bool) -> None:
		self._isWordWrapping = value

	def _edit(self, sessionID: int, title: str, text: str) -> None:
		"""
		Edits text using the program defined in `editor`.

		Args:
			sessionID: The ID of the remote editing session.
			title: The title of the remote editing session.
			text: The text of the remote editing session.
		"""
		logger.debug(f"Editing remote text with ID {sessionID}, title {title!r}, and text {text!r}.")
		# Use windows line endings when editing the file.
		newline: str = "\r\n"
		with tempfile.NamedTemporaryFile(
			"w", encoding="utf-8", newline=newline, prefix="mume_editing_", suffix=".txt", delete=False
		) as tempFileObj:
			filename = tempFileObj.name
			tempFileObj.write(text)
		lastModified = os.path.getmtime(filename)
		if self.outputFormat == "tintin":
			print(f"MPICOMMAND:{self.editor} {filename}:MPICOMMAND")
			input("Continue:")
		else:
			subprocess.run((*self.editor.split(), filename))  # NOQA: PLW1510, S603
		if os.path.getmtime(filename) == lastModified:
			# The user closed the text editor without saving. Cancel the editing session.
			self._cancel(sessionID)
		else:
			with open(filename, encoding="utf-8", newline=newline) as fileObj:
				output: str = fileObj.read()
			if self.isWordWrapping:
				output = self.postprocess(output)
			self._write(sessionID, output.replace("\r", "").strip())
		os.remove(filename)

	def _view(self, title: str, text: str) -> None:
		"""
		Views text using the program defined in `pager`.

		Args:
			title: The title of the remote viewing session.
			text: The text of the remote viewing session.
		"""
		logger.debug(f"Viewing remote text with title {title!r} and text {text!r}.")
		# Use windows line endings when viewing the file.
		newline: str = "\r\n"
		with tempfile.NamedTemporaryFile(
			"w", encoding="utf-8", newline=newline, prefix="mume_viewing_", suffix=".txt", delete=False
		) as fileObj:
			filename = fileObj.name
			fileObj.write(text)
		if self.outputFormat == "tintin":
			print(f"MPICOMMAND:{self.pager} {filename}:MPICOMMAND")
		else:
			subprocess.run((*self.pager.split(), filename))  # NOQA: PLW1510, S603
			os.remove(filename)

	def _cancel(self, sessionID: int) -> None:
		"""
		Cancels a remote editing session.

		Args:
			sessionID: The ID of the remote editing session.
		"""
		logger.debug(f"Canceling remote editing session with ID {sessionID}.")
		self.gmcpSend("MUME.Client.CancelEdit", {"id": sessionID})

	def _write(self, sessionID: int, text: str) -> None:
		"""
		Writes text of a remote editing session back to the game.

		Args:
			sessionID: The ID of the remote editing session.
			text: The edited text of the remote editing session.
		"""
		# The game currently only supports a subset of unicode characters found in Latin-1.
		data = bytes(text, "latin-1", "replace")
		text = str(data, "latin-1")
		logger.debug(f"Writing remote editing session with ID {sessionID} and text {text!r}.")
		self.gmcpSend("MUME.Client.Write", {"id": sessionID, "text": text})

	def start(self, command: RemoteEditingCommand, **kwargs: Any) -> None:
		"""
		Called when a remote editing command is received.

		Args:
			command: The remote editing command.
			**kwargs: Keyword arguments to extract data from.
		"""
		sessionID: int = kwargs.get("id", -1)
		title: str = kwargs.get("title", "")
		text: str = kwargs.get("text", "")
		if command is RemoteEditingCommand.EDIT:
			thread = threading.Thread(target=self._edit, args=(sessionID, title, text), daemon=True)
		elif command is RemoteEditingCommand.VIEW:
			thread = threading.Thread(target=self._view, args=(title, text), daemon=True)
		self._threads.append(thread)
		logger.debug(f"Starting remote editing session thread with command {command.name}.")
		thread.start()

	def close(self) -> None:
		"""Clean up any active editing sessions."""
		logger.debug("Joining remote editing session threads.")
		for thread in self._threads:
			thread.join()
		logger.debug("Remote editing session threads cleared.")
		self._threads.clear()

	def postprocess(self, text: str) -> str:
		"""
		Reformats text before it is sent to the game when wordwrapping is enabled.

		Args:
			text: The text to be processed.

		Returns:
			The text with formatting applied.
		"""
		paragraphs: list[str] = self.getParagraphs(text)
		for i, paragraph in enumerate(paragraphs):
			if not self.isComment(paragraph):
				paragraphs[i] = self.wordWrap(self.capitalise(self.collapseSpaces(paragraph)))
		return "\n".join(paragraphs)

	def getParagraphs(self, text: str) -> list[str]:
		"""
		Extracts paragraphs from a string.

		Args:
			text: The text to analyze.

		Returns:
			The extracted paragraphs.
		"""
		lines: list[str] = text.splitlines()
		lineno: int = 0
		while lineno < len(lines):
			if self.isComment(lines[lineno]):
				if lineno > 0:
					lines[lineno] = "\0" + lines[lineno]
				if lineno + 1 < len(lines):
					lines[lineno] += "\0"
			lineno += 1
		text = "\n".join(lines)
		text = re.sub(r"\0\n\0?", "\0", text)
		lines = [line.rstrip() for line in text.split("\0")]
		return [line for line in lines if line]

	@staticmethod
	def isComment(line: str) -> bool:
		"""
		Determines whether a line is a comment.

		Args:
			line: The line to analyze.

		Returns:
			True if the line is a comment, False otherwise.
		"""
		return line.lstrip().startswith("#")

	@staticmethod
	def collapseSpaces(text: str) -> str:
		"""
		Collapses all consecutive space and tab characters of a string to a single space character.

		Args:
			text: The text to perform the operation on.

		Returns:
			The text with consecutive space and tab characters collapsed.
		"""
		# replace consecutive newlines with a null placeholder
		text = text.replace("\n", "\0")
		# collapse all runs of whitespace into a single space
		text = re.sub(r"[ \t]+", " ", text.strip())
		# reinsert consecutive newlines
		return text.replace("\0", "\n")

	@staticmethod
	def capitalise(text: str) -> str:
		"""
		Capitalizes each sentence in a string.

		Args:
			text: The text to perform sentence capitalization on.

		Returns:
			The text after each sentence has been capitalized.
		"""
		return ". ".join(sentence.capitalize() for sentence in text.split(". "))

	@staticmethod
	def wordWrap(text: str) -> str:
		"""
		Wordwraps text using module-specific settings.

		Args:
			text: The text to be wordwrapped.

		Returns:
			The text with wordwrapping applied.
		"""
		return textwrap.fill(
			text, width=79, drop_whitespace=True, break_long_words=False, break_on_hyphens=False
		)
