# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import socket
import unittest
from queue import Empty, Queue
from unittest.mock import Mock, call

# Mapper Modules:
from mapper import MUD_DATA
from mapper.main import Game
from mapper.protocols.mpi import MPI_INIT
from mapper.protocols.proxy import ProtocolHandler
from mapper.protocols.telnet_constants import (
	CHARSET,
	CHARSET_ACCEPTED,
	CR_LF,
	DO,
	GA,
	IAC,
	LF,
	NAWS,
	SB,
	SE,
	TTYPE,
	TTYPE_SEND,
	WILL,
)


# The initial output of MUME. Used by the server thread to detect connection success.
INITIAL_OUTPUT = [
	IAC + DO + TTYPE,
	IAC + DO + NAWS,
]
WELCOME_MESSAGE = CR_LF + b"                              ***  MUME VIII  ***" + CR_LF + CR_LF


class TestGameThread(unittest.TestCase):
	def testGameThread(self):
		# fmt: off
		initialConfiguration = (  # What the server thread sends MUME on connection success.
			IAC + WILL + CHARSET
			# Tell the Mume server to put IAC-GA at end of prompts.
			+ MPI_INIT + b"P2" + LF + b"G" + LF
			# Identify for Mume Remote Editing.
			+ MPI_INIT + b"I" + LF
			# Turn on XML mode.
			+ MPI_INIT + b"X2" + LF + b"3G" + LF
		)
		# fmt: on
		outputToPlayer = Queue()
		outputFromMume = Queue()
		inputToMume = Queue()
		mumeSocket = Mock(spec=socket.socket)
		mumeSocket.recv.side_effect = lambda arg: outputFromMume.get()
		mumeSocket.sendall.side_effect = lambda data: inputToMume.put(data)
		clientSocket = Mock(spec=socket.socket)
		clientSocket.sendall.side_effect = lambda data: outputToPlayer.put(data)
		mapperThread = Mock()
		mapperThread.interface = "text"
		proxy = ProtocolHandler(
			clientSocket,
			mumeSocket,
			outputFormat="normal",
			promptTerminator=IAC + GA,
			isEmulatingOffline=False,
			mapperCommands=[],
			eventCaller=mapperThread.queue.put,
		)
		proxy.connect()
		mapperThread.proxy = proxy
		gameThread = Game(mumeSocket, mapperThread)
		gameThread.daemon = (
			True  # otherwise if this does not terminate, it prevents unittest from terminating
		)
		gameThread.start()
		# test initial telnet negotiations were passed to the client
		try:
			for item in INITIAL_OUTPUT:
				outputFromMume.put(item)
				data = outputToPlayer.get(timeout=1)
				self.assertEqual(data, item)
		except Empty:
			raise AssertionError("initial telnet negotiations were not passed to the client")
		# test when the server sends its initial negotiations, the server thread outputs its initial configuration
		try:
			while initialConfiguration:
				data = inputToMume.get(timeout=1)
				self.assertIn(data, initialConfiguration, f"Unknown initial configuration: {data!r}")
				initialConfiguration = initialConfiguration.replace(data, b"", 1)
		except Empty:
			errorMessage = (
				"The server thread did not output the expected number of configuration parameters.",
				f"The yet-to-be-seen configurations are: {initialConfiguration!r}",
			)
			raise AssertionError("\n".join(errorMessage))
		# test nothing extra has been sent yet
		if not inputToMume.empty():
			remainingOutput = inputToMume.get()
			errorMessage = (
				"The server thread spat out at least one unexpected initial configuration.",
				f"Remaining output: {remainingOutput!r}",
			)
			raise AssertionError("\n".join(errorMessage))
		# test regular text is passed through to the client
		try:
			outputFromMume.put(WELCOME_MESSAGE)
			data = outputToPlayer.get(timeout=1)
			self.assertEqual(data, WELCOME_MESSAGE)
		except Empty:
			raise AssertionError("The welcome message was not passed through to the client within 1 second.")
		# test further telnet negotiations are passed to the client with the exception of charset negotiations
		try:
			charsetNegotiation = IAC + DO + CHARSET + IAC + SB + TTYPE + TTYPE_SEND + IAC + SE
			charsetResponseFromMume = IAC + SB + CHARSET + CHARSET_ACCEPTED + b"US-ASCII" + IAC + SE
			outputFromMume.put(charsetNegotiation)
			data = outputToPlayer.get(timeout=1)
			self.assertEqual(data, charsetNegotiation[3:])  # slicing off the charset negotiation
			outputFromMume.put(charsetResponseFromMume)
			self.assertTrue(outputToPlayer.empty())
		except Empty:
			raise AssertionError("Further telnet negotiations were not passed to the client")
		# when mume outputs further text, test it is passed to the user
		try:
			usernamePrompt = b"By what name do you wish to be known? "
			outputFromMume.put(usernamePrompt)
			data = outputToPlayer.get(timeout=1)
			self.assertEqual(data, usernamePrompt)
		except Empty:
			raise AssertionError("Further text was not passed to the user")
		# when mume outputs an empty string, test server thread closes within a second
		outputFromMume.put(b"")
		gameThread.join(1)
		self.assertFalse(gameThread.is_alive())


class TestGameThreadThroughput(unittest.TestCase):
	def setUp(self):
		self.inputFromPlayer = Queue()
		self.outputToPlayer = Queue()
		self.inputToMume = Queue()
		self.outputFromMume = Queue()
		playerSocket = Mock(spec=socket.socket)
		playerSocket.recv.side_effect = lambda arg: self.inputFromPlayer.get()
		playerSocket.sendall.side_effect = lambda data: self.outputToPlayer.put(data)
		mumeSocket = Mock(spec=socket.socket)
		mumeSocket.recv.side_effect = lambda arg: self.outputFromMume.get()
		mumeSocket.sendall.side_effect = lambda data: self.inputToMume.put(data)
		mapperThread = Mock()
		mapperThread.interface = "text"
		proxy = ProtocolHandler(
			playerSocket,
			mumeSocket,
			outputFormat="normal",
			promptTerminator=CR_LF,
			isEmulatingOffline=False,
			mapperCommands=[],
			eventCaller=mapperThread.queue.put,
		)
		proxy.connect()
		mapperThread.proxy = proxy
		self.gameThread = Game(mumeSocket, mapperThread)
		self.gameThread.daemon = (
			True  # otherwise if this does not terminate, it prevents unittest from terminating
		)
		self.gameThread.start()

	def tearDown(self):
		self.outputFromMume.put(b"")
		del self.gameThread

	def runThroughput(self, threadInput, expectedOutput, expectedData, inputDescription):
		try:
			self.outputFromMume.put(threadInput)
			res = self.outputToPlayer.get(timeout=1)
			while not self.outputToPlayer.empty():
				res += self.outputToPlayer.get(timeout=1)
			self.assertEqual(
				res,
				expectedOutput,
				f"When entering {inputDescription}, the expected output did not match {expectedOutput!r}",
			)
		except Empty:
			raise AssertionError(
				f"{inputDescription} data was not received by the player socket within 1 second."
			)
		actualData = self.gameThread.mapper.queue.put.mock_calls
		i = 0
		while len(actualData) > i < len(expectedData):
			self.assertEqual(
				actualData[i],
				expectedData[i],
				f"When entering {inputDescription}, call #{i} to the mapper queue was not as expected",
			)
			i += 1
		if i < len(actualData):
			raise AssertionError("The mapper queue received the unexpected data: " + str(actualData[i]))
		if i < len(expectedData):
			raise AssertionError(
				"The mapper queue did not receive the expected data: " + str(expectedData[i])
			)

	def testProcessingPrompt(self):
		self.runThroughput(
			threadInput=b"<prompt>\x1b[34mMana:Hot Move:Tired>\x1b[0m</prompt>" + IAC + GA,
			expectedOutput=b"\x1b[34mMana:Hot Move:Tired>\x1b[0m" + CR_LF,
			expectedData=[call((MUD_DATA, ("prompt", b"\x1b[34mMana:Hot Move:Tired>\x1b[0m")))],
			inputDescription="prompt with mana burning and moves tired",
		)

	def testProcessingEnteringRoom(self):
		# fmt: off
		threadInput = (
			b"<movement dir=down/><room><name>Seagull Inn</name>" + CR_LF
			+ b"<gratuitous><description>"
			+ b"This is the most famous meeting-place in Harlond where people of all sorts" + CR_LF
			+ b"exchange news, rumours, deals and friendships. Sailors from the entire coast of" + CR_LF
			+ b"Middle-earth, as far as Dol Amroth and even Pelargir, are frequent guests here." + CR_LF
			+ b"For the sleepy, there is a reception and chambers upstairs. A note is stuck to" + CR_LF
			+ b"the wall." + CR_LF
			+ b"</description></gratuitous>"
			+ b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here." + CR_LF
			+ b"A white-painted bench is here." + CR_LF
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here." + CR_LF
			+ b"An elven lamplighter is resting here." + CR_LF
			+ b"</room>"
		)
		expectedOutput = (
			b"Seagull Inn" + CR_LF
			+ b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here." + CR_LF
			+ b"A white-painted bench is here." + CR_LF
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here." + CR_LF
			+ b"An elven lamplighter is resting here." + CR_LF
		)
		expectedDesc = (
			b"This is the most famous meeting-place in Harlond where people of all sorts" + LF
			+ b"exchange news, rumours, deals and friendships. Sailors from the entire coast of" + LF
			+ b"Middle-earth, as far as Dol Amroth and even Pelargir, are frequent guests here." + LF
			+ b"For the sleepy, there is a reception and chambers upstairs. A note is stuck to" + LF
			+ b"the wall." + LF
		)
		expectedDynamicDesc = (
			b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here." + LF
			+ b"A white-painted bench is here." + LF
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here." + LF
			+ b"An elven lamplighter is resting here." + LF
		)
		# fmt: on
		expectedData = [
			call((MUD_DATA, ("movement", b"down"))),
			call((MUD_DATA, ("name", b"Seagull Inn"))),
			call((MUD_DATA, ("description", expectedDesc))),
			call((MUD_DATA, ("dynamic", expectedDynamicDesc))),
		]
		inputDescription = "moving into a room"
		self.runThroughput(threadInput, expectedOutput, expectedData, inputDescription)
