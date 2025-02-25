# -*- mode: python -*-
# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import glob
import hashlib
import os
import pathlib
import re
import shutil
import tempfile
from datetime import datetime
from typing import Any, Union

# Third-party Modules:
import PyInstaller.config
import speechlight
from knickknacks.iterables import pad_list
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.datastruct import TOC

# Mapper Modules:
from mapper import __version__ as MAPPER_VERSION


APP_NAME: str = "Mapper Proxy"
APP_AUTHOR: str = "Nick Stockton"
APP_VERSION_MATCH: Union[re.Match[str], None] = re.search(
	r"^[vV]?(?P<version>\d+\.\d+\.\d+)(?P<version_type>.*)$", MAPPER_VERSION.strip(), flags=re.UNICODE
)
APP_VERSION: str
APP_VERSION_TYPE: str
if APP_VERSION_MATCH is not None:
	APP_VERSION, APP_VERSION_TYPE = APP_VERSION_MATCH.groups()
else:
	APP_VERSION = "0.0.0"
	APP_VERSION_TYPE = ""
ORIG_DEST: str = os.path.realpath(os.path.expanduser(DISTPATH))  # type: ignore[name-defined] # NOQA: F821
RUN_FILE: str = "run_mapper_proxy.py"
isTag: bool = not APP_VERSION_TYPE


print(f"Using version {APP_VERSION}{APP_VERSION_TYPE}.")


# APP_VERSION_CSV should be a string containing a comma separated list of numbers in the version.
# For example, "17, 4, 5, 0" if the version is 17.4.5.
APP_VERSION_CSV: str = ", ".join(pad_list(APP_VERSION.split("."), padding="0", count=4, fixed=True))
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

excludes: list[str] = [
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

dll_excludes: TOC = TOC(
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

block_cipher: Union[Any, None] = None

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

# Remove old build files.
shutil.rmtree(ORIG_DEST, ignore_errors=True)
shutil.rmtree(APP_DEST, ignore_errors=True)
if os.path.exists(RUN_FILE) and not os.path.isdir(RUN_FILE):
	os.remove(RUN_FILE)
if os.path.exists(ZIP_FILE) and not os.path.isdir(ZIP_FILE):
	os.remove(ZIP_FILE)
shutil.rmtree(VERSION_FILE, ignore_errors=True)

with open(VERSION_FILE, "w", encoding="utf-8") as f:
	f.write(version_data)

run_data: str = """
from __future__ import annotations

from mapper.main import run

if __name__ == "__main__":
	run()
""".lstrip()
with open(RUN_FILE, "w", encoding="utf-8") as f:
	f.write(run_data)

a: Analysis = Analysis(
	[RUN_FILE],
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

pyz: PYZ = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe: EXE = EXE(
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

coll: COLLECT = COLLECT(
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
shutil.rmtree(os.path.join(APP_DEST, "Include"), ignore_errors=True)
shutil.rmtree(os.path.join(APP_DEST, "lib2to3", "tests"), ignore_errors=True)

include_files: list[tuple[list[str], str]] = [
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
	(
		glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "src", "mapper_data", "*.sample"))),
		"mapper_data",
	),
	(
		glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "src", "mapper_data", "*.schema"))),
		"mapper_data",
	),
	(
		glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "src", "mapper_data", "tiles", "*"))),
		"mapper_data/tiles",
	),
]

dest_dir: str
for files, destination in include_files:
	dest_dir = os.path.join(APP_DEST, destination)
	if not os.path.exists(dest_dir):
		os.makedirs(dest_dir)
	for src in files:
		if os.path.exists(src) and not os.path.isdir(src):
			shutil.copy(src, dest_dir)

# In order to insure reproducible zip files, the items inside the zip should have a fixed time.
# Inside zip files, dates and times are stored in local time in 16 bits, not UTC.
# Oldest allowed date for zip is 1980-01-01 0:00.
zip_epoch: int = int(datetime(1980, 1, 1, 0, 0, 0, tzinfo=None).timestamp())  # NOQA: DTZ001
source_epoch: int = int(os.getenv("SOURCE_DATE_EPOCH", zip_epoch))
pdest = pathlib.Path(APP_DEST)
os.utime(pdest.resolve(), times=(source_epoch, source_epoch))
for child in pdest.rglob("*"):
	os.utime(child.resolve(), times=(source_epoch, source_epoch))

print(f"Compressing the distribution to {ZIP_FILE}.")
shutil.make_archive(
	base_name=os.path.splitext(ZIP_FILE)[0],
	format="zip",
	root_dir=os.path.normpath(os.path.join(APP_DEST, os.pardir)),
	base_dir=os.path.basename(APP_DEST),
	owner=None,
	group=None,
)

if os.path.exists(RUN_FILE) and not os.path.isdir(RUN_FILE):
	os.remove(RUN_FILE)
shutil.rmtree(APP_DEST, ignore_errors=True)

print("Generating checksums.")
hashes: dict[str, hashlib._Hash] = {
	"sha256": hashlib.sha256(),
}
block_size: int = 2**16
with open(ZIP_FILE, "rb") as zf:
	for block in iter(lambda: zf.read(block_size), b""):
		for func in hashes.values():
			func.update(block)
for hashtype, func in hashes.items():
	with open(f"{ZIP_FILE}.{hashtype}", "w", encoding="utf-8") as f:
		f.write(f"{func.hexdigest().lower()} *{os.path.basename(ZIP_FILE)}\n")

print("Done.")
