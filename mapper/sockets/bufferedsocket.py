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
from typing import Any, Union

# Third-party Modules:
import certifi
from boltons import socketutils  # type: ignore[import]

# Local Modules:
from .fakesocket import FakeSocket


CERT_LOCATION: str = certifi.where()


logger: logging.Logger = logging.getLogger(__name__)


class BufferedSocket(socketutils.BufferedSocket):  # type: ignore[misc, no-any-unimported]
	def __init__(  # type: ignore[no-any-unimported]
		self,
		sock: Union[socket.socket, FakeSocket],
		timeout: Union[socketutils._UNSET, float, None] = socketutils._UNSET,
		maxsize: int = socketutils.DEFAULT_MAXSIZE,
		recvsize: Union[socketutils._UNSET, int] = socketutils._UNSET,
		encrypt: bool = False,
		**kwargs: Any,
	) -> None:
		"""
		Defines the constructor for the object.

		Args:
			sock: The connected socket to be wrapped.
			timeout: The default timeout for [send][1] and [recv][2], in seconds.
				Set to `None` for no timeout, `0` for nonblocking.
				[1]: <https://docs.python.org/library/socket.html#socket.socket.send>
				[2]: <https://docs.python.org/library/socket.html#socket.socket.recv>
			maxsize: The maximum number of bytes to be received into the buffer before it raises an exception.
			recvsize: The number of bytes to receive for every lower-level [`socket.recv`][1] call.
				[1]: <https://docs.python.org/library/socket.html#socket.socket.recv>
			encrypt: True if the socket should be wrapped in an [SSL context][1], False otherwise.
				[1]: <https://docs.python.org/library/ssl.html#ssl.SSLContext>
			**kwargs: Key-word only arguments to be passed to the
				[wrapSSL][mapper.sockets.bufferedsocket.BufferedSocket.wrapSSL] method.
		"""
		self.sock: Union[socket.socket, FakeSocket, ssl.SSLSocket]
		super().__init__(sock, timeout, maxsize, recvsize)
		if encrypt and isinstance(self.sock, socket.socket):
			self.sock = self.wrapSSL(self.sock, **kwargs)

	def wrapSSL(self, sock: socket.socket, **kwargs: Any) -> ssl.SSLSocket:
		"""
		Wraps a socket in an SSL context.

		Args:
			sock: The unencrypted socket.
			**kwargs: Key-word only arguments to be passed to the [`SSLContext.wrap_socket`][1] method.
				[1]: <https://docs.python.org/library/ssl.html#ssl.SSLContext.wrap_socket>

		Returns:
			The socket wrapped in an
			[SSL context.](https://docs.python.org/library/ssl.html#ssl.SSLContext)
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

	def doSSLHandshake(self, sock: ssl.SSLSocket) -> None:
		"""
		Performs an SSL handshake.

		Note:
			The [`SSLSocket.do_handshake`][1] method is non-blocking and must be retried until it returns successfully.
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
