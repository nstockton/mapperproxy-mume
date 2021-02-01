#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import sys
import traceback

# Third-party Modules:
from tap import Tap

# Mapper Modules:
import mapper.main
from mapper import INTERFACES, OUTPUT_FORMATS


try:
	import pyglet  # type: ignore[import]
except ImportError:
	pyglet = None
	print("Unable to import Pyglet. GUI will be disabled.")


VERSION: str
try:
	import mpm_version  # type: ignore[import]
except ImportError:
	VERSION = "%(prog)s: No version information available. This is normal when running from source."
else:
	VERSION = mpm_version.VERSION
finally:
	VERSION += f" (Python {'.'.join(str(i) for i in sys.version_info[:3])} {sys.version_info.releaselevel})"


class ArgumentParser(Tap):
	emulation: bool = False
	"""Start in emulation mode."""
	interface: str = INTERFACES[0]
	"""Select a user interface."""
	format: str = OUTPUT_FORMATS[0]
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
		self.add_argument(
			"-v",
			"--version",
			help="Print the program version as well as the Python version.",
			action="version",
			version=VERSION,
		)
		self.add_argument("-e", "--emulation")
		self.add_argument("-i", "--interface", choices=INTERFACES)
		self.add_argument("-f", "--format", choices=OUTPUT_FORMATS)
		self.add_argument("-lh", "--local_host", metavar="address")
		self.add_argument("-lp", "--local_port", metavar="port")
		self.add_argument("-rh", "--remote_host", metavar="address")
		self.add_argument("-rp", "--remote_port", metavar="port")
		self.add_argument("-nssl", "--no_ssl")
		self.add_argument("-ptlf", "--prompt_terminator_lf")
		self.add_argument("-gp", "--gag_prompts")
		self.add_argument("-ff", "--find_format", metavar="text")


if __name__ == "__main__":
	parser: ArgumentParser = ArgumentParser(description="The accessible Mume mapper.")
	args: ArgumentParser = parser.parse_args()
	try:
		mapper.main.main(
			outputFormat=args.format,
			interface=args.interface if pyglet is not None else "text",
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
		traceback.print_exception(*sys.exc_info())
		logging.exception("OOPS!")
	finally:
		logging.info("Shutting down.")
		logging.shutdown()
