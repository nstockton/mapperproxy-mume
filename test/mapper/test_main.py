import unittest
from unittest.mock import call, Mock
from telnetlib import ECHO, IAC, NAWS, SB, TTYPE, WILL
from time import sleep
from queue import Empty, Queue

from mapper.main import *


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
		inputFromUser = Queue()
		outputToUser = Queue()
		clientSocket.recv.side_effect = lambda arg: inputFromUser.get()
		clientSocket.sendall.side_effect = lambda data: outputToUser.put(data)

		serverThread = Server(
			client=clientSocket,
			server=serverSocket,
			mapper=Mock(),
			outputFormat=None,
			interface="text",
			promptTerminator=None
		)
		serverThread.start()

		# test that the initial configuration parameters are outputted when the server first replies
		outputFromMume.put(IAC+DO+TTYPE+IAC+DO+NAWS,)
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
		
		#  out comes start screen
		#assert it comes out other end
		#in goes username
		#assert comes out
		#in goes some more negociation
		#assert it comes out
		# put in password
		#assert it comes out
		 #input nothing to close it
		 # assert thread is dead
		
		serverThreadInput = [  # list binary input in chronological order
			b"\r\n                              ***  MUME VIII  ***\r\n\r\n                              In progress at FIRE\r\n                     (Free Internet Roleplay Experiences)\r\n                      Hosted at HEIG-VD (www.heig-vd.ch)\r\n\r\n             Adapted from J.R.R. Tolkien's Middle-earth world and\r\n                   maintained by CryHavoc, Manwe, and Nada.\r\n\r\n              Original code DikuMUD I (help credits), created by:\r\n       S. Hammer, T. Madsen, K. Nyboe, M. Seifert, and H.H. Staerfeldt.\r\n\r\nIf you have never played MUME before, type NEW to create a new character,\r\nor ? for help. Otherwise, type your account or character name.\r\n\r\n\r\n",
			b"By what name do you wish to be known? ",
			IAC+DO+b"*"+IAC+SB+TTYPE+ECHO+IAC+SE,
			b"IACSB*\x02US-ASCIIIACSE",
			b"",
		]
		serverThreadInput.reverse()  # reverse because the pop function takes from the end of the list

		# close server thread
		outputFromMume.put(b"")
		serverThread.join(1)
		self.assertFalse(serverThread.is_alive())
