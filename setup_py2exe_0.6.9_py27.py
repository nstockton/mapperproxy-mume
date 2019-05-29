# This script should be considered deprecated. Don't use unless you know what you are doing.
import glob
from distutils.core import setup
import os.path
import shutil
import sys

import py2exe

import speechlight

APP_NAME = "Mapper Proxy"
APP_AUTHOR = "Nick Stockton"
APP_VERSION = "2.2"

# Remove old build and dist directories
shutil.rmtree("build", ignore_errors=True)
shutil.rmtree("dist", ignore_errors=True)

# If run without arguments, build executables in quiet mode.
if len(sys.argv) == 1:
	sys.argv.append("py2exe")
	sys.argv.append("-q")


class Target(object):
	def __init__(self, **kw):
		self.__dict__.update(kw)
		# For the versioninfo resources
		self.version = APP_VERSION
		self.company_name = ""
		self.copyright = APP_AUTHOR
		self.name = APP_NAME

program = Target(description="%s V%s" % (APP_NAME, APP_VERSION), script="start.py", dest_base=APP_NAME)

excludes = [
	"_gtkagg",
	"_tkagg",
	"bsddb",
	"curses",
	"email",
	"pywin.debugger",
	"pywin.debugger.dbgcon",
	"pywin.dialogs",
	"tcl",
	"Tkconstants",
	"Tkinter",
	"pdbunittest",
	"difflib",
	"pyreadline",
	"optparse",
	"pickle",
	"calendar"
]

dll_excludes = [
	"libgdk-win32-2.0-0.dll",
	"libgobject-2.0-0.dll",
	"tcl84.dll",
	"tk84.dll",
	"MSVCP90.dll",
	"mswsock.dll",
	"powrprof.dll",
	"python23.dll",
	"_sre.pyd",
	"_winreg.pyd",
	"unicodedata.pyd",
	"zlib.pyd",
	"wxc.pyd",
	"wxmsw24uh.dll",
	"w9xpopen.exe"
]

packages = [
	"encodings.ascii",
	"encodings.utf_8",
	"encodings.latin_1"
]

setup_options = {
	"py2exe": {
		"dist_dir": "%s V%s" % (APP_NAME, APP_VERSION),
		"bundle_files": 1,
		"ascii": False,
		"compressed": True,
		"optimize": 2,
		"excludes": excludes,
		"dll_excludes": dll_excludes,
		"packages": packages
	}
}

setup(options=setup_options, zipfile=None, console=[program], data_files=[(".", ["./cacert.pem"]), ("speech_libs", glob.glob(os.path.join(speechlight.where(), "*.dll"))), ("maps", glob.glob("maps\\*.sample")), ("data", glob.glob("data\\*.sample"))])

# Remove the build folder since we no longer need it.
shutil.rmtree("build", ignore_errors=True)
