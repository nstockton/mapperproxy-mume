# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging
from telnetlib import IAC

# Local Modules:
from .telnet import TelnetHandler
from .mpi import MPI_INIT, MPIHandler
from .xml import XMLHandler
from ..utils import unescapeXML


logger = logging.getLogger(__name__)
__all__ = ["ProtocolHandler"]


class ProtocolHandler(object):
	def __init__(
			self,
			processed=None,
			remoteSender=None,
			eventSender=None,
			outputFormat=None,
			promptTerminator=None
	):
		self._processed = bytearray() if processed is None else processed
		self._remoteSender = bytearray() if remoteSender is None else remoteSender
		self._eventSender = [] if eventSender is None else eventSender
		self._outputFormat = outputFormat
		self._promptTerminator = promptTerminator
		self._unprocessed = bytearray()
		self._telnet = TelnetHandler(self._processed, self._remoteSender, self._promptTerminator)
		self._mpi = MPIHandler(self._processed, self._remoteSender, self._outputFormat)
		self._xml = XMLHandler(self._processed, self._eventSender, self._outputFormat)

	def close(self):
		self._mpi.close()

	def _handleUnprocessed(self, handler):
		for item in self._unprocessed:
			handler(item)
		self._unprocessed.clear()

	def feed(self, dataBytes):
		telnet = self._telnet
		mpi = self._mpi
		xml = self._xml
		unprocessed = self._unprocessed
		for ordinal in dataBytes:
			if telnet.inSubOption.isSet():
				# The byte is part of a sub-negotiation.
				telnet.handleSubOption(ordinal)
			elif telnet.optionNegotiation is not None:
				# The byte is the final byte of a 3-byte option.
				telnet.handleOption(ordinal)
			elif telnet.inCommand.isSet():
				# The byte is the final byte of a 2-byte command, or the second byte of a 3-byte option.
				telnet.handleCommand(ordinal)
				if ordinal in IAC:
					# Escaped IAC.
					unprocessed.append(ordinal)
			elif ordinal in IAC:
				# The byte is the first byte of a 2-byte command / 3-byte option.
				telnet.inCommand.set()
			elif mpi.inMPI.isSet():
				self._handleUnprocessed(mpi.handleMPI)
				mpi.handleMPI(ordinal)
			elif mpi.canInit.isSet() and ordinal in MPI_INIT and MPI_INIT.startswith(mpi.MPIBuffer):
				# Ordinal is one of the bytes in the 4-byte MPI_INIT sequence,
				# and the sequence was preceded by a new-line character (\n).
				mpi.MPIBuffer.append(ordinal)
				if mpi.MPIBuffer == MPI_INIT:
					# Ordinal is the final byte.
					mpi.inMPI.set()
					mpi.MPIBuffer.clear()
					if self._processed.endswith(b"\n"):
						del self._processed[-1]
			else:
				if ordinal in b"\n":
					mpi.canInit.set()
				else:
					mpi.canInit.clear()
				if mpi.MPIBuffer:
					# The Bytes in the buffer are in MPI_INIT, but aren't part of an MPI init sequence.
					unprocessed.extend(mpi.MPIBuffer)
					mpi.MPIBuffer.clear()
				self._handleUnprocessed(xml.handleXML)
				xml.handleXML(ordinal)
		result = bytes(self._processed)
		self._processed.clear()
		return result if self._outputFormat == "raw" else unescapeXML(result, True)
