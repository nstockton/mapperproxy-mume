# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import os
import socket
try:
	import certifi
	import ssl
except ImportError:
	ssl = None
from telnetlib import IAC, GA, DONT, DO, WONT, WILL, theNULL, SB, SE, TTYPE, NAWS
import threading

from .mapper import USER_DATA, MUD_DATA, Mapper
from .mpi import MPI
from .utils import getDirectoryPath, touch, unescapeXML


LISTENING_STATUS_FILE = os.path.join(getDirectoryPath("."), "mapper_ready.ignore")
CHARSET = chr(42).encode("us-ascii")
SB_REQUEST, SB_ACCEPTED, SB_REJECTED, SB_TTABLE_IS, SB_TTABLE_REJECTED, SB_TTABLE_ACK, SB_TTABLE_NAK = (
	chr(i).encode("us-ascii") for i in range(1, 8)
)


class Proxy(threading.Thread):
	def __init__(self, client, server, mapper, isEmulatingOffline):
		threading.Thread.__init__(self)
		self.name = "Proxy"
		self._client = client
		self._server = server
		self._mapper = mapper
		self.isEmulatingOffline = isEmulatingOffline
		self.finished = threading.Event()

	def close(self):
		self.finished.set()

	def run(self):
		userCommands = [
			func[len("user_command_"):].encode("us-ascii", "ignore") for func in dir(self._mapper)
			if func.startswith("user_command_")
		]
		while not self.finished.isSet():
			try:
				data = self._client.recv(4096)
			except socket.timeout:
				continue
			except EnvironmentError:
				self.close()
				continue
			if not data:
				self.close()
			elif self.isEmulatingOffline or data.strip() and data.strip().split()[0] in userCommands:
				self._mapper.queue.put((USER_DATA, data))
			else:
				try:
					self._server.sendall(data)
				except EnvironmentError:
					self.close()
					continue


class Server(threading.Thread):
	def __init__(self, client, server, mapper, outputFormat, interface, promptTerminator):
		threading.Thread.__init__(self)
		self.name = "Server"
		self._client = client
		self._server = server
		self._mapper = mapper
		self._outputFormat = outputFormat
		self._interface = interface
		self._promptTerminator = promptTerminator
		self.finished = threading.Event()
		self.ignoreBytes = frozenset([ord(theNULL), 0x11])
		self.negotiationBytes = frozenset(ord(byte) for byte in [DONT, DO, WONT, WILL])
		self.inNegotiation = False
		self.inSubNegotiation = False
		self.subNegotiationBuffer = bytearray()
		self.inCharset = False
		self.inCharsetResponse = False
		self.charsetResponseCode = None
		self.charsetResponseBuffer = bytearray()
		self.charsetSep = b";"
		charsets = {
			"ascii": b"US-ASCII",
			"latin-1": b"ISO-8859-1",
			"utf-8": b"UTF-8"
		}
		self.defaultCharset = charsets["ascii"]
		self.inMPI = False
		self.mpiInitCounter = 0
		self.mpiCommand = None
		self.mpiLen = None
		self.mpiBuffer = bytearray()
		self.mpiThreads = []
		self.inXML = False
		self.inGratuitous = False
		self.xmlModes = {  # If a tag matches a key, self.xmlMode will be changed to its value.
			b"room": b"room",
			b"exits": b"exits",
			b"prompt": b"prompt",
			b"name": b"name",
			b"description": b"description",
			b"terrain": b"terrain",
			b"/exits": None,
			b"/prompt": None,
			b"/room": None,
			b"/name": b"room",
			b"/description": b"room",
			b"/terrain": b"room"
		}
		self.xmlMode = None
		self.xmlTagBuffer = bytearray()  # Used for start and end tag names.
		self.xmlTextBuffer = bytearray()  # Used for the text between start and end tags.
		self.tintinTagReplacements = {  # Used for reformatting tags for Tintin.
			b"prompt": b"PROMPT:",
			b"/prompt": b":PROMPT",
			b"name": b"NAME:",
			b"/name": b":NAME",
			b"tell": b"TELL:",
			b"/tell": b":TELL",
			b"narrate": b"NARRATE:",
			b"/narrate": b":NARRATE",
			b"pray": b"PRAY:",
			b"/pray": b":PRAY",
			b"say": b"SAY:",
			b"/say": b":SAY",
			b"emote": b"EMOTE:",
			b"/emote": b":EMOTE"
		}
		self.lineBuffer = bytearray()  # Used for sending non-XML lines to the mapper thread.
		self.clientBuffer = bytearray()  # Used for the resulting data that will be sent on to the user's client.

	def close(self):
		self.finished.set()

	def processNegotiationByte(self, byte):
		if byte in self.negotiationBytes:
			# This is the second byte in a 3-byte telnet negotiation sequence.
			if self.inSubNegotiation:
				self.subNegotiationBuffer.extend((ord(IAC), byte))
			else:
				self.clientBuffer.extend((ord(IAC), byte))
		else:
			# byte is the final byte in a 2-3 byte telnet negotiation sequence.
			self.inNegotiation = False
			if byte == ord(SB):
				# Sub-negotiation begin
				self.inSubNegotiation = True
			elif byte == ord(SE):
				# Sub-negotiation end.
				if self.inCharsetResponse:
					self.charsetResponseCode = None
					self.charsetResponseBuffer.clear()
					self.inCharsetResponse = False
				else:
					self.clientBuffer.extend(IAC + SB + self.subNegotiationBuffer + IAC + SE)
				self.subNegotiationBuffer.clear()
				self.inSubNegotiation = False
			elif self.inSubNegotiation:
				if self.subNegotiationBuffer[-1] in self.negotiationBytes:
					self.subNegotiationBuffer.append(byte)
				else:
					self.subNegotiationBuffer.extend((ord(IAC), byte))
			elif byte == ord(IAC):
				# This is an escaped IAC byte to be added to the buffer.
				if self.inMPI:
					self.mpiBuffer.append(byte)
				else:
					self.clientBuffer.extend(IAC + IAC)
					if self.xmlMode is None:
						self.lineBuffer.append(byte)
			elif byte == ord(CHARSET) and self.inCharset and self.clientBuffer.endswith(IAC + DO):
				# Negotiate the character set.
				self._server.sendall(IAC + SB + CHARSET + SB_REQUEST + self.charsetSep + self.defaultCharset + IAC + SE)
				# IAC + DO was appended to the client buffer earlier.
				# It must be removed as character set negotiation data should not be sent to the mud client.
				del self.clientBuffer[-2:]
			elif byte == ord(GA):
				# Replace the IAC-GA sequence (used by the game to terminate a prompt)
				# with the user specified prompt terminator.
				self.clientBuffer.extend(self._promptTerminator)
				self._mapper.queue.put((MUD_DATA, ("iac_ga", b"")))
				if self.xmlMode is None:
					self.lineBuffer.extend(b"\r\n")
			else:
				if self.clientBuffer[-1] in self.negotiationBytes:
					self.clientBuffer.append(byte)
				else:
					self.clientBuffer.extend((ord(IAC), byte))

	def processSubNegotiation(self, byte):
		if self.inCharset and byte == ord(CHARSET):
			self.inCharsetResponse = True
		elif self.inCharsetResponse and byte not in self.ignoreBytes:
			if self.charsetResponseCode is None:
				self.charsetResponseCode = byte
			else:
				self.charsetResponseBuffer.append(byte)
		else:
			self.subNegotiationBuffer.append(byte)

	def processMPIByte(self, byte):
		if byte == ord("\n") and self.mpiCommand is None and self.mpiLen is None:
			# The first line of MPI data was recieved.
			# The first byte is the MPI command, E for edit, V for view.
			# The remaining byte sequence is the length of the MPI data to be received.
			if self.mpiBuffer[0:1] in (b"E", b"V") and self.mpiBuffer[1:].isdigit():
				self.mpiCommand = bytes(self.mpiBuffer[0:1])
				self.mpiLen = int(self.mpiBuffer[1:])
			else:
				# Invalid MPI command or length.
				self.inMPI = False
			self.mpiBuffer.clear()
		else:
			self.mpiBuffer.append(byte)
			if self.mpiLen is not None and len(self.mpiBuffer) == self.mpiLen:
				# The last byte in the MPI data has been reached.
				self.mpiThreads.append(
					MPI(
						client=self._client,
						server=self._server,
						isTinTin=self._outputFormat == "tintin",
						command=self.mpiCommand,
						data=bytes(self.mpiBuffer)
					)
				)
				self.mpiBuffer.clear()
				self.mpiCommand = None
				self.mpiLen = None
				self.mpiThreads[-1].start()
				self.inMPI = False

	def processXMLByte(self, byte):
		xmlModes = self.xmlModes
		if byte == ord(">"):
			# End of XML tag reached.
			tag = bytes(self.xmlTagBuffer)
			text = bytes(self.xmlTextBuffer)
			if self.xmlMode is None and tag.startswith(b"movement"):
				self._mapper.queue.put((MUD_DATA, ("movement", tag[13:-1])))
			elif tag in xmlModes:
				self.xmlMode = xmlModes[tag]
				if tag == b"/room":
					self._mapper.queue.put((MUD_DATA, ("dynamic", text)))
				elif tag.startswith(b"/"):
					self._mapper.queue.put((MUD_DATA, (tag[1:].decode("ascii"), text)))
			elif tag == b"gratuitous":
				self.inGratuitous = True
			elif tag == b"/gratuitous":
				self.inGratuitous = False
			if self._outputFormat == "tintin":
				self.clientBuffer.extend(self.tintinTagReplacements.get(tag, b""))
			self.xmlTagBuffer.clear()
			self.xmlTextBuffer.clear()
			self.inXML = False
		else:
			self.xmlTagBuffer.append(byte)

	def processTextByte(self, byte):
		if self.xmlMode:
			self.xmlTextBuffer.append(byte)
		if byte == ord("\n") and self.lineBuffer:
			for line in bytes(self.lineBuffer).splitlines():
				if line.strip():
					self._mapper.queue.put((MUD_DATA, ("line", line)))
			self.lineBuffer.clear()
		else:
			self.lineBuffer.append(byte)

	def processData(self, data):
		for byte in bytearray(data):
			if self.inNegotiation:
				self.processNegotiationByte(byte)
			elif byte == ord(IAC):
				self.inNegotiation = True
			elif self.inSubNegotiation:
				self.processSubNegotiation(byte)
			elif byte in self.ignoreBytes:
				self.clientBuffer.append(byte)
			elif self.inMPI:
				self.processMPIByte(byte)
			elif (
				byte == ord("~") and self.mpiInitCounter == 0 and self.clientBuffer.endswith(b"\n")
				or self.mpiInitCounter == 1 and byte == ord("$")
				or self.mpiInitCounter == 2 and byte == ord("#")
			):
				# Byte is one of the first 3 bytes in the 4-byte MPI sequence (~$#E),
				# and the sequence was preceded by a new-line character (\n).
				self.mpiInitCounter += 1
			elif self.mpiInitCounter == 3 and byte == ord("E"):
				# Byte is the final byte in the 4-byte MPI sequence (~$#E).
				self.inMPI = True
				self.mpiInitCounter = 0
			elif self.inXML or byte == ord("<"):
				self.mpiInitCounter = 0
				if byte == ord("<"):
					# Start of new XML tag.
					self.inXML = True
				else:
					self.processXMLByte(byte)
				if self._outputFormat == "raw":
					self.clientBuffer.append(byte)
			else:
				# Byte is not part of a Telnet negotiation, MPI negotiation, or XML tag name.
				self.mpiInitCounter = 0
				self.processTextByte(byte)
				if self._outputFormat == "raw" or not self.inGratuitous:
					self.clientBuffer.append(byte)
		result = bytes(self.clientBuffer)
		self.clientBuffer.clear()
		return result

	def run(self):
		initialOutput = b"".join((IAC, DO, TTYPE, IAC, DO, NAWS))
		encounteredInitialOutput = False
		while not self.finished.isSet():
			try:
				data = self._server.recv(4096)
			except EnvironmentError:
				self.close()
				continue
			if not data:
				self.close()
				continue
			elif not encounteredInitialOutput and data.startswith(initialOutput):
				# The connection to Mume has been established, and the game has just responded with the login screen.
				# Identify for Mume Remote Editing.
				self._server.sendall(b"~$#EI\n")
				# Turn on XML mode.
				self._server.sendall(b"~$#EX2\n3G\n")
				# Tell the Mume server to put IAC-GA at end of prompts.
				self._server.sendall(b"~$#EP2\nG\n")
				# Tell the server that we will negotiate the character set.
				self._server.sendall(IAC + WILL + CHARSET)
				self.inCharset = True
				encounteredInitialOutput = True
			result = self.processData(data)
			try:
				if self._outputFormat == "raw":
					self._client.sendall(result)
				else:
					self._client.sendall(unescapeXML(result, isbytes=True))
			except EnvironmentError:
				self.close()
				continue
		if self._interface != "text":
			# Shutdown the gui
			with self._mapper._gui_queue_lock:
				self._mapper._gui_queue.put(None)
		# Join the MPI threads (if any) before joining the Mapper thread.
		for mpiThread in self.mpiThreads:
			mpiThread.join()


class MockedSocket(object):
	def connect(self, *args):
		pass

	def getpeercert(*args):
		return {"subject": [["commonName", "mume.org"]]}

	def shutdown(self, *args):
		pass

	def close(self, *args):
		pass

	def sendall(self, *args):
		pass


def main(
		outputFormat,
		interface,
		isEmulatingOffline,
		promptTerminator,
		gagPrompts,
		findFormat,
		localHost,
		localPort,
		remoteHost,
		remotePort,
		noSsl
):
	outputFormat = outputFormat.strip().lower()
	interface = interface.strip().lower()
	if not promptTerminator:
		promptTerminator = IAC + GA
	if not gagPrompts:
		gagPrompts = False
	if interface != "text":
		try:
			import pyglet
		except ImportError:
			print("Unable to find pyglet. Disabling the GUI")
			interface = "text"
	# initialise client connection
	proxySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	proxySocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	proxySocket.bind((localHost, localPort))
	proxySocket.listen(1)
	touch(LISTENING_STATUS_FILE)
	clientConnection, proxyAddress = proxySocket.accept()
	clientConnection.settimeout(1.0)
	# initialise server connection
	if isEmulatingOffline:
		serverConnection = MockedSocket()
	else:
		serverConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		serverConnection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		serverConnection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		if not noSsl and ssl is not None:
			serverConnection = ssl.wrap_socket(
				serverConnection,
				cert_reqs=ssl.CERT_REQUIRED,
				ca_certs=certifi.where(),
				ssl_version=ssl.PROTOCOL_TLS
			)
	try:
		serverConnection.connect((remoteHost, remotePort))

	except TimeoutError:
		try:
			clientConnection.sendall(b"\r\nError: server connection timed out!\r\n")
			clientConnection.sendall(b"\r\n")
			clientConnection.shutdown(socket.SHUT_RDWR)
		except EnvironmentError:
			pass
		clientConnection.close()
		try:
			os.remove(LISTENING_STATUS_FILE)
		except Exception:
			pass
		return
	if not noSsl and ssl is not None:
		# Validating server identity with ssl module
		# See https://wiki.python.org/moin/SSL
		for field in serverConnection.getpeercert()["subject"]:
			if field[0][0] == "commonName":
				certhost = field[0][1]
				if certhost != "mume.org":
					raise ssl.SSLError("Host name 'mume.org' doesn't match certificate host '{}'".format(certhost))
	mapperThread = Mapper(
		client=clientConnection,
		server=serverConnection,
		outputFormat=outputFormat,
		interface=interface,
		promptTerminator=promptTerminator,
		gagPrompts=gagPrompts,
		findFormat=findFormat,
		isEmulatingOffline=isEmulatingOffline,
	)
	proxyThread = Proxy(
		client=clientConnection,
		server=serverConnection,
		mapper=mapperThread,
		isEmulatingOffline=isEmulatingOffline
	)
	serverThread = Server(
		client=clientConnection,
		server=serverConnection,
		mapper=mapperThread,
		outputFormat=outputFormat,
		interface=interface,
		promptTerminator=promptTerminator
	)
	if not isEmulatingOffline:
		serverThread.start()
	proxyThread.start()
	mapperThread.start()
	if interface != "text":
		pyglet.app.run()
	if not isEmulatingOffline:
		serverThread.join()
	try:
		serverConnection.shutdown(socket.SHUT_RDWR)
	except EnvironmentError:
		pass
	if not isEmulatingOffline:
		mapperThread.queue.put((None, None))
	mapperThread.join()
	try:
		clientConnection.sendall(b"\r\n")
		proxyThread.close()
		clientConnection.shutdown(socket.SHUT_RDWR)
	except EnvironmentError:
		pass
	proxyThread.join()
	serverConnection.close()
	clientConnection.close()
	try:
		os.remove(LISTENING_STATUS_FILE)
	except Exception:
		pass
