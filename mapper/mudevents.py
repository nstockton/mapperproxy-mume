# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from abc import ABC, abstractmethod


class Handler(ABC):
	def __init__(self, mapper, event):
		self.mapper = mapper
		self.event = event
		self.mapper.registerMudEventHandler(event, self.handle)

	def __del__(self):
		self.mapper.deregisterMudEventHandler(self.event, self.handle)

	@abstractmethod
	def handle(self, data):
		pass
