# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import threading
from typing import Any, Callable, List, Union


class BaseDelay(threading.Thread):
	"""
	Implements the base delay class.
	"""

	_delays: List[threading.Thread] = []

	def __init__(
		self, duration: int, count: Union[int, None], function: Callable[..., Any], *args, **kwargs
	) -> None:
		"""
		Args:
			duration: The amount of time (in seconds) to delay between iterations.
			count: The number of iterations to delay, or None to repeat indefinitely.
			function: The function to be called at each iteration.
				Any remaining positional or keyword arguments will be passed to this function.
		"""
		if count is not None and count < 0:
			raise ValueError("count must be a positive number or None.")
		super().__init__()
		self.daemon = True
		self._duration = duration
		self._count = count
		self._function = function
		self._args = args
		self._kwargs = kwargs
		self._finished = threading.Event()

	def stop(self) -> None:
		"""Stops an active delay."""
		self._finished.set()

	def run(self) -> None:
		try:
			self._delays.append(self)
			while not self._finished.is_set() and self._count != 0:
				self._finished.wait(self._duration)
				if not self._finished.is_set():
					self._function(*self._args, **self._kwargs)
				if self._count is not None:
					self._count -= 1
		finally:
			del self._function, self._args, self._kwargs
			self._delays.remove(self)


class Delay(BaseDelay):
	"""
	Implements a delay which automatically starts upon creation.
	"""

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.start()


class OneShot(Delay):
	"""
	Implements a delay which is run only once.
	"""

	def __init__(self, duration: int, function: Callable[..., Any], *args, **kwargs) -> None:
		"""
		Args:
			duration: The amount of time (in seconds) to delay.
			function: The function to be called when the delay completes.
				Any remaining positional or keyword arguments will be passed to this function.
		"""
		super().__init__(duration, 1, function, *args, **kwargs)


class Repeating(Delay):
	"""
	Implements a delay which runs indefinitely.
	"""

	def __init__(self, duration: int, function: Callable[..., Any], *args, **kwargs) -> None:
		"""
		Args:
			duration: The amount of time (in seconds) to delay between iterations.
			function: The function to be called at each iteration.
				Any remaining positional or keyword arguments will be passed to this function.
		"""
		super().__init__(duration, None, function, *args, **kwargs)