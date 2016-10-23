#!/usr/bin/env python

import logging
import mapper
try:
	import mapper.emulation
	if __name__ == "__main__":
		mapper.emulation.main()
except:
	import sys, traceback
	traceback.print_exception(*sys.exc_info())
	logging.exception('OOPSE!')
finally:
	logging.info('Shutting down.')
	logging.shutdown()
