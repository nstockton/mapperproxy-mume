# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
from queue import Empty, Queue
from unittest import TestCase

# Local Modules:
from mapper import MUD_DATA
from mapper.utils import unescapeXML
from mapper.protocols.xml import LF, MPI_INIT, XMLProtocol


class TestXMLProtocol(TestCase):
	def setUp(self):
		name = b"\x1b[34mLower Flet\x1b[0m"
		# fmt: off
		description = (
			b"\x1b[35mBeing close to the ground, this white platform is not encircled by any rail.\x1b[0m" + LF
			+ b"\x1b[35mInstead, beautiful draperies and tapestries hang from the many branches that\x1b[0m" + LF
			+ b"\x1b[35msurround the flet. Swaying gently in the breeze, images on the colourful\x1b[0m" + LF
			+ b"\x1b[35mcloth create a place where one can stand and let the mind wander into the\x1b[0m" + LF
			+ b"\x1b[35mstories told by the everchanging patterns.\x1b[0m" + LF
		)
		dynamic = (
			b"A finely crafted crystal lamp is hanging from a tree branch." + LF
			+ b"An elven caretaker is standing here, offering his guests a rest." + LF
		)
		exits = b"Exits: north." + LF
		magic = b"You feel less protected."
		prompt = b"!f CW&gt;"
		self.rawData = (
			b"<room><name>" + name + b"</name>" + LF
			+ b"<gratuitous><description>" + description + b"</description></gratuitous>"
			+ dynamic
			+ b"</room><exits>" + exits + b"</exits>" + LF
			+ b"<magic>" + magic + b"</magic>" + LF
			+ b"<prompt>" + prompt + b"</prompt>"
		)
		self.normalData = (
			name + LF
			+ dynamic
			+ exits + LF
			+ magic + LF
			+ unescapeXML(prompt, True)
		)
		self.tintinData = (
			b"NAME:" + name + b":NAME" + LF
			+ dynamic
			+ exits + LF
			+ magic + LF
			+ b"PROMPT:" + unescapeXML(prompt, True) + b":PROMPT"
		)
		# fmt: on
		self.expectedEvents = [
			self.createEvent("name", name),
			self.createEvent("description", description),
			self.createEvent("dynamic", dynamic),
			self.createEvent("exits", exits),
			self.createEvent("line", magic),
			self.createEvent("prompt", unescapeXML(prompt, True)),
		]
		self.gameReceives = bytearray()
		self.playerReceives = bytearray()
		self.xml = XMLProtocol(self.gameReceives.extend, self.playerReceives.extend)
		self.eventQueue = Queue()
		self.xml.eventCaller = self.eventQueue.put

	def tearDown(self):
		self.xml.on_connectionLost()
		del self.xml
		self.gameReceives.clear()
		self.playerReceives.clear()

	def parse(self, data):
		self.xml.on_dataReceived(data)
		playerReceives = bytes(self.playerReceives)
		self.playerReceives.clear()
		gameReceives = bytes(self.gameReceives)
		self.gameReceives.clear()
		state = self.xml.state
		self.xml.state = "data"
		return playerReceives, gameReceives, state

	def getEvents(self):
		events = []
		while not self.eventQueue.empty():
			try:
				events.append(self.eventQueue.get(timeout=1))
			except Empty:
				raise AssertionError("Event was not received from the mapper queue within 1 second.")
		return events

	def createEvent(self, name, data):
		return (MUD_DATA, (name, data))

	def testXMLDataReceived(self):
		data = b"Hello World!" + LF
		self.assertEqual(self.playerReceives, b"")
		self.assertEqual(self.gameReceives, b"")
		self.assertEqual(self.xml.state, "data")
		self.xml.outputFormat = "normal"
		self.xml.on_connectionMade()
		self.assertEqual(self.parse(data), (data, MPI_INIT + b"X2" + LF + b"3G" + LF, "data"))
		self.assertEqual(self.getEvents(), [self.createEvent("line", data.rstrip(LF))])
		self.assertEqual(self.parse(self.rawData), (self.normalData, b"", "data"))
		self.assertEqual(self.getEvents(), self.expectedEvents)
		self.xml.outputFormat = "tintin"
		self.assertEqual(self.parse(self.rawData), (self.tintinData, b"", "data"))
		self.assertEqual(self.getEvents(), self.expectedEvents)
		self.xml.outputFormat = "raw"
		self.assertEqual(self.parse(self.rawData), (self.rawData, b"", "data"))
		self.assertEqual(self.getEvents(), self.expectedEvents)
