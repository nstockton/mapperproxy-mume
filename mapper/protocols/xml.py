"""
Mume XML Protocol.
"""


# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from typing import AbstractSet, Mapping

# Local Modules:
from .base import Protocol
from .mpi import MPI_INIT
from .telnet_constants import CR_LF, LF
from .. import MUD_DATA
from ..utils import unescapeXML


LT: bytes = b"<"
GT: bytes = b">"


logger: logging.Logger = logging.getLogger(__name__)


class XMLProtocol(Protocol):
	"""
	Implements the Mume XML protocol.
	"""

	states: AbstractSet[str] = frozenset(("data", "tag"))
	"""Valid states for the state machine."""
	modes: Mapping[bytes, bytes] = {
		b"room": b"room",
		b"exits": b"exits",
		b"prompt": b"prompt",
		b"name": b"name",
		b"description": b"description",
		b"terrain": b"terrain",
		b"/exits": None,
		b"/prompt": None,
		b"/room": None,
		b"/name": b"room",
		b"/description": b"room",
		b"/terrain": b"room",
	}
	"""A mapping of XML mode to new XML mode values."""
	tintinReplacements: Mapping[bytes, bytes] = {
		b"prompt": b"PROMPT:",
		b"/prompt": b":PROMPT",
		b"name": b"NAME:",
		b"/name": b":NAME",
		b"tell": b"TELL:",
		b"/tell": b":TELL",
		b"narrate": b"NARRATE:",
		b"/narrate": b":NARRATE",
		b"pray": b"PRAY:",
		b"/pray": b":PRAY",
		b"say": b"SAY:",
		b"/say": b":SAY",
		b"emote": b"EMOTE:",
		b"/emote": b":EMOTE",
	}
	"""A mapping of tag to replacement values for Tintin."""

	def __init__(self, *args, **kwargs) -> None:
		self.outputFormat = kwargs.pop("outputFormat") if "outputFormat" in kwargs else None
		self.eventCaller = kwargs.pop("eventCaller") if "eventCaller" in kwargs else lambda *args: None
		super().__init__(*args, **kwargs)
		self._state: str = "data"
		self._tagBuffer = bytearray()  # Used for start and end tag names.
		self._textBuffer = bytearray()  # Used for the text between start and end tags.
		self._lineBuffer = bytearray()  # Used for non-XML lines.
		self._gratuitous = False
		self._mode = None

	@property
	def state(self) -> str:
		"""
		The state of the state machine.

		Valid values are in `states`.
		"""
		return self._state

	@state.setter
	def state(self, value: str) -> None:
		if value not in self.states:
			raise ValueError(f"'{value}' not in {tuple(sorted(self.states))}")
		self._state = value

	def on_dataReceived(self, data: bytes) -> None:  # NOQA: C901
		outputFormat = self.outputFormat
		appDataBuffer = []
		while data:
			if self.state == "data":
				appData, separator, data = data.partition(LT)
				if outputFormat == "raw" or not self._gratuitous:
					appDataBuffer.append(appData)
				if self._mode is None:
					self._lineBuffer.extend(appData)
					lines = self._lineBuffer.splitlines(True)
					self._lineBuffer.clear()
					if lines and not lines[-1].endswith(LF):
						self._lineBuffer.extend(lines.pop())
					lines = [line.rstrip(CR_LF) for line in lines if line.strip()]
					for line in lines:
						self.on_mapperEvent("line", unescapeXML(line, True))
				else:
					self._textBuffer.extend(appData)
				if separator:
					self.state = "tag"
			elif self.state == "tag":
				appData, separator, data = data.partition(GT)
				self._tagBuffer.extend(appData)
				if not separator:
					# End of tag not reached yet.
					continue
				# End of tag reached.
				tag = bytes(self._tagBuffer)
				self._tagBuffer.clear()
				text = bytes(self._textBuffer)
				self._textBuffer.clear()
				if outputFormat == "raw":
					appDataBuffer.append(LT + tag + GT)
				elif outputFormat == "tintin" and not self._gratuitous:
					appDataBuffer.append(self.tintinReplacements.get(tag, b""))
				if self._mode is None and tag.startswith(b"movement"):
					self.on_mapperEvent("movement", unescapeXML(tag[13:-1], True))
				elif tag == b"gratuitous":
					self._gratuitous = True
				elif tag == b"/gratuitous":
					self._gratuitous = False
				elif tag in self.modes:
					self._mode = self.modes[tag]
					if tag.startswith(b"/"):
						self.on_mapperEvent(
							"dynamic" if tag == b"/room" else tag[1:].decode("us-ascii"), unescapeXML(text, True)
						)
				self.state = "data"
		if appDataBuffer:
			appDataBuffer = b"".join(appDataBuffer)
			if outputFormat == "raw":
				super().on_dataReceived(appDataBuffer)
			else:
				super().on_dataReceived(unescapeXML(appDataBuffer, True))

	def on_connectionMade(self) -> None:
		# Turn on XML mode.
		# Mode "3" tells MUME to enable XML output without sending an initial "<xml>" tag.
		# Option "G" tells MUME to wrap room descriptions in gratuitous tags if they would otherwise be hidden.
		self.write(MPI_INIT + b"X2" + LF + b"3G" + LF)

	def on_mapperEvent(self, name: str, data: bytes) -> None:
		"""
		Sends an event to the mapper thread.

		Args:
			name: The event name.
			data: The payload.
		"""
		self.eventCaller((MUD_DATA, (name, data)))
