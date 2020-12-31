# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import importlib
import logging
import os
import select
import socket
import ssl
import threading
import time
from types import ModuleType
from typing import Union

# Third-party Modules:
from boltons.socketutils import _UNSET, DEFAULT_MAXSIZE, BufferedSocket

# Local Modules:
from .mapper import Mapper
from .utils import getDirectoryPath, touch


try:
	certifi: Union[ModuleType, None] = importlib.import_module("certifi")
except ImportError:
	certifi = None

try:
	pyglet: Union[ModuleType, None] = importlib.import_module("pyglet")
except ImportError:
	print("Unable to import Pyglet. GUI will be disabled.")
	pyglet = None


LISTENING_STATUS_FILE = os.path.join(getDirectoryPath("."), "mapper_ready.ignore")


logger = logging.getLogger(__name__)


class BufferedSSLSocket(BufferedSocket):
	def __init__(
		self, sock, timeout=_UNSET, maxsize=DEFAULT_MAXSIZE, recvsize=_UNSET, insecure=False, **sslKWArgs
	):
		super().__init__(sock, timeout, maxsize, recvsize)
		if not insecure and ssl is not None:
			self.wrapSSL(**sslKWArgs)

	def wrapSSL(self, **kwargs):
		if not certifi:
			print("Error: cannot encrypt connection. Certifi not found.")
			return None
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


class Player(threading.Thread):
	def __init__(self, player, mapper):
		threading.Thread.__init__(self)
		self.name = "Player"
		self.player = player
		self.mapper = mapper
		self.finished = threading.Event()

	def close(self):
		self.finished.set()

	def run(self):
		while not self.finished.isSet():
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
	def __init__(self, game, mapper):
		threading.Thread.__init__(self)
		self.name = "Game"
		self.game = game
		self.mapper = mapper
		self.finished = threading.Event()

	def close(self):
		self.finished.set()

	def run(self):
		while not self.finished.isSet():
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
	def __init__(self, *args, **kwargs):
		self.inboundBuffer = None
		self.timeout = None

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

	def setsockopt(self, *args):
		pass

	def getpeercert(self, *args):
		return {"subject": [["commonName", "mume.org"]]}

	def shutdown(self, *args):
		pass

	def close(self, *args):
		pass

	def send(self, data, flags=0):
		if data == b"quit":
			self.inboundBuffer = b""
		return len(data)

	def sendall(self, data, flags=0):
		self.send(data, flags)
		return None  # sendall returns None on success.

	def recv(self, buffersize, flags=0):
		#  Simulate some lag.
		time.sleep(0.005)
		if self.inboundBuffer is not None:
			inboundBuffer = self.inboundBuffer
			self.inboundBuffer = None
			return inboundBuffer
		raise MockedSocketEmpty()


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
	noSsl,
):
	# initialise client connection
	proxySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	proxySocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	proxySocket.bind((localHost, localPort))
	proxySocket.listen(1)
	touch(LISTENING_STATUS_FILE)
	playerSocket, playerAddress = proxySocket.accept()
	playerSocket = BufferedSocket(playerSocket, timeout=1.0)
	# initialise server connection
	try:
		if isEmulatingOffline:
			gameSocket = MockedSocket()
		else:
			gameSocket = socket.create_connection((remoteHost, remotePort))
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
		gameSocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		gameSocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	gameSocket = BufferedSSLSocket(
		gameSocket, timeout=None, insecure=noSsl or isEmulatingOffline, server_hostname=remoteHost
	)
	mapperThread = Mapper(
		playerSocket=playerSocket,
		gameSocket=gameSocket,
		outputFormat=outputFormat,
		interface=interface,
		promptTerminator=promptTerminator,
		gagPrompts=gagPrompts,
		findFormat=findFormat,
		isEmulatingOffline=isEmulatingOffline,
	)
	playerThread = Player(playerSocket, mapperThread)
	gameThread = Game(gameSocket, mapperThread)
	gameThread.start()
	playerThread.start()
	mapperThread.start()
	if interface != "text":
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
