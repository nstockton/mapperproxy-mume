import unittest
from unittest.mock import call, Mock
from telnetlib import ECHO, IAC, NAWS, SB, TTYPE, WILL
from queue import Queue

from mapper.main import *


class TestServerThread(unittest.TestCase):
	def testServerThreadInitialises(self):

		
		
		serverSocket = Mock(spec=socket.socket)
		serverSocketOutput = Queue()
		serverSocketInput = Queue()
		serverSocket.recv.side_effect = lambda arg: serverSocketOutput.get()
		serverSocket.sendall.side_effect = lambda data: serverSocketInput.put(data)
		clientSocket = Mock(spec=socket.socket)
		clientSocketOutput = Queue()
		clientSocketInput = Queue()
		clientSocket.recv.side_effect = lambda arg: clientSocketOutput.get()
		clientSocket.sendall.side_effect = lambda data: clientSocketOutput.put(data)

		serverThread = Server(
			client=clientSocket,
			server=serverSocket,
			mapper=Mock(),
			outputFormat=None,
			interface="text",
			promptTerminator=None
		)
		serverThread.start()

		serverSocketOutput.put(IAC+DO+TTYPE+IAC+DO+NAWS,)
		self.assertEqual(serverSocketInput.get(), b"~$#EI\n")
		#self.assertEqual(initialConfiguration, serverSocket.sendall.mock_calls)
		
		initialConfiguration = [
			call(),
			call(b"~$#EX2\n3G\n"),
			call(b"~$#EP2\nG\n"),
			call(IAC+WILL+b"*"),
		]

		# put initial telnet bits out of server
		# test that negociation stuff came back out server input
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
		
			#call(IAC+SB+b"*"+ECHO+b";US-ASCII"+IAC+SE),
		#]
		serverThreadInput = [  # list binary input in chronological order
			b"\r\n                              ***  MUME VIII  ***\r\n\r\n                              In progress at FIRE\r\n                     (Free Internet Roleplay Experiences)\r\n                      Hosted at HEIG-VD (www.heig-vd.ch)\r\n\r\n             Adapted from J.R.R. Tolkien's Middle-earth world and\r\n                   maintained by CryHavoc, Manwe, and Nada.\r\n\r\n              Original code DikuMUD I (help credits), created by:\r\n       S. Hammer, T. Madsen, K. Nyboe, M. Seifert, and H.H. Staerfeldt.\r\n\r\nIf you have never played MUME before, type NEW to create a new character,\r\nor ? for help. Otherwise, type your account or character name.\r\n\r\n\r\n",
			b"By what name do you wish to be known? ",
			IAC+DO+b"*"+IAC+SB+TTYPE+ECHO+IAC+SE,
			b"IACSB*\x02US-ASCIIIACSE",
			b"",
		]
		serverThreadInput.reverse()  # reverse because the pop function takes from the end of the list
		serverSocketOutput.put(b"")
		serverThread.join(1)
		self.assertTrue(serverThread.is_alive())
