# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import socket
import sys
import threading
import traceback
from contextlib import ExitStack, closing, suppress
from pathlib import Path

# Third-party Modules:
import pyglet
from knickknacks.platforms import get_directory_path
from tap import Tap

# Local Modules:
from . import INTERFACES, LITERAL_INTERFACES, LITERAL_OUTPUT_FORMATS, OUTPUT_FORMATS, __version__
from .mapper import Mapper
from .sockets.bufferedsocket import BufferedSocket
from .sockets.fakesocket import FakeSocket, FakeSocketEmptyError


LISTENING_STATUS_FILE: Path = Path(get_directory_path("mapper_ready.ignore"))


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
			except TimeoutError:  # NOQA: PERF203
				continue
			except OSError:
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
			except FakeSocketEmptyError:  # NOQA: PERF203
				continue
			except OSError:
				self.close()
				continue
		if self.mapper.interface != "text":
			# Shutdown the gui
			self.mapper._gui_queue.put(None)


class ArgumentParser(Tap):
	emulation: bool = False
	"""Start in emulation mode."""
	interface: LITERAL_INTERFACES = INTERFACES[0]
	"""Select a user interface."""
	format: LITERAL_OUTPUT_FORMATS = OUTPUT_FORMATS[0]
	"""Select how data from the server is transformed before  being sent to the client."""
	local_host: str = "127.0.0.1"
	"""The local host address to bind to."""
	local_port: int = 4000
	"""The local port to bind to."""
	remote_host: str = "mume.org"
	"""The remote host address to connect to."""
	remote_port: int = 4242
	"""The remote port to connect to."""
	no_ssl: bool = False
	"""Disable encrypted communication between the local and remote hosts."""
	prompt_terminator_lf: bool = False
	"""Terminate game prompts with return-linefeed characters (IAC + GA is default)."""
	gag_prompts: bool = False
	"""Gag emulated prompts."""
	find_format: str = "{vnum}, {name}, {attribute}"
	"""
	The format string for controlling output of the find commands.
	Accepts the following placeholders in braces:
	{attribute}, {direction}, {clockPosition}, {distance}, {name}, {vnum}.
	Where {attribute} represents the attribute on which the search is performed.
	"""

	def configure(self) -> None:
		version: str = (
			f"%(prog)s v{__version__} "
			+ f"(Python {'.'.join(str(i) for i in sys.version_info[:3])} {sys.version_info.releaselevel})"
		)
		self.add_argument(
			"-v",
			"--version",
			help="Print the program version as well as the Python version.",
			action="version",
			version=version,
		)
		self.add_argument("-e", "--emulation")
		self.add_argument("-i", "--interface")
		self.add_argument("-f", "--format")
		self.add_argument("-lh", "--local_host", metavar="address")
		self.add_argument("-lp", "--local_port", metavar="port")
		self.add_argument("-rh", "--remote_host", metavar="address")
		self.add_argument("-rp", "--remote_port", metavar="port")
		self.add_argument("-nssl", "--no_ssl")
		self.add_argument("-ptlf", "--prompt_terminator_lf")
		self.add_argument("-gp", "--gag_prompts")
		self.add_argument("-ff", "--find_format", metavar="text")


def main(
	outputFormat: str,
	interface: str,
	isEmulatingOffline: bool,
	promptTerminator: bytes | None,
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
	LISTENING_STATUS_FILE.touch()
	unbufferedPlayerSocket: socket.socket
	playerAddress: tuple[str, int]
	unbufferedPlayerSocket, playerAddress = proxySocket.accept()  # NOQA: F841
	playerSocket: BufferedSocket = BufferedSocket(
		unbufferedPlayerSocket,
		timeout=1.0,
	)
	# initialise server connection
	unbufferedGameSocket: socket.socket | FakeSocket
	try:
		if isEmulatingOffline:
			unbufferedGameSocket = FakeSocket()
		else:
			unbufferedGameSocket = socket.create_connection((remoteHost, remotePort))
	except TimeoutError:
		cm: ExitStack
		with ExitStack() as cm:
			cm.enter_context(closing(playerSocket))
			cm.enter_context(suppress(EnvironmentError))
			playerSocket.sendall(b"\r\nError: server connection timed out!\r\n")
			playerSocket.sendall(b"\r\n")
			playerSocket.shutdown(socket.SHUT_RDWR)
			LISTENING_STATUS_FILE.unlink(missing_ok=True)
			return
	else:
		unbufferedGameSocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		unbufferedGameSocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	gameSocket: BufferedSocket = BufferedSocket(
		unbufferedGameSocket,
		timeout=None,
		encrypt=not noSsl and not isEmulatingOffline,
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
	if interface != "text":
		pyglet.app.run()
	gameThread.join()
	with suppress(EnvironmentError):
		gameSocket.shutdown(socket.SHUT_RDWR)
	mapperThread.queue.put(None)
	mapperThread.join()
	with suppress(EnvironmentError):
		playerSocket.sendall(b"\r\n")
		playerThread.close()
		playerSocket.shutdown(socket.SHUT_RDWR)
	playerThread.join()
	mapperThread.proxy.close()
	mapperThread.gmcpRemoteEditing.close()
	gameSocket.close()
	playerSocket.close()
	LISTENING_STATUS_FILE.unlink(missing_ok=True)


def run() -> None:
	parser: ArgumentParser = ArgumentParser(
		underscores_to_dashes=True, description="The accessible Mume mapper."
	)
	args: ArgumentParser = parser.parse_args()
	try:
		logging.info("Initializing")  # NOQA: LOG015
		main(
			outputFormat=args.format,
			interface=args.interface,
			isEmulatingOffline=args.emulation,
			promptTerminator=b"\r\n" if args.prompt_terminator_lf else None,
			gagPrompts=args.gag_prompts,
			findFormat=args.find_format,
			localHost=args.local_host,
			localPort=args.local_port,
			remoteHost=args.remote_host,
			remotePort=args.remote_port,
			noSsl=args.no_ssl,
		)
	except Exception:
		traceback.print_exc()
		logging.exception("OOPS!")  # NOQA: LOG015
	finally:
		logging.info("Shutting down.")  # NOQA: LOG015
		logging.shutdown()
