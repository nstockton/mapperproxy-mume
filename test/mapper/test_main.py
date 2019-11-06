import unittest
from unittest.mock import call, Mock
from telnetlib import ECHO, IAC, NAWS, SB, TTYPE, WILL

from mapper.main import *


class TestServerThread(unittest.TestCase):
	def testServerThreadInitialises(self):
		expectedOutput = [
			call(b"~$#EI\n"),
			call(b"~$#EX2\n3G\n"),
			call(b"~$#EP2\nG\n"),
			call(IAC+WILL+b"*"),
			call(IAC+SB+b"*"+ECHO+b";US-ASCII"+IAC+SE),
		]
		serverThreadInput = [  # list binary input in chronological order
			IAC+DO+TTYPE+IAC+DO+NAWS,
			b"\r\n                              ***  MUME VIII  ***\r\n\r\n                              In progress at FIRE\r\n                     (Free Internet Roleplay Experiences)\r\n                      Hosted at HEIG-VD (www.heig-vd.ch)\r\n\r\n             Adapted from J.R.R. Tolkien's Middle-earth world and\r\n                   maintained by CryHavoc, Manwe, and Nada.\r\n\r\n              Original code DikuMUD I (help credits), created by:\r\n       S. Hammer, T. Madsen, K. Nyboe, M. Seifert, and H.H. Staerfeldt.\r\n\r\nIf you have never played MUME before, type NEW to create a new character,\r\nor ? for help. Otherwise, type your account or character name.\r\n\r\n\r\n",
			b"By what name do you wish to be known? ",
			IAC+DO+b"*"+IAC+SB+TTYPE+ECHO+IAC+SE,
			b"IACSB*\x02US-ASCIIIACSE",
			b"",
		]
		serverThreadInput.reverse()  # reverse because the pop function takes from the end of the list

		serverSocket = Mock(spec=socket.socket)
		serverSocket.recv.side_effect = lambda arg: serverThreadInput.pop()

		serverThread = Server(
			client=Mock(),
			server=serverSocket,
			mapper=Mock(),
			outputFormat=None,
			interface="text",
			promptTerminator=None
		)

		serverThread.run()

		for i in range(len(serverSocket.sendall.mock_calls)):
			self.assertEqual( expectedOutput[i], serverSocket.sendall.mock_calls[i],
				"verifying args of serverSocket.sendall in call number "+str(i))
