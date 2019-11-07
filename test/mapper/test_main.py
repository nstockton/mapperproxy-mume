import unittest
from unittest.mock import call, Mock
from telnetlib import ECHO, IAC, NAWS, SB, TTYPE, WILL
from queue import Empty, Queue

from mapper.main import *

initialOutput = IAC+DO+TTYPE+IAC+DO+NAWS
welcomeMessage = b"\r\n                              ***  MUME VIII  ***\r\n\r\n"


class TestServerThread(unittest.TestCase):
	def testServerThreadInitialises(self):
		initialConfiguration = [
			b"~$#EI\n",
			b"~$#EX2\n3G\n",
			b"~$#EP2\nG\n",
			IAC+WILL+b"*",
		]

		serverSocket = Mock(spec=socket.socket)
		outputFromMume = Queue()
		inputToMume = Queue()
		serverSocket.recv.side_effect = lambda arg: outputFromMume.get()
		serverSocket.sendall.side_effect = lambda data: inputToMume.put(data)
		clientSocket = Mock(spec=socket.socket)
		outputToUser = Queue()
		clientSocket.sendall.side_effect = lambda data: outputToUser.put(data)

		serverThread = Server(
			client=clientSocket,
			server=serverSocket,
			mapper=Mock(),
			outputFormat=None,
			interface="text",
			promptTerminator=None
		)
		serverThread.daemon = True
		serverThread.start()

		# test that the initial configuration parameters are outputted when the server first replies
		outputFromMume.put(initialOutput)
		try:
			while initialConfiguration:
				data = inputToMume.get(timeout=1)
				self.assertIn(data, initialConfiguration, "Unknown initial configuration: "+str(data))
				initialConfiguration.remove(data)
		except Empty:
			raise AssertionError("The server thread did not output the expected number of configuration parameters.\
				The yet-to-be-seen configurations are: "+"; ".join(initialConfiguration))
		if not inputToMume.empty():
			remainingOutput = inputToMume.get()
			raise AssertionError("The server thread spat out at least one unexpected initial configuration: "+str(remainingOutput))

		# test initial telnet negociation was passed to the client
		try:
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, initialOutput)
		except Empty:
			raise AssertionError("initial telnet negociations were not passed to the client")
			
		# test regular text is passed through to the client
		try:
			outputFromMume.put(welcomeMessage)
			clientWelcomeMessage = outputToUser.get(timeout=1)
			self.assertEqual(welcomeMessage, clientWelcomeMessage)
		except Empty:
			raise AssertionError("The welcome message was not passed through to the client within 1 second.")

		#in goes some more negociation
		#assert it comes out
		# put in password
		#assert it comes out
		 #input nothing to close it
		 # assert thread is dead
		
		serverThreadInput = [  # list binary input in chronological order
			IAC+DO+b"*"+IAC+SB+TTYPE+ECHO+IAC+SE,
			b"IACSB*\x02US-ASCIIIACSE",
			b"",
		]
		serverThreadInput.reverse()  # reverse because the pop function takes from the end of the list

		# close server thread
		outputFromMume.put(b"")
		serverThread.join(1)
		self.assertFalse(serverThread.is_alive())
