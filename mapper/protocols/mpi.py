# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging
import os
import subprocess
import sys
import tempfile
import threading

# Local Modules:
from .telnet import escapeIAC
from ..utils import removeFile


MPI_INIT = b"~$#E"


logger = logging.getLogger(__name__)


class MPIHandler(object):
	def __init__(self, processed, remoteSender, outputFormat=None):
		self._processed = processed
		self._remoteSender = remoteSender
		self._isTinTin = outputFormat == "tintin"
		self.MPIBuffer = bytearray()
		self.canInit = threading.Event()
		self.inMPI = threading.Event()
		self._commands = {
			b"E": self._edit,
			b"V": self._view
		}
		self._command = None
		self._length = None
		self._MPIThreads = []
		if sys.platform == "win32":
			self.editor = "notepad"
			self.pager = "notepad"
		else:
			self.editor = os.getenv("TINTINEDITOR", "nano -w")
			self.pager = os.getenv("TINTINPAGER", "less")

	def _sendRemote(self, dataBytes):
		try:
			self._remoteSender(dataBytes)
		except TypeError:
			if isinstance(self._remoteSender, (bytearray, list)):
				self._remoteSender.extend(dataBytes)
			else:
				raise

	def _edit(self, dataBytes):
		session, description, body = dataBytes[1:].split(b"\n", 2)
		with tempfile.NamedTemporaryFile(prefix="mume_editing_", suffix=".txt", delete=False) as fileObj:
			fileObj.write(body.replace(b"\r", b"").replace(b"\n", b"\r\n"))
		lastModified = os.path.getmtime(fileObj.name)
		if self._isTinTin:
			print(f"MPICOMMAND:{self.editor} {fileObj.name}:MPICOMMAND")
			input("Continue:")
		else:
			editorProcess = subprocess.Popen([*self.editor.split(), fileObj.name])
			editorProcess.wait()
		if os.path.getmtime(fileObj.name) == lastModified:
			# The user closed the text editor without saving. Cancel the editing session.
			response = b"C" + session
		else:
			with open(fileObj.name, "rb") as fileObj:
				response = b"E" + session + b"\n" + fileObj.read()
		response = escapeIAC(response.replace(b"\r", b"")).strip() + b"\n"
		removeFile(fileObj)
		self._sendRemote(MPI_INIT + b"E" + str(len(response)).encode("us-ascii") + b"\n" + response)

	def _view(self, dataBytes):
		with tempfile.NamedTemporaryFile(prefix="mume_viewing_", suffix=".txt", delete=False) as fileObj:
			fileObj.write(dataBytes.replace(b"\r", b"").replace(b"\n", b"\r\n"))
		if self._isTinTin:
			print(f"MPICOMMAND:{self.pager} {fileObj.name}:MPICOMMAND")
		else:
			pagerProcess = subprocess.Popen([*self.pager.split(), fileObj.name])
			pagerProcess.wait()
			removeFile(fileObj)

	def handleMPI(self, ordinal):
		if self._command is None:
			# The first byte is the MPI command.
			self._command = bytes([ordinal])
			if self._command not in self._commands:
				# Invalid MPI command.
				self.inMPI.clear()
				self._processed.extend(b"\n" + MPI_INIT + self._command)
				self._command = None
		elif self._length is None and ordinal in b"\n":
			# The buffer contains the length of subsequent bytes to be received.
			try:
				self._length = int(self.MPIBuffer)
				self.MPIBuffer.clear()
			except (TypeError, ValueError):
				# Invalid length.
				self.inMPI.clear()
				self._processed.extend(b"\n" + MPI_INIT + self._command + self.MPIBuffer + b"\n")
				self._command = None
				self.MPIBuffer.clear()
		else:
			self.MPIBuffer.append(ordinal)
			if len(self.MPIBuffer) == self._length:
				# The final byte in the expected MPI data has been received.
				thread = threading.Thread(
					target=self._commands[self._command],
					args=(bytes(self.MPIBuffer),),
					daemon=True
				)
				self._MPIThreads.append(thread)
				self._command = None
				self._length = None
				self.MPIBuffer.clear()
				self.inMPI.clear()
				thread.start()

	def close(self):
		for thread in self._MPIThreads:
			thread.join()
		self._MPIThreads.clear()
