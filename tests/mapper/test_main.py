# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import socket
import unittest
from unittest.mock import Mock

from mapper.main import SB_ACCEPTED, SB_SEND, Server
from mapper.mpi import MPI_INIT
from telnetlib import CHARSET, IAC, DO, NAWS, SB, SE, TTYPE, WILL
from queue import Empty, Queue


# The initial output of MUME. Used by the server thread to detect connection success.
INITIAL_OUTPUT = IAC + DO + TTYPE + IAC + DO + NAWS
WELCOME_MESSAGE = b"\r\n                              ***  MUME VIII  ***\r\n\r\n"


class TestServerThread(unittest.TestCase):
	def testServerThread(self):
		initialConfiguration = [  # What the server thread sends MUME on connection success.
			# Identify for Mume Remote Editing.
			MPI_INIT + b"I\n",
			# Turn on XML mode.
			MPI_INIT + b"X2\n3G\n",
			# Tell the Mume server to put IAC-GA at end of prompts.
			MPI_INIT + b"P2\nG\n",
			# Tell the server that we will negotiate the character set.
			IAC + WILL + CHARSET,
		]
		mumeSocket = Mock(spec=socket.socket)
		outputFromMume = Queue()
		inputToMume = Queue()
		mumeSocket.recv.side_effect = lambda arg: outputFromMume.get()
		mumeSocket.sendall.side_effect = lambda data: inputToMume.put(data)
		clientSocket = Mock(spec=socket.socket)
		outputToUser = Queue()
		clientSocket.sendall.side_effect = lambda data: outputToUser.put(data)
		serverThread = Server(
			client=clientSocket,
			server=mumeSocket,
			mapper=Mock(),
			outputFormat=None,
			interface="text",
			promptTerminator=None
		)
		serverThread.daemon = True  # otherwise if this does not terminate, it prevents unittest from terminating
		serverThread.start()
		# test when the server sends its initial negociations, the server thread outputs its initial configuration
		self.assertEqual(initialConfiguration, serverThread.initialConfiguration)
		self.assertEqual(INITIAL_OUTPUT, serverThread.initialOutput)
		outputFromMume.put(INITIAL_OUTPUT)
		try:
			while initialConfiguration:
				data = inputToMume.get(timeout=1)
				self.assertIn(data, initialConfiguration, "Unknown initial configuration: {!r}".format(data))
				initialConfiguration.remove(data)
		except Empty:
			errorMessage = (
				"The server thread did not output the expected number of configuration parameters.",
				"The yet-to-be-seen configurations are: {!r}".format(initialConfiguration)
			)
			raise AssertionError("\n".join(errorMessage))
		# test nothing extra has been sent yet
		if not inputToMume.empty():
			remainingOutput = inputToMume.get()
			errorMessage = (
				"The server thread spat out at least one unexpected initial configuration.",
				"Remaining output: {!r}".format(remainingOutput)
			)
			raise AssertionError("\n".join(errorMessage))
		# test initial telnet negociations were passed to the client
		try:
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, INITIAL_OUTPUT)
		except Empty:
			raise AssertionError("initial telnet negociations were not passed to the client")
		# test regular text is passed through to the client
		try:
			outputFromMume.put(WELCOME_MESSAGE)
			data = outputToUser.get(timeout=1)
			self.assertEqual(WELCOME_MESSAGE, data)
		except Empty:
			raise AssertionError("The welcome message was not passed through to the client within 1 second.")
		# test further telnet negociations are passed to the client with the exception of charset negociations
		try:
			charsetNegociation = IAC + DO + CHARSET + IAC + SB + TTYPE + SB_SEND + IAC + SE
			charsetSubnegociation = IAC + SB + CHARSET + SB_ACCEPTED + b"US-ASCII" + IAC + SE
			outputFromMume.put(charsetNegociation)
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, charsetNegociation[3:])  # slicing off the charset negociation
			outputFromMume.put(charsetSubnegociation)
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, b"")
		except Empty:
			raise AssertionError("Further telnet negociations were not passed to the client")
		# when mume outputs further text, test it is passed to the user
		try:
			usernamePrompt = b"By what name do you wish to be known? "
			outputFromMume.put(usernamePrompt)
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, usernamePrompt)
		except Empty:
			raise AssertionError("Further text was not passed to the user")
		# when mume outputs an empty string, test server thread closes within a second
		outputFromMume.put(b"")
		serverThread.join(1)
		self.assertFalse(serverThread.is_alive())
