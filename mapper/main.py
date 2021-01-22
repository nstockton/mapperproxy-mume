# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import os
import select
import socket
import ssl
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party Modules:
from boltons.socketutils import _UNSET, DEFAULT_MAXSIZE, BufferedSocket

# Local Modules:
from .mapper import Mapper
from .utils import getDirectoryPath, touch


CERT_LOCATION: Union[str, None]
try:
	import certifi
except ImportError:
	CERT_LOCATION = None
else:
	CERT_LOCATION = certifi.where()

piglet: "Union[pyglet, None]"
try:
	import pyglet
except ImportError:
	pyglet = None
	print("Unable to import Pyglet. GUI will be disabled.")


LISTENING_STATUS_FILE: str = os.path.join(getDirectoryPath("."), "mapper_ready.ignore")


logger: logging.Logger = logging.getLogger(__name__)


class BufferedSSLSocket(BufferedSocket):  # type: ignore
	def __init__(
		self,
		sock: Union[socket.socket, MockedSocket],
		timeout: Union[_UNSET, float, None] = _UNSET,
		maxsize: int = DEFAULT_MAXSIZE,
		recvsize: Union[_UNSET, int] = _UNSET,
		insecure: bool = False,
		**sslKWArgs: Any,
	) -> None:
		self.sock: Union[socket.socket, MockedSocket, ssl.SSLSocket]
		super().__init__(sock, timeout, maxsize, recvsize)
		if not insecure and ssl is not None:
			self.wrapSSL(**sslKWArgs)

	def wrapSSL(
		self,
		server_side: bool = False,
		do_handshake_on_connect: bool = True,
		suppress_ragged_eofs: bool = True,
		server_hostname: Optional[str] = None,
		session: Optional[ssl.SSLSession] = None,
	) -> None:
		if CERT_LOCATION is None:
			print("Error: cannot encrypt connection. Certifi not found.")
			return None
		with self._recv_lock:
			with self._send_lock:
				sock: Union[socket.socket, MockedSocket, ssl.SSLSocket] = self.sock
				originalTimeout: Union[float, None] = sock.gettimeout()
				sock.settimeout(None)
				try:
					if isinstance(sock, socket.socket):
						context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
						context.load_verify_locations(CERT_LOCATION)
						sock = context.wrap_socket(
							sock,
							server_side=server_side,
							do_handshake_on_connect=False,  # This should always be set to False.
							suppress_ragged_eofs=suppress_ragged_eofs,
							server_hostname=server_hostname,
							session=session,
						)
					if isinstance(sock, ssl.SSLSocket):
						self.doSSLHandshake(sock)
				finally:
					sock.settimeout(originalTimeout)
					self.sock = sock

	def doSSLHandshake(self, sock: ssl.SSLSocket) -> None:
		while True:
			try:
				sock.do_handshake()
				break
			except ssl.SSLWantReadError:
				select.select([sock], [], [])
			except ssl.SSLWantWriteError:
				select.select([], [sock], [])


class Player(threading.Thread):
	def __init__(self, player: BufferedSocket, mapper: Mapper) -> None:
		threading.Thread.__init__(self)
		self.name: str = "Player"
		self.player: BufferedSocket = player
		self.mapper: Mapper = mapper
		self.finished: threading.Event = threading.Event()

	def close(self) -> None:
		self.finished.set()

	def run(self) -> None:
		data: bytes
		while not self.finished.is_set():
			try:
				data = self.player.recv(4096)
				if data:
					self.mapper.proxy.player.parse(data)
				else:
					self.close()
			except socket.timeout:
				continue
			except EnvironmentError:
				self.close()
				continue
		if self.mapper.isEmulatingOffline:
			self.mapper.proxy.game.write(b"quit")


class Game(threading.Thread):
	def __init__(self, game: BufferedSSLSocket, mapper: Mapper) -> None:
		threading.Thread.__init__(self)
		self.name: str = "Game"
		self.game: BufferedSSLSocket = game
		self.mapper: Mapper = mapper
		self.finished: threading.Event = threading.Event()

	def close(self) -> None:
		self.finished.set()

	def run(self) -> None:
		data: bytes
		while not self.finished.is_set():
			try:
				data = self.game.recv(4096)
				if data:
					self.mapper.proxy.game.parse(data)
				else:
					self.close()
			except MockedSocketEmpty:
				continue
			except EnvironmentError:
				self.close()
				continue
		if self.mapper.interface != "text":
			# Shutdown the gui
			self.mapper._gui_queue.put(None)


class MockedSocketEmpty(Exception):
	pass


class MockedSocket(object):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		self.inboundBuffer = Union[bytes, None]
		self.timeout: Union[float, None] = None

	def gettimeout(self) -> Union[float, None]:
		return self.timeout

	def settimeout(self, timeout: Union[float, None]) -> None:
		self.timeout = None if timeout is None else float(timeout)

	def getblocking(self) -> bool:
		return self.gettimeout() is None

	def setblocking(self, flag: bool) -> None:
		self.settimeout(None if flag else 0.0)

	def connect(self, *args: Any) -> None:
		pass

	def setsockopt(self, *args: Any) -> None:
		pass

	def getpeercert(self, *args: Any) -> Dict[str, List[List[str]]]:
		return {"subject": [["commonName", "mume.org"]]}

	def shutdown(self, *args: Any) -> None:
		pass

	def close(self, *args: Any) -> None:
		pass

	def send(self, data: bytes, flags: int = 0) -> int:
		if data == b"quit":
			self.inboundBuffer = b""
		return len(data)

	def sendall(self, data: bytes, flags: int = 0) -> None:
		self.send(data, flags)

	def recv(self, buffersize: int, flags: int = 0) -> bytes:
		#  Simulate some lag.
		time.sleep(0.005)
		if isinstance(self.inboundBuffer, bytes):
			inboundBuffer: bytes = self.inboundBuffer
			self.inboundBuffer = None
			return inboundBuffer
		raise MockedSocketEmpty()


def main(
	outputFormat: str,
	interface: str,
	isEmulatingOffline: bool,
	promptTerminator: Union[bytes, None],
	gagPrompts: bool,
	findFormat: str,
	localHost: str,
	localPort: int,
	remoteHost: str,
	remotePort: int,
	noSsl: bool,
) -> None:
	# initialise client connection
	proxySocket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	proxySocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	proxySocket.bind((localHost, localPort))
	proxySocket.listen(1)
	touch(LISTENING_STATUS_FILE)
	unbufferedPlayerSocket: socket.socket
	playerAddress: Tuple[str, int]
	unbufferedPlayerSocket, playerAddress = proxySocket.accept()
	playerSocket: BufferedSocket = BufferedSocket(unbufferedPlayerSocket, timeout=1.0)
	# initialise server connection
	unbufferedGameSocket: Union[socket.socket, MockedSocket]
	try:
		if isEmulatingOffline:
			unbufferedGameSocket = MockedSocket()
		else:
			unbufferedGameSocket = socket.create_connection((remoteHost, remotePort))
	except TimeoutError:
		try:
			playerSocket.sendall(b"\r\nError: server connection timed out!\r\n")
			playerSocket.sendall(b"\r\n")
			playerSocket.shutdown(socket.SHUT_RDWR)
		except EnvironmentError:
			pass
		finally:
			playerSocket.close()
			os.remove(LISTENING_STATUS_FILE)
			return None
	else:
		unbufferedGameSocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		unbufferedGameSocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	gameSocket: BufferedSSLSocket = BufferedSSLSocket(
		unbufferedGameSocket, timeout=None, insecure=noSsl or isEmulatingOffline, server_hostname=remoteHost
	)
	mapperThread: Mapper = Mapper(
		playerSocket=playerSocket,
		gameSocket=gameSocket,
		outputFormat=outputFormat,
		interface=interface,
		promptTerminator=promptTerminator,
		gagPrompts=gagPrompts,
		findFormat=findFormat,
		isEmulatingOffline=isEmulatingOffline,
	)
	playerThread: Player = Player(playerSocket, mapperThread)
	gameThread: Game = Game(gameSocket, mapperThread)
	gameThread.start()
	playerThread.start()
	mapperThread.start()
	if interface != "text" and pyglet is not None:
		pyglet.app.run()
	gameThread.join()
	try:
		gameSocket.shutdown(socket.SHUT_RDWR)
	except EnvironmentError:
		pass
	mapperThread.queue.put((None, None))
	mapperThread.join()
	try:
		playerSocket.sendall(b"\r\n")
		playerThread.close()
		playerSocket.shutdown(socket.SHUT_RDWR)
	except EnvironmentError:
		pass
	playerThread.join()
	mapperThread.proxy.close()
	gameSocket.close()
	playerSocket.close()
	os.remove(LISTENING_STATUS_FILE)
