# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from typing import List, Tuple
from unittest import TestCase

# Mapper Modules:
from mapper import MUD_DATA
from mapper.protocols.mpi import MPI_INIT
from mapper.protocols.telnet_constants import LF
from mapper.protocols.xml import LT, XMLProtocol
from mapper.utils import unescapeXMLBytes


EVENT_TYPE = Tuple[int, Tuple[str, bytes]]


class TestXMLProtocol(TestCase):
	def setUp(self) -> None:
		name: bytes = b"\x1b[34mLower Flet\x1b[0m"
		# fmt: off
		description: bytes = (
			b"\x1b[35mBeing close to the ground, this white platform is not encircled by any rail.\x1b[0m" + LF
			+ b"\x1b[35mInstead, beautiful draperies and tapestries hang from the many branches that\x1b[0m" + LF
			+ b"\x1b[35msurround the flet. Swaying gently in the breeze, images on the colourful\x1b[0m" + LF
			+ b"\x1b[35mcloth create a place where one can stand and let the mind wander into the\x1b[0m" + LF
			+ b"\x1b[35mstories told by the everchanging patterns.\x1b[0m" + LF
		)
		detectMagic: bytes = b"\x1b[35mTraces of white tones form the aura of this place.\x1b[0m"
		dynamic: bytes = (
			b"A finely crafted crystal lamp is hanging from a tree branch." + LF
			+ b"An elven caretaker is standing here, offering his guests a rest." + LF
		)
		exits: bytes = b"Exits: north." + LF
		magic: bytes = b"You feel less protected."
		line: bytes = b"Hello world!"
		prompt: bytes = b"!f CW&gt;"
		self.rawData: bytes = (
			b"<room><name>" + name + b"</name>" + LF
			+ b"<gratuitous><description>" + description + b"</description></gratuitous>"
			+ b"<magic>" + detectMagic + b"</magic>" + LF
			+ dynamic
			+ b"<exits>" + exits + b"</exits></room>" + LF
			+ b"<magic>" + magic + b"</magic>" + LF
			+ line + LF
			+ b"<prompt>" + prompt + b"</prompt>"
		)
		self.normalData: bytes = (
			name + LF
			+ detectMagic + LF
			+ dynamic
			+ exits + LF
			+ magic + LF
			+ line + LF
			+ unescapeXMLBytes(prompt)
		)
		self.tintinData: bytes = (
			b"NAME:" + name + b":NAME" + LF
			+ detectMagic + LF
			+ dynamic
			+ exits + LF
			+ magic + LF
			+ line + LF
			+ b"PROMPT:" + unescapeXMLBytes(prompt) + b":PROMPT"
		)
		# fmt: on
		self.expectedEvents: List[EVENT_TYPE] = [
			self.createEvent("name", name),
			self.createEvent("description", description),
			self.createEvent("magic", detectMagic),
			self.createEvent("exits", exits),
			self.createEvent("dynamic", dynamic),
			self.createEvent("magic", magic),
			self.createEvent("line", line),
			self.createEvent("prompt", unescapeXMLBytes(prompt)),
		]
		self.gameReceives: bytearray = bytearray()
		self.playerReceives: bytearray = bytearray()
		self.xml: XMLProtocol = XMLProtocol(self.gameReceives.extend, self.playerReceives.extend)
		self.mapperEvents: List[EVENT_TYPE] = []
		self.xml.eventCaller = self.mapperEvents.append

	def tearDown(self) -> None:
		self.xml.on_connectionLost()
		del self.xml
		self.gameReceives.clear()
		self.playerReceives.clear()

	def parse(self, data: bytes) -> Tuple[bytes, bytes, str]:
		self.xml.on_dataReceived(data)
		playerReceives: bytes = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives: bytes = bytes(self.gameReceives)
		self.gameReceives.clear()
		state: str = self.xml.state
		self.xml.state = "data"
		return playerReceives, gameReceives, state

	def createEvent(self, name: str, data: bytes) -> EVENT_TYPE:
		return MUD_DATA, (name, data)

	def testXMLState(self) -> None:
		with self.assertRaises(ValueError):
			self.xml.state = "**junk**"

	def testXMLOn_dataReceived(self) -> None:
		data: bytes = b"Hello World!" + LF
		self.xml.outputFormat = "normal"
		self.xml.on_connectionMade()
		self.assertEqual(self.parse(data), (data, MPI_INIT + b"X2" + LF + b"3G" + LF, "data"))
		self.assertEqual(self.mapperEvents, [self.createEvent("line", data.rstrip(LF))])
		self.mapperEvents.clear()
		self.assertEqual(self.parse(LT + b"IncompleteTag"), (b"", b"", "tag"))
		self.assertFalse(self.mapperEvents)
		self.assertEqual(self.xml._tagBuffer, b"IncompleteTag")
		self.assertEqual(self.xml._textBuffer, b"")
		self.xml._tagBuffer.clear()
		self.assertEqual(self.parse(self.rawData), (self.normalData, b"", "data"))
		self.assertEqual(self.mapperEvents, self.expectedEvents)
		self.mapperEvents.clear()
		self.xml.outputFormat = "tintin"
		self.assertEqual(self.parse(self.rawData), (self.tintinData, b"", "data"))
		self.assertEqual(self.mapperEvents, self.expectedEvents)
		self.mapperEvents.clear()
		self.xml.outputFormat = "raw"
		self.assertEqual(self.parse(self.rawData), (self.rawData, b"", "data"))
		self.assertEqual(self.mapperEvents, self.expectedEvents)
