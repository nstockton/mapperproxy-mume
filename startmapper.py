#!/usr/bin/env python

import logging
import sys

import mapper.main

if __name__ == "__main__":
	if sys.argv:
		outputFormat = sys.argv[-1].strip().lower()
		if outputFormat not in ("normal", "tintin", "raw"):
			outputFormat = "normal"
	else:
		outputFormat = "normal"
	try:
		mapper.main.main(outputFormat)
	except:
		import sys, traceback
		traceback.print_exception(*sys.exc_info())
		logging.exception('OOPSE!')
	finally:
		logging.info('Shutting down.')
		logging.shutdown()
