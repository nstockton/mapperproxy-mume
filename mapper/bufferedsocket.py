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
from typing import Any, Optional, Union

# Third-party Modules:
import certifi
from boltons import socketutils  # type: ignore[import]

# Local Modules:
from .fakesocket import FakeSocket


CERT_LOCATION = certifi.where()


logger: logging.Logger = logging.getLogger(__name__)


class BufferedSocket(socketutils.BufferedSocket):  # type: ignore[misc, no-any-unimported]
	def __init__(  # type: ignore[no-any-unimported]
		self,
		sock: Union[socket.socket, FakeSocket],
		timeout: Union[socketutils._UNSET, float, None] = socketutils._UNSET,
		maxsize: int = socketutils.DEFAULT_MAXSIZE,
		recvsize: Union[socketutils._UNSET, int] = socketutils._UNSET,
		encrypt: bool = False,
		**sslKWArgs: Any,
	) -> None:
		self.sock: Union[socket.socket, FakeSocket, ssl.SSLSocket]
		super().__init__(sock, timeout, maxsize, recvsize)
		if encrypt:
			self.wrapSSL(**sslKWArgs)

	def wrapSSL(
		self,
		server_side: bool = False,
		do_handshake_on_connect: bool = True,
		suppress_ragged_eofs: bool = True,
		server_hostname: Optional[str] = None,
		session: Optional[ssl.SSLSession] = None,
	) -> None:
		with self._recv_lock:
			with self._send_lock:
				sock: Union[socket.socket, FakeSocket, ssl.SSLSocket] = self.sock
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
