#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import argparse
import logging
import sys
import traceback

# Mapper Modules:
import mapper.main
from mapper import INTERFACES, OUTPUT_FORMATS


try:
	from mpm_version import VERSION
except ImportError:
	VERSION = "%(prog)s: No version information available. This is normal when running from source."
finally:
	VERSION += f" (Python {'.'.join(str(i) for i in sys.version_info[:3])} {sys.version_info.releaselevel})"


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="The accessible Mume mapper.")
	parser.add_argument("-v", "--version", action="version", version=VERSION)
	parser.add_argument("-e", "--emulation", help="Start in emulation mode.", action="store_true")
	parser.add_argument("-i", "--interface", help="Select a user interface.", choices=INTERFACES, default="text")
	parser.add_argument(
		"-f",
		"--format",
		help="Select how data from the server is transformed before  being sent to the client.",
		choices=OUTPUT_FORMATS,
		default="normal",
	)
	parser.add_argument(
		"-lh", "--local-host", metavar="address", help="The local host address to bind to.", default="127.0.0.1"
	)
	parser.add_argument(
		"-lp", "--local-port", metavar="port", type=int, help="The local port to bind to.", default=4000
	)
	parser.add_argument(
		"-rh", "--remote-host", metavar="address", help="The remote host address to connect to.", default="mume.org"
	)
	parser.add_argument(
		"-rp", "--remote-port", metavar="port", type=int, help="The remote port to connect to.", default=4242
	)
	parser.add_argument(
		"-nssl",
		"--no-ssl",
		help="Disable encrypted communication between the local and remote hosts.",
		action="store_true",
	)
	parser.add_argument(
		"-ptlf",
		"--prompt-terminator-lf",
		help="Terminate game prompts with return-linefeed characters (IAC + GA is default).",
		action="store_true",
	)
	parser.add_argument("-gp", "--gag-prompts", help="Gag emulated prompts.", action="store_true")
	parser.add_argument(
		"-ff",
		"--find-format",
		help=(
			"The format string for controlling output of the find commands. "
			"Accepts the following placeholders in braces: "
			"{attribute}, {direction}, {clockPosition}, {distance}, {name}, {vnum}. "
			"Where {attribute} represents the attribute on which the search is performed."
		),
		default="{vnum}, {name}, {attribute}",
	)
	args = parser.parse_args()
	try:
		mapper.main.main(
			outputFormat=args.format,
			interface=args.interface if mapper.main.pyglet is not None else "text",
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
