# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging
import os
import select
import socket
import ssl
from telnetlib import DO, GA, IAC, NAWS, TTYPE
import threading

# Third-party Modules:
from boltons.socketutils import _UNSET, DEFAULT_MAXSIZE, BufferedSocket
try:
	import certifi
except ImportError:
	certifi = None

# Local Modules:
from .protocols import ProtocolHandler
from .protocols.telnetfilter import TelnetFilter
from .protocols.mpi import MPI_INIT
from .mapper import USER_DATA, Mapper
from .utils import getDirectoryPath, removeFile, touch


LISTENING_STATUS_FILE = os.path.join(getDirectoryPath("."), "mapper_ready.ignore")


logger = logging.getLogger(__name__)


class BufferedSSLSocket(BufferedSocket):
	def __init__(
			self,
			sock,
			timeout=_UNSET,
			maxsize=DEFAULT_MAXSIZE,
			recvsize=_UNSET,
			insecure=False,
			**sslKWArgs
	):
		super().__init__(sock, timeout, maxsize, recvsize)
		if not insecure and ssl is not None:
			self.wrapSSL(**sslKWArgs)

	def wrapSSL(self, **kwargs):
		if not certifi:
			print("Error: cannot encrypt connection. Certifi not found.")
			return
		kwargs["do_handshake_on_connect"] = False  # This needs to always be set to False.
		with self._recv_lock:
			with self._send_lock:
				sock = self.sock
				originalTimeout = sock.gettimeout()
				sock.settimeout(None)
				try:
					context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
					context.load_verify_locations(certifi.where())
					sock = context.wrap_socket(sock, **kwargs)
					self.doSSLHandshake(sock)
				finally:
					sock.settimeout(originalTimeout)
					self.sock = sock

	def doSSLHandshake(self, sock):
		while True:
			try:
				sock.do_handshake()
				break
			except ssl.SSLWantReadError:
				select.select([sock], [], [])
			except ssl.SSLWantWriteError:
				select.select([], [sock], [])


class Proxy(threading.Thread):
	def __init__(self, client, server, mapper, isEmulatingOffline):
		threading.Thread.__init__(self)
		self.name = "Proxy"
		self._client = client
		self._server = server
		self._mapper = mapper
		self.isEmulatingOffline = isEmulatingOffline
		self._handler = TelnetFilter()
		self.finished = threading.Event()

	def close(self):
		self.finished.set()

	def sendClient(self, data):
		self._client.sendall(data)

	def sendServer(self, data):
		try:
			self._server.sendall(data)
			return True
		except EnvironmentError:
			self.close()
			return False

	def run(self):
		handler = self._handler
		userCommands = [
			func[len("user_command_"):].encode("us-ascii", "ignore") for func in dir(self._mapper)
			if func.startswith("user_command_")
		]
		while not self.finished.isSet():
			try:
				data = self._client.recv(4096)
				negotiations, text = handler.parse(data)
			except socket.timeout:
				continue
			except EnvironmentError:
				self.close()
				continue
			if not data:
				self.close()
			elif text.strip() and (self.isEmulatingOffline or text.strip().split()[0] in userCommands):
				self._mapper.queue.put((USER_DATA, text))
				if negotiations:
					self.sendServer(negotiations)
			else:
				self.sendServer(data)


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
		# The initial output of MUME. Used by the server thread to detect connection success.
		self.initialOutput = IAC + DO + TTYPE + IAC + DO + NAWS
		self.initialConfiguration = [  # What the server thread sends MUME on connection success.
			# Identify for Mume Remote Editing.
			MPI_INIT + b"I\n",
			# Turn on XML mode.
			# Mode "3" tells MUME to enable XML output without sending an initial "<xml>" tag.
			# Option "G" tells MUME to wrap room descriptions in gratuitous tags if they would otherwise be hidden.
			MPI_INIT + b"X2\n3G\n",
			# Tell the Mume server to put IAC-GA at end of prompts.
			MPI_INIT + b"P2\nG\n"
		]
		self._handler = ProtocolHandler(
			remoteSender=self.sendServer,
			eventSender=self._mapper.queue.put,
			outputFormat=self._outputFormat,
			promptTerminator=self._promptTerminator
		)

	def close(self):
		self.finished.set()

	def sendClient(self, data):
		self._client.sendall(data)

	def sendServer(self, data):
		self._server.sendall(data)

	def run(self):
		handler = self._handler
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
			elif not encounteredInitialOutput and data.startswith(self.initialOutput):
				# The connection to Mume has been established, and the game has just responded with the login screen.
				for item in self.initialConfiguration:
					self.sendServer(item)
				handler._telnet.charset("us-ascii")
				encounteredInitialOutput = True
			try:
				self.sendClient(handler.parse(data))
			except EnvironmentError:
				self.close()
				continue
		if self._interface != "text":
			# Shutdown the gui
			with self._mapper._gui_queue_lock:
				self._mapper._gui_queue.put(None)
		handler.close()


class MockedSocket(object):
	timeout = None

	def gettimeout(self):
		return self.timeout

	def settimeout(self, timeout):
		self.timeout = None if timeout is None else float(timeout)

	def getblocking(self):
		return self.gettimeout() is None

	def setblocking(self, flag):
		self.settimeout(None if flag else 0.0)

	def connect(self, *args):
		pass

	def getpeercert(*args):
		return {"subject": [["commonName", "mume.org"]]}

	def shutdown(self, *args):
		pass

	def close(self, *args):
		pass

	def send(self, data, flags=0):
		return len(data)

	def sendall(self, data, flags=0):
		return None  # sendall returns None on success.


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
	clientConnection = BufferedSocket(clientConnection, timeout=1.0)
	# initialise server connection
	if isEmulatingOffline:
		serverConnection = MockedSocket()
	else:
		serverConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		serverConnection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		serverConnection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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
		removeFile(LISTENING_STATUS_FILE)
		return
	serverConnection = BufferedSSLSocket(
		serverConnection,
		timeout=None,
		insecure=noSsl or isEmulatingOffline,
		server_hostname=remoteHost
	)
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
	removeFile(LISTENING_STATUS_FILE)
