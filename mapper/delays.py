# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import threading


_delays = []


class Delay(threading.Thread):
	def __init__(self, _interval, _iterations, _function, *args, **kwargs):
		super().__init__()
		self.daemon = True
		self._interval = _interval
		self._iterations = _iterations
		self._function = _function
		self._args = args
		self._kwargs = kwargs
		self._finished = threading.Event()
		self.start()

	def stop(self):
		self._finished.set()

	def run(self):
		try:
			_delays.append(self)
			while not self._finished.is_set() and (self._iterations is None or self._iterations > 0):
				self._finished.wait(self._interval)
				if not self._finished.is_set():
					self._function(*self._args, **self._kwargs)
				if self._iterations is not None:
					self._iterations -= 1
		finally:
			del self._function, self._args, self._kwargs
			_delays.remove(self)


class OneShot(Delay):
	def __init__(self, _interval, _function, *args, **kwargs):
		super().__init__(_interval, 1, _function, *args, **kwargs)


class Repeating(Delay):
	def __init__(self, _interval, _function, *args, **kwargs):
		super().__init__(_interval, None, _function, *args, **kwargs)
