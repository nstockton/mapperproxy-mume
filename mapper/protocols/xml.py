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
from typing import Any, Callable, Dict, FrozenSet, List, MutableSequence, Tuple, Union

# Local Modules:
from .base import Protocol
from .mpi import MPI_INIT
from .telnet_constants import CR_LF, LF
from .. import MUD_DATA
from ..utils import unescapeXMLBytes


LT: bytes = b"<"
GT: bytes = b">"


logger: logging.Logger = logging.getLogger(__name__)


class XMLProtocol(Protocol):
	"""
	Implements the Mume XML protocol.
	"""

	states: FrozenSet[str] = frozenset(("data", "tag"))
	"""Valid states for the state machine."""
	modes: Dict[bytes, Union[bytes, None]] = {
		b"room": b"room",
		b"/room": None,
		b"name": b"name",
		b"/name": b"room",
		b"description": b"description",
		b"/description": b"room",
		b"terrain": None,
		b"/terrain": b"room",
		b"magic": b"magic",
		b"/magic": None,
		b"exits": b"exits",
		b"/exits": None,
		b"prompt": b"prompt",
		b"/prompt": None,
	}
	"""A mapping of XML mode to new XML mode values."""
	tintinReplacements: Dict[bytes, bytes] = {
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

	def __init__(self, *args: Any, **kwargs: Any) -> None:
		self.outputFormat: Union[str, None] = kwargs.pop("outputFormat") if "outputFormat" in kwargs else None
		self.eventCaller: Callable[[Tuple[int, Tuple[str, bytes]]], None] = (
			kwargs.pop("eventCaller") if "eventCaller" in kwargs else lambda *args: None
		)
		super().__init__(*args, **kwargs)
		self._state: str = "data"
		self._tagBuffer: bytearray = bytearray()  # Used for start and end tag names.
		self._textBuffer: bytearray = bytearray()  # Used for the text between start and end tags.
		self._dynamicBuffer: bytearray = bytearray()  # Used for dynamic room descriptions.
		self._lineBuffer: bytearray = bytearray()  # Used for non-XML lines.
		self._gratuitous: bool = False
		self._inRoom: bool = False
		self._mode: Union[bytes, None] = None

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

	def _handleXMLText(self, data: bytes, appDataBuffer: MutableSequence[bytes]) -> bytes:
		"""
		Handles XML data that is not part of a tag.

		Args:
			data: The received data.
			appDataBuffer: The application level data buffer.

		Returns:
			The remaining data.
		"""
		appData, separator, data = data.partition(LT)
		if self.outputFormat == "raw" or not self._gratuitous:
			appDataBuffer.append(appData)
		if self._mode is None:
			self._lineBuffer.extend(appData)
			lines = self._lineBuffer.splitlines(True)
			self._lineBuffer.clear()
			if lines and not lines[-1].endswith(LF):
				self._lineBuffer.extend(lines.pop())
			lines = [line.rstrip(CR_LF) for line in lines if line.strip()]
			for line in lines:
				self.on_mapperEvent("line", unescapeXMLBytes(line))
		else:
			self._textBuffer.extend(appData)
		if separator:
			self.state = "tag"
		return data

	def _handleXMLTag(self, data: bytes, appDataBuffer: MutableSequence[bytes]) -> bytes:
		"""
		Handles XML data that is part of a tag (I.E. enclosed in '<>').

		Args:
			data: The received data.
			appDataBuffer: The application level data buffer.

		Returns:
			The remaining data.
		"""
		appData, separator, data = data.partition(GT)
		self._tagBuffer.extend(appData)
		if not separator:
			# End of tag not reached yet.
			return data
		tag = bytes(self._tagBuffer)
		self._tagBuffer.clear()
		text = bytes(self._textBuffer)
		self._textBuffer.clear()
		if self.outputFormat == "raw":
			appDataBuffer.append(LT + tag + GT)
		elif self.outputFormat == "tintin" and not self._gratuitous:
			appDataBuffer.append(self.tintinReplacements.get(tag, b""))
		if self._mode is None and tag.startswith(b"movement"):
			self.on_mapperEvent("movement", unescapeXMLBytes(tag[13:-1]))
		elif tag == b"gratuitous":
			self._gratuitous = True
		elif tag == b"/gratuitous":
			self._gratuitous = False
		elif tag == b"room":
			self._inRoom = True
			self._mode = self.modes[tag]
		elif tag == b"/room":
			self._inRoom = False
			self._mode = self.modes[tag]
			self._dynamicBuffer.extend(text)
			self.on_mapperEvent("dynamic", unescapeXMLBytes(bytes(self._dynamicBuffer).lstrip(b"\r\n")))
			self._dynamicBuffer.clear()
		elif tag in self.modes:
			if self._inRoom:
				if tag.startswith(b"/"):
					self.on_mapperEvent(tag[1:].decode("us-ascii"), unescapeXMLBytes(text))
					self._mode = b"room"
				else:
					self._dynamicBuffer.extend(text)
					self._mode = self.modes[tag]
			else:
				if tag.startswith(b"/"):
					self.on_mapperEvent(tag[1:].decode("us-ascii"), unescapeXMLBytes(text))
				self._mode = self.modes[tag]
		self.state = "data"
		return data

	def on_dataReceived(self, data: bytes) -> None:
		appDataBuffer: List[bytes] = []
		while data:
			if self.state == "data":
				data = self._handleXMLText(data, appDataBuffer)
			elif self.state == "tag":
				data = self._handleXMLTag(data, appDataBuffer)
		if appDataBuffer:
			if self.outputFormat == "raw":
				super().on_dataReceived(b"".join(appDataBuffer))
			else:
				super().on_dataReceived(unescapeXMLBytes(b"".join(appDataBuffer)))

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
