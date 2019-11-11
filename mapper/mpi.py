# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import os
import subprocess
import sys
from telnetlib import IAC
import tempfile
import threading

from .utils import removeFile


MPI_INIT = b"~$#E"


class MPI(threading.Thread):
	def __init__(self, client, server, isTinTin, command, data):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self.isTinTin = bool(isTinTin)
		self.command = command
		self.data = data
		if sys.platform == "win32":
			self.editor = "notepad"
			self.pager = "notepad"
		else:
			self.editor = os.getenv("TINTINEDITOR", "nano -w")
			self.pager = os.getenv("TINTINPAGER", "less")

	def run(self):
		if self.command == b"V":
			with tempfile.NamedTemporaryFile(suffix=".txt", prefix="mume_viewing_", delete=False) as fileObj:
				fileObj.write(self.data.replace(b"\n", b"\r\n"))
			if self.isTinTin:
				print("MPICOMMAND:{} {}:MPICOMMAND".format(self.pager, fileObj.name))
			else:
				pagerProcess = subprocess.Popen(self.pager.split() + [fileObj.name])
				pagerProcess.wait()
				removeFile(fileObj)
		elif self.command == b"E":
			session, description, body = self.data[1:].split(b"\n", 2)
			with tempfile.NamedTemporaryFile(suffix=".txt", prefix="mume_editing_", delete=False) as fileObj:
				fileObj.write(body.replace(b"\n", b"\r\n"))
			lastModified = os.path.getmtime(fileObj.name)
			if self.isTinTin:
				print("MPICOMMAND:{} {}:MPICOMMAND".format(self.editor, fileObj.name))
				input("Continue:")
			else:
				editorProcess = subprocess.Popen(self.editor.split() + [fileObj.name])
				editorProcess.wait()
			if os.path.getmtime(fileObj.name) == lastModified:
				# The user closed the text editor without saving. Cancel the editing session.
				response = b"C" + session
			else:
				with open(fileObj.name, "rb") as fileObj:
					response = b"E" + session + b"\n" + fileObj.read()
			response = response.replace(b"\r", b"").replace(IAC, IAC + IAC).strip() + b"\n"
			self._server.sendall(MPI_INIT + b"E" + str(len(response)).encode("us-ascii") + b"\n" + response)
			removeFile(fileObj)
