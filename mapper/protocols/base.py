# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable


logger: logging.Logger = logging.getLogger(__name__)


class BaseProtocol(ABC):
	@abstractmethod
	def write(self, data: bytes) -> None:
		"""
		Writes data to peer.

		Args:
			data: The bytes to be written.
		"""

	@abstractmethod
	def on_connectionMade(self) -> None:
		"""Called by `connect` when a connection to peer has been established."""

	@abstractmethod
	def on_connectionLost(self) -> None:
		"""Called by `disconnect` when a connection to peer has been lost."""

	@abstractmethod
	def on_dataReceived(self, data: bytes) -> None:
		"""
		Called by `parse` when data is received.

		Args:
			data: The received data.
		"""


class Protocol(BaseProtocol):
	def __init__(
		self, writer: Callable[[bytes], None], receiver: Callable[[bytes], None], **kwargs: Any
	) -> None:
		self._writer: Callable[[bytes], None] = writer
		self._receiver: Callable[[bytes], None] = receiver

	def write(self, data: bytes) -> None:
		self._writer(data)

	def on_dataReceived(self, data: bytes) -> None:
		self._receiver(data)
