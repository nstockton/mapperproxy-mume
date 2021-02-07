# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import os
import socket
import threading
from typing import Tuple, Union

# Local Modules:
from .mapper import Mapper
from .sockets.bufferedsocket import BufferedSocket
from .sockets.fakesocket import FakeSocket, FakeSocketEmpty
from .utils import getDirectoryPath, touch


try:
	import pyglet  # type: ignore[import]
except ImportError:
	pyglet = None


LISTENING_STATUS_FILE: str = os.path.join(getDirectoryPath("."), "mapper_ready.ignore")


logger: logging.Logger = logging.getLogger(__name__)


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
	def __init__(self, game: BufferedSocket, mapper: Mapper) -> None:
		threading.Thread.__init__(self)
		self.name: str = "Game"
		self.game: BufferedSocket = game
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
			except FakeSocketEmpty:
				continue
			except EnvironmentError:
				self.close()
				continue
		if self.mapper.interface != "text":
			# Shutdown the gui
			self.mapper._gui_queue.put(None)


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
	playerSocket: BufferedSocket = BufferedSocket(
		unbufferedPlayerSocket,
		timeout=1.0,
	)
	# initialise server connection
	unbufferedGameSocket: Union[socket.socket, FakeSocket]
	try:
		if isEmulatingOffline:
			unbufferedGameSocket = FakeSocket()
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
	gameSocket: BufferedSocket = BufferedSocket(
		unbufferedGameSocket,
		timeout=None,
		encrypt=False if noSsl or isEmulatingOffline else True,
		server_hostname=remoteHost,
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
