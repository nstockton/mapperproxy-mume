# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import select
import socket
import ssl
from contextlib import AbstractContextManager
from typing import Any, Union, cast

# Third-party Modules:
import certifi
from boltons import socketutils

# Local Modules:
from .fakesocket import FakeSocket


CERT_LOCATION: str = certifi.where()


logger: logging.Logger = logging.getLogger(__name__)


class BufferedSocket(socketutils.BufferedSocket):
	_recv_lock: AbstractContextManager[None]
	_send_lock: AbstractContextManager[None]

	def __init__(
		self,
		sock: Union[socket.socket, FakeSocket],
		*args: Any,
		encrypt: bool = False,
		**kwargs: Any,
	) -> None:
		"""
		Defines the constructor for the object.

		Args:
			sock: The connected socket to be wrapped.
			*args: Positional arguments to be passed to the parent constructor.
			encrypt:
				True if the socket should be wrapped in an [SSL context][1], False otherwise.
				[1]: <https://docs.python.org/library/ssl.html#ssl.SSLContext>
			**kwargs:
				Key-word only arguments to be passed to the parent constructor.
				Additional key-word only arguments will be passed to the
				[wrapSSL][mapper.sockets.bufferedsocket.BufferedSocket.wrapSSL] method.
		"""
		parentExtraArgs: tuple[str, ...] = ("timeout", "maxsize", "recvsize")
		parentKWArgs: dict[str, Any] = {arg: kwargs.pop(arg) for arg in parentExtraArgs if arg in kwargs}
		super().__init__(cast(socket.socket, sock), *args, **parentKWArgs)
		if encrypt and isinstance(self.sock, socket.socket):
			self.sock = self.wrapSSL(self.sock, **kwargs)

	def wrapSSL(self, sock: socket.socket, **kwargs: Any) -> ssl.SSLSocket:
		"""
		Wraps a socket in an SSL context.

		Args:
			sock: The unencrypted socket.
			**kwargs:
				Key-word only arguments to be passed to the [`SSLContext.wrap_socket`][1] method.
				[1]: <https://docs.python.org/library/ssl.html#ssl.SSLContext.wrap_socket>

		Returns:
			The socket wrapped in an [SSL context.][1]
			[1]: <https://docs.python.org/library/ssl.html#ssl.SSLContext>
		"""
		kwargs["do_handshake_on_connect"] = False  # Avoid race condition.
		with self._recv_lock, self._send_lock:
			originalTimeout: Union[float, None] = sock.gettimeout()
			sock.settimeout(None)
			try:
				context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
				context.load_verify_locations(CERT_LOCATION)
				sock = context.wrap_socket(sock, **kwargs)
				self.doSSLHandshake(sock)
			finally:
				sock.settimeout(originalTimeout)
		return sock

	@staticmethod
	def doSSLHandshake(sock: ssl.SSLSocket) -> None:
		"""
		Performs an SSL handshake.

		Note:
			The [`SSLSocket.do_handshake`][1] method
			is non-blocking and must be retried until it returns successfully.
			See [here][2] for further explanation.
			[1]: <https://docs.python.org/library/ssl.html#ssl.SSLSocket.do_handshake>
			[2]: <https://docs.python.org/library/ssl.html#ssl-nonblocking>

		Args:
			sock: The socket to perform the handshake on.
		"""
		while True:
			try:
				sock.do_handshake()
				break
			except ssl.SSLWantReadError:
				select.select([sock], [], [])
			except ssl.SSLWantWriteError:
				select.select([], [sock], [])
