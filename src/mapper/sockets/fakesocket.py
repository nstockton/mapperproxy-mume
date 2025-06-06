# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import time
from typing import Any, Union


logger: logging.Logger = logging.getLogger(__name__)


class FakeSocketEmptyError(Exception):
	pass


class FakeSocket:
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		self.inboundBuffer: Union[bytes, None] = None
		self.timeout: Union[float, None] = None

	def gettimeout(self) -> Union[float, None]:
		return self.timeout

	def settimeout(self, timeout: Union[float, None]) -> None:
		self.timeout = None if timeout is None else float(timeout)

	def getblocking(self) -> bool:
		return self.gettimeout() is None

	def setblocking(self, flag: bool) -> None:
		self.settimeout(None if flag else 0.0)

	def connect(self, *args: Any) -> None:  # pragma: no cover
		pass

	def setsockopt(self, *args: Any) -> None:  # pragma: no cover
		pass

	def getpeercert(self, *args: Any) -> dict[str, list[list[str]]]:  # NOQA: PLR6301
		return {"subject": [["commonName", "mume.org"]]}

	def shutdown(self, *args: Any) -> None:  # pragma: no cover
		pass

	def close(self, *args: Any) -> None:  # pragma: no cover
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
		raise FakeSocketEmptyError
