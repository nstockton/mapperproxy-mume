# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging

# Local Modules:
from .telnet import TelnetHandler
from .mpi import MPIHandler
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
		self._eventSender = list() if eventSender is None else eventSender
		self._outputFormat = outputFormat
		self._promptTerminator = promptTerminator
		self.handlers = []
		self._telnet = TelnetHandler(self._processed, self._remoteSender, self._promptTerminator)
		self.handlers.append(self._telnet.parse)
		self._mpi = MPIHandler(self._processed, self._remoteSender, self._outputFormat)
		self.handlers.append(self._mpi.parse)
		self._xml = XMLHandler(self._processed, self._eventSender, self._outputFormat)
		self.handlers.append(self._xml.parse)

	def close(self):
		self._mpi.close()

	__del__ = close

	def notify(self, value):
		for handler in self.handlers:
			try:
				value = handler(value)
				if value is None:
					break
			except TypeError:
				value = [handler(i) for i in value]
				if not value:
					break
		else:
			# Loop was completed without break.
			return value

	def parse(self, dataBytes):
		for ordinal in dataBytes:
			self.notify(ordinal)
		result = bytes(self._processed)
		self._processed.clear()
		return result if self._outputFormat == "raw" else unescapeXML(result, True)
