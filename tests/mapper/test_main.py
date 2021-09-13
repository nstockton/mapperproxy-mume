# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import socket
from queue import Empty, Queue
from typing import Callable, Sequence, Tuple
from unittest import TestCase
from unittest.mock import Mock, _Call, _CallList, call

# Third-party Modules:
from mudproto.mpi import MPI_INIT
from mudproto.telnet_constants import (
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
)

# Mapper Modules:
from mapper.main import Game
from mapper.proxy import ProxyHandler


# The initial output of MUME. Used by the server thread to detect connection success.
INITIAL_OUTPUT: Tuple[bytes, ...] = (
	IAC + DO + TTYPE,
	IAC + DO + NAWS,
)
WELCOME_MESSAGE: bytes = CR_LF + b"                              ***  MUME VIII  ***" + CR_LF + CR_LF


class TestGameThread(TestCase):
	def setUp(self) -> None:
		logging.disable(logging.CRITICAL)

	def tearDown(self) -> None:
		logging.disable(logging.NOTSET)

	def testGameThread(self) -> None:
		# fmt: off
		initialConfiguration: bytes = (  # What the server thread sends MUME on connection success.
			# Tell the Mume server to put IAC-GA at end of prompts.
			MPI_INIT + b"P2" + LF + b"G" + LF
			# Identify for Mume Remote Editing.
			+ MPI_INIT + b"I" + LF
			# Turn on XML mode.
			+ MPI_INIT + b"X2" + LF + b"3G" + LF
		)
		# fmt: on
		outputToPlayer: Queue[bytes] = Queue()
		outputFromMume: Queue[bytes] = Queue()
		inputToMume: Queue[bytes] = Queue()
		mumeSocket: Mock = Mock(spec=socket.socket)
		mumeSocket.recv.side_effect = lambda arg: outputFromMume.get()
		mumeSocket.sendall.side_effect = lambda data: inputToMume.put(data)
		clientSocket: Mock = Mock(spec=socket.socket)
		clientSocket.sendall.side_effect = lambda data: outputToPlayer.put(data)
		mapperThread: Mock = Mock()
		mapperThread.interface = "text"
		proxy: ProxyHandler = ProxyHandler(
			clientSocket.sendall,
			mumeSocket.sendall,
			outputFormat="normal",
			promptTerminator=IAC + GA,
			isEmulatingOffline=False,
			mapperCommands=[],
			eventCaller=mapperThread.queue.put,
		)
		proxy.connect()
		mapperThread.proxy = proxy
		gameThread: Game = Game(mumeSocket, mapperThread)
		gameThread.daemon = True  # Allow unittest to quit if game thread does not close properly.
		gameThread.start()
		# test initial telnet negotiations were passed to the client
		data: bytes
		errorMessage: str
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
				"The server thread did not output the expected number of configuration parameters."
				+ f"The yet-to-be-seen configurations are: {initialConfiguration!r}"
			)
			raise AssertionError(errorMessage)
		# test nothing extra has been sent yet
		if not inputToMume.empty():
			remainingOutput: bytes = inputToMume.get()
			errorMessage = (
				"The server thread spat out at least one unexpected initial configuration."
				+ f"Remaining output: {remainingOutput!r}"
			)
			raise AssertionError(errorMessage)
		# test regular text is passed through to the client
		try:
			outputFromMume.put(WELCOME_MESSAGE)
			data = outputToPlayer.get(timeout=1)
			self.assertEqual(data, WELCOME_MESSAGE)
		except Empty:
			raise AssertionError("The welcome message was not passed through to the client within 1 second.")
		# test further telnet negotiations are passed to the client with the exception of charset negotiations
		try:
			charsetNegotiation: bytes = IAC + DO + CHARSET + IAC + SB + TTYPE + TTYPE_SEND + IAC + SE
			charsetResponseFromMume: bytes = IAC + SB + CHARSET + CHARSET_ACCEPTED + b"US-ASCII" + IAC + SE
			outputFromMume.put(charsetNegotiation)
			data = outputToPlayer.get(timeout=1)
			self.assertEqual(data, charsetNegotiation[3:])  # slicing off the charset negotiation
			outputFromMume.put(charsetResponseFromMume)
			self.assertTrue(outputToPlayer.empty())
		except Empty:
			raise AssertionError("Further telnet negotiations were not passed to the client")
		# when mume outputs further text, test it is passed to the user
		try:
			usernamePrompt: bytes = b"By what name do you wish to be known? "
			outputFromMume.put(usernamePrompt)
			data = outputToPlayer.get(timeout=1)
			self.assertEqual(data, usernamePrompt)
		except Empty:
			raise AssertionError("Further text was not passed to the user")
		# when mume outputs an empty string, test server thread closes within a second
		outputFromMume.put(b"")
		gameThread.join(1)
		self.assertFalse(gameThread.is_alive())


class TestGameThreadThroughput(TestCase):
	def setUp(self) -> None:
		logging.disable(logging.CRITICAL)
		self.inputFromPlayer: Queue[bytes] = Queue()
		self.outputToPlayer: Queue[bytes] = Queue()
		self.inputToMume: Queue[bytes] = Queue()
		self.outputFromMume: Queue[bytes] = Queue()
		playerSocket: Mock = Mock(spec=socket.socket)
		playerSocket.recv.side_effect = lambda arg: self.inputFromPlayer.get()
		playerSocket.sendall.side_effect = lambda data: self.outputToPlayer.put(data)
		mumeSocket: Mock = Mock(spec=socket.socket)
		mumeSocket.recv.side_effect = lambda arg: self.outputFromMume.get()
		mumeSocket.sendall.side_effect = lambda data: self.inputToMume.put(data)
		self.mapperThread: Mock = Mock()
		self.mapperThread.interface = "text"
		proxy: ProxyHandler = ProxyHandler(
			playerSocket.sendall,
			mumeSocket.sendall,
			outputFormat="normal",
			promptTerminator=CR_LF,
			isEmulatingOffline=False,
			mapperCommands=[],
			eventCaller=self.mapperThread.queue.put,
		)
		proxy.connect()
		self.mapperThread.proxy = proxy
		self.gameThread: Game = Game(mumeSocket, self.mapperThread)
		self.gameThread.daemon = True  # Allow unittest to quit if game thread does not close properly.
		self.gameThread.start()

	def tearDown(self) -> None:
		logging.disable(logging.NOTSET)
		self.outputFromMume.put(b"")
		del self.gameThread

	def runThroughput(
		self,
		threadInput: bytes,
		expectedOutput: bytes,
		expectedData: Sequence[Callable[[int, Tuple[str, bytes]], _Call]],
		inputDescription: str,
	) -> None:
		res: bytes
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
		actualData: _CallList = self.mapperThread.queue.put.mock_calls
		i: int = 0
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

	def testProcessingPrompt(self) -> None:
		self.runThroughput(
			threadInput=b"<prompt>\x1b[34mMana:Hot Move:Tired>\x1b[0m</prompt>" + IAC + GA,
			expectedOutput=b"\x1b[34mMana:Hot Move:Tired>\x1b[0m" + CR_LF,
			expectedData=[call(("prompt", b"\x1b[34mMana:Hot Move:Tired>\x1b[0m"))],
			inputDescription="prompt with mana burning and moves tired",
		)

	def testProcessingEnteringRoom(self) -> None:
		# fmt: off
		threadInput: bytes = (
			b"<movement dir=down/><room t=&#35;><name>Seagull Inn</name>" + CR_LF
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
		expectedOutput: bytes = (
			b"Seagull Inn" + CR_LF
			+ b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here." + CR_LF
			+ b"A white-painted bench is here." + CR_LF
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here." + CR_LF
			+ b"An elven lamplighter is resting here." + CR_LF
		)
		expectedDesc: bytes = (
			b"This is the most famous meeting-place in Harlond where people of all sorts" + LF
			+ b"exchange news, rumours, deals and friendships. Sailors from the entire coast of" + LF
			+ b"Middle-earth, as far as Dol Amroth and even Pelargir, are frequent guests here." + LF
			+ b"For the sleepy, there is a reception and chambers upstairs. A note is stuck to" + LF
			+ b"the wall." + LF
		)
		expectedDynamicDesc: bytes = (
			b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here." + LF
			+ b"A white-painted bench is here." + LF
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here." + LF
			+ b"An elven lamplighter is resting here." + LF
		)
		# fmt: on
		expectedData: Tuple[Callable[[int, Tuple[str, bytes]], _Call], ...] = (
			call(("movement", b"down")),
			call(("room", b"t=#")),
			call(("name", b"Seagull Inn")),
			call(("description", expectedDesc)),
			call(("dynamic", expectedDynamicDesc)),
		)
		inputDescription: str = "moving into a room"
		self.runThroughput(threadInput, expectedOutput, expectedData, inputDescription)
