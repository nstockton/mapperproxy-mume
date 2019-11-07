# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import socket
import unittest
from unittest.mock import Mock

from mapper.main import Server
from telnetlib import CHARSET, ECHO, IAC, DO, NAWS, RCP, SB, SE, TTYPE, WILL
from queue import Empty, Queue


INITIAL_OUTPUT = IAC + DO + TTYPE + IAC + DO + NAWS
WELCOME_MESSAGE = b"\r\n                              ***  MUME VIII  ***\r\n\r\n"


class TestServerThread(unittest.TestCase):
	def testServerThread(self):
		initialConfiguration = [
			b"~$#EI\n",
			b"~$#EX2\n3G\n",
			b"~$#EP2\nG\n",
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
		outputFromMume.put(INITIAL_OUTPUT)
		try:
			while initialConfiguration:
				data = inputToMume.get(timeout=1)
				self.assertIn(data, initialConfiguration, "Unknown initial configuration: " + str(data))
				initialConfiguration.remove(data)
		except Empty:
			raise AssertionError(
				"The server thread did not output the expected number of configuration parameters."
				+ "The yet-to-be-seen configurations are: "
				+ "; ".join(initialConfiguration)
			)
		# test nothing extr has been sent yet
		if not inputToMume.empty():
			remainingOutput = inputToMume.get()
			raise AssertionError(
				"The server thread spat out at least one unexpected initial configuration: "
				+ str(remainingOutput)
			)
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
			charsetNegociation = IAC + DO + CHARSET + IAC + SB + TTYPE + ECHO + IAC + SE
			charsetSubnegociation = IAC + SB + CHARSET + RCP + b"US-ASCII" + IAC + SE
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
