# -*- mode: python -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Future Modules:
from __future__ import annotations

# Built-in Modules:
import glob
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from _hashlib import HASH
from contextlib import suppress
from typing import Dict, List, Match, Pattern, Tuple, Union

# Third-party Modules:
import PyInstaller.config
import speechlight
from PyInstaller.archive.pyz_crypto import PyiBlockCipher
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.datastruct import TOC

# Mapper Modules:
from mapper.utils import padList


APP_NAME: str = "Mapper Proxy"
APP_AUTHOR: str = "Nick Stockton"
APP_VERSION: str
APP_VERSION_TYPE: str
VERSION_REGEX: Pattern[str] = re.compile(r"^[vV]([\d]+\.[\d]+\.[\d]+)(\-\d+\-g[\da-f]+)$", re.IGNORECASE)
ORIG_DEST: str = os.path.realpath(os.path.expanduser(DISTPATH))  # type: ignore[name-defined] # NOQA: F821
isTag: bool = False
found_version: Union[str, None] = None
match: Union[Match[str], None]

if os.path.exists(
	os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "version.ignore"))
) and not os.path.isdir(os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "version.ignore"))):
	with open(
		os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "version.ignore")), "r", encoding="utf-8"
	) as f:
		match = VERSION_REGEX.search(f.read(30).strip().lower())
		if match is not None:
			APP_VERSION = match.group(1)
			if match.group(2).startswith("-0-g"):
				APP_VERSION_TYPE = ""
				isTag = True
			else:
				APP_VERSION_TYPE = match.group(2)
			found_version = "version file"
elif os.path.exists(os.path.normpath(os.path.join(ORIG_DEST, os.pardir, ".git"))) and os.path.isdir(
	os.path.normpath(os.path.join(ORIG_DEST, os.pardir, ".git"))
):
	with suppress(subprocess.CalledProcessError):
		match = VERSION_REGEX.search(
			subprocess.check_output("git describe --tags --always --long", shell=True)
			.decode("utf-8")
			.strip()
			.lower()
		)
		if match is not None:
			APP_VERSION = match.group(1)
			if match.group(2).startswith("-0-g"):
				APP_VERSION_TYPE = ""
				isTag = True
			else:
				APP_VERSION_TYPE = match.group(2)
			found_version = "latest Git tag"
if found_version:
	print(f"Using version info from {found_version}. ({APP_VERSION}{APP_VERSION_TYPE})")
else:
	APP_VERSION = "0.0.0"
	APP_VERSION_TYPE = ""
	print(f"No version information found. Using default. ({APP_VERSION}{APP_VERSION_TYPE})")
# APP_VERSION_CSV should be a string containing a comma separated list of numbers in the version.
# For example, "17, 4, 5, 0" if the version is 17.4.5.
APP_VERSION_CSV: str = ", ".join(padList(APP_VERSION.split("."), padding="0", count=4, fixed=True))
APP_DEST: str = os.path.normpath(
	os.path.join(
		ORIG_DEST,
		os.pardir,
		(APP_NAME if not isTag else f"{APP_NAME}_V{APP_VERSION}{APP_VERSION_TYPE}")
		.replace("-", "_")
		.replace(" ", "_"),
	)
)
ZIP_FILE: str
if isTag:
	ZIP_FILE = APP_DEST + ".zip"
else:
	ZIP_FILE = os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "MapperProxy.zip"))
VERSION_FILE: str = os.path.normpath(
	os.path.join(os.path.realpath(os.path.expanduser(tempfile.gettempdir())), "mpm_version.ignore")
)
PyInstaller.config.CONF["distpath"] = APP_DEST

excludes: List[str] = [
	"_gtkagg",
	"_tkagg",
	"bsddb",
	"curses",
	"pywin.debugger",
	"pywin.debugger.dbgcon",
	"pywin.dialogs",
	"tcl",
	"Tkconstants",
	"tkinter.constants",
	"Tkinter",
	"tkinter",
	"multiprocessing",
	"bz2",
	"lzma",
	"_testcapi",
	"pdbunittest",
	"difflib",
	"pyreadline",
	"optparse",
	"numpy",
	"PIL",
	"xml",
]

dll_excludes: TOC = TOC(  # type: ignore[no-any-unimported]
	[
		("api-ms-win-core-console-l1-1-0.dll", None, None),
		("api-ms-win-core-datetime-l1-1-0.dll", None, None),
		("api-ms-win-core-debug-l1-1-0.dll", None, None),
		("api-ms-win-core-errorhandling-l1-1-0.dll", None, None),
		("api-ms-win-core-file-l1-1-0.dll", None, None),
		("api-ms-win-core-file-l1-2-0.dll", None, None),
		("api-ms-win-core-file-l2-1-0.dll", None, None),
		("api-ms-win-core-handle-l1-1-0.dll", None, None),
		("api-ms-win-core-heap-l1-1-0.dll", None, None),
		("api-ms-win-core-interlocked-l1-1-0.dll", None, None),
		("api-ms-win-core-libraryloader-l1-1-0.dll", None, None),
		("api-ms-win-core-localization-l1-2-0.dll", None, None),
		("api-ms-win-core-memory-l1-1-0.dll", None, None),
		("api-ms-win-core-namedpipe-l1-1-0.dll", None, None),
		("api-ms-win-core-processenvironment-l1-1-0.dll", None, None),
		("api-ms-win-core-processthreads-l1-1-0.dll", None, None),
		("api-ms-win-core-processthreads-l1-1-1.dll", None, None),
		("api-ms-win-core-profile-l1-1-0.dll", None, None),
		("api-ms-win-core-rtlsupport-l1-1-0.dll", None, None),
		("api-ms-win-core-string-l1-1-0.dll", None, None),
		("api-ms-win-core-synch-l1-1-0.dll", None, None),
		("api-ms-win-core-synch-l1-2-0.dll", None, None),
		("api-ms-win-core-sysinfo-l1-1-0.dll", None, None),
		("api-ms-win-core-timezone-l1-1-0.dll", None, None),
		("api-ms-win-core-util-l1-1-0.dll", None, None),
		("api-ms-win-crt-conio-l1-1-0.dll", None, None),
		("api-ms-win-crt-convert-l1-1-0.dll", None, None),
		("api-ms-win-crt-environment-l1-1-0.dll", None, None),
		("api-ms-win-crt-filesystem-l1-1-0.dll", None, None),
		("api-ms-win-crt-heap-l1-1-0.dll", None, None),
		("api-ms-win-crt-locale-l1-1-0.dll", None, None),
		("api-ms-win-crt-math-l1-1-0.dll", None, None),
		("api-ms-win-crt-multibyte-l1-1-0.dll", None, None),
		("api-ms-win-crt-process-l1-1-0.dll", None, None),
		("api-ms-win-crt-runtime-l1-1-0.dll", None, None),
		("api-ms-win-crt-stdio-l1-1-0.dll", None, None),
		("api-ms-win-crt-string-l1-1-0.dll", None, None),
		("api-ms-win-crt-time-l1-1-0.dll", None, None),
		("api-ms-win-crt-utility-l1-1-0.dll", None, None),
		("tcl86t.dll", None, None),
		("tk86t.dll", None, None),
		("ucrtbase.dll", None, None),
		("mfc140u.dll", None, None),
	]
)

block_cipher: Union[PyiBlockCipher, None] = None  # type: ignore[no-any-unimported]

version_data: str = f"""
# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=({APP_VERSION_CSV}),
    prodvers=(1, 0, 0, 1),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'LFileDescript'),
        StringStruct(u'', u'{APP_NAME} V{APP_VERSION}{APP_VERSION_TYPE}'),
        StringStruct(u'FileVersion', u'{APP_VERSION}'),
        StringStruct(u'LegalCopyright', u'{APP_AUTHOR}'),
        StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
        StringStruct(u'ProductName', u'{APP_NAME}'),
        StringStruct(u'ProductVersion', u'{APP_VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

# Remove old dist directory and old version file.
shutil.rmtree(ORIG_DEST, ignore_errors=True)
shutil.rmtree(APP_DEST, ignore_errors=True)
if os.path.exists(ZIP_FILE) and not os.path.isdir(ZIP_FILE):
	os.remove(ZIP_FILE)
if os.path.exists(
	os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py"))
) and not os.path.isdir(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py"))):
	os.remove(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
shutil.rmtree(VERSION_FILE, ignore_errors=True)

with open(VERSION_FILE, "w", encoding="utf-8") as f:
	f.write(version_data)

with open(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")), "w", encoding="utf-8") as f:
	f.write(f'VERSION = "{APP_NAME} V{APP_VERSION}{APP_VERSION_TYPE}"')

a: Analysis = Analysis(  # type: ignore[no-any-unimported]
	["start.py"],
	pathex=[os.path.normpath(os.path.join(APP_DEST, os.pardir))],
	binaries=[],
	datas=[],
	hiddenimports=["certifi", "decimal", "uuid"],
	hookspath=[],
	runtime_hooks=[],
	excludes=excludes,
	win_no_prefer_redirects=False,
	win_private_assemblies=False,
	cipher=block_cipher,
	noarchive=False,
)

pyz: PYZ = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # type: ignore[no-any-unimported]

exe: EXE = EXE(  # type: ignore[no-any-unimported]
	pyz,
	a.scripts,
	[],
	exclude_binaries=True,
	name=APP_NAME,
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=False,  # Not using UPX for the moment, as it can raise false positives in some antivirus software.
	runtime_tmpdir=None,
	console=True,
	version=VERSION_FILE,
)

coll: COLLECT = COLLECT(  # type: ignore[no-any-unimported]
	exe,
	a.binaries - dll_excludes,
	a.zipfiles,
	a.datas,
	strip=False,
	upx=False,
	name="",
)

# Remove junk.
shutil.rmtree(ORIG_DEST, ignore_errors=True)
shutil.rmtree(os.path.normpath(os.path.join(APP_DEST, os.pardir, "__pycache__")), ignore_errors=True)
wp: str = os.path.realpath(os.path.expanduser(workpath))  # type: ignore[name-defined] # NOQA: F821
shutil.rmtree(wp, ignore_errors=True)
# The directory above workpath should now be empty.
# Using os.rmdir to remove it instead of shutil.rmtree for safety.
os.rmdir(os.path.normpath(os.path.join(wp, os.pardir)))
if os.path.exists(
	os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py"))
) and not os.path.isdir(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py"))):
	os.remove(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
shutil.rmtree(os.path.join(APP_DEST, "Include"), ignore_errors=True)
shutil.rmtree(os.path.join(APP_DEST, "lib2to3", "tests"), ignore_errors=True)

include_files: List[Tuple[List[str], str]] = [
	(
		[
			os.path.normpath(os.path.join(APP_DEST, os.pardir, "LICENSE.txt")),
			os.path.normpath(os.path.join(APP_DEST, os.pardir, "README.md")),
		],
		".",
	),
	(
		glob.glob(os.path.join(os.path.realpath(os.path.expanduser(speechlight.LIB_DIRECTORY)), "*.dll")),
		"speech_libs",
	),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "maps", "*.sample"))), "maps"),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "data", "*.sample"))), "data"),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "data", "*.schema"))), "data"),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "tiles", "*"))), "tiles"),
]

dest_dir: str
for files, destination in include_files:
	dest_dir = os.path.join(APP_DEST, destination)
	if not os.path.exists(dest_dir):
		os.makedirs(dest_dir)
	for src in files:
		if os.path.exists(src) and not os.path.isdir(src):
			shutil.copy(src, dest_dir)

print(f"Compressing the distribution to {ZIP_FILE}.")
shutil.make_archive(
	base_name=os.path.splitext(ZIP_FILE)[0],
	format="zip",
	root_dir=os.path.normpath(os.path.join(APP_DEST, os.pardir)),
	base_dir=os.path.basename(APP_DEST),
	owner=None,
	group=None,
)
shutil.rmtree(APP_DEST, ignore_errors=True)

print("Generating checksums.")
hashes: Dict[str, HASH] = {  # type: ignore[no-any-unimported]
	"sha256": hashlib.sha256(),
}
block_size: int = 2 ** 16
with open(ZIP_FILE, "rb") as zf:
	for block in iter(lambda: zf.read(block_size), b""):
		for _, hash in hashes.items():
			hash.update(block)
for hashtype, hash in hashes.items():
	with open(f"{ZIP_FILE}.{hashtype}", "w", encoding="utf-8") as f:
		f.write(f"{hash.hexdigest().lower()} *{os.path.basename(ZIP_FILE)}\n")

print("Done.")
