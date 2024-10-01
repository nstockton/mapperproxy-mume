# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:  # pragma: no cover
	# Prevent cyclic import.
	from .mapper import Mapper


class Handler(ABC):
	def __init__(self, mapper: Mapper, event: Optional[str] = None) -> None:
		"""
		Initialises a mud event handler in the given mapper instance.

		Args:
			mapper: An instance of mapper.mapper.Mapper that dispatches events.
			event: The event name. May be omitted if the subclass defines an event attribute.
		"""
		self.mapper = mapper
		if event:
			self.event = event
		elif not hasattr(self, "event"):
			raise ValueError(
				"Tried to initialise handler without an event type."
				+ " Either pass event=MyEventType when initialising, "
				+ "or declare self.event in the class definition."
			)
		self.mapper.registerMudEventHandler(self.event, self.handle)

	def __del__(self) -> None:
		"""Deregisters the event handler after the object is deleted and garbage collected."""
		if hasattr(self, "event"):
			self.mapper.deregisterMudEventHandler(self.event, self.handle)

	@abstractmethod
	def handle(self, text: str) -> None:
		"""Called when the event is dispatched."""
