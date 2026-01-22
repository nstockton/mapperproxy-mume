# -*- mode: python -*-
# Copyright (c) 2025 Nick Stockton and contributors
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import hashlib
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

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
APP_VERSION_MATCH: re.Match[str] | None = re.search(
	r"^[vV]?(?P<version>\d+\.\d+\.\d+)(?P<version_type>.*)$", MAPPER_VERSION.strip(), flags=re.UNICODE
)
APP_VERSION: str
APP_VERSION_TYPE: str
if APP_VERSION_MATCH is not None:
	APP_VERSION, APP_VERSION_TYPE = APP_VERSION_MATCH.groups()
else:
	APP_VERSION = "0.0.0"
	APP_VERSION_TYPE = ""
ORIG_DEST_PATH: Path = Path(DISTPATH).expanduser().resolve()  # type: ignore[name-defined] # NOQA: F821
RUN_FILE_PATH: Path = Path("run_mapper_proxy.py")
isTag: bool = not APP_VERSION_TYPE


print(f"Using version {APP_VERSION}{APP_VERSION_TYPE}.")


# APP_VERSION_CSV should be a string containing a comma separated list of numbers in the version.
# For example, "17, 4, 5, 0" if the version is 17.4.5.
APP_VERSION_CSV: str = ", ".join(pad_list(APP_VERSION.split("."), padding="0", count=4, fixed=True))
APP_DEST_NAME: str = f"{APP_NAME}_V{APP_VERSION}{APP_VERSION_TYPE}" if isTag else APP_NAME
APP_DEST_PATH: Path = ORIG_DEST_PATH.parent / APP_DEST_NAME.replace("-", "_").replace(" ", "_")
ZIP_FILE_PATH: Path
if isTag:
	ZIP_FILE_PATH = APP_DEST_PATH.with_name(f"{APP_DEST_PATH.name}.zip")
else:
	ZIP_FILE_PATH = ORIG_DEST_PATH.parent / "MapperProxy.zip"
VERSION_FILE_PATH: Path = Path(tempfile.gettempdir()).expanduser().resolve() / "mpm_version.ignore"
PyInstaller.config.CONF["distpath"] = str(APP_DEST_PATH)

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

block_cipher: Any | None = None

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
shutil.rmtree(ORIG_DEST_PATH, ignore_errors=True)
shutil.rmtree(APP_DEST_PATH, ignore_errors=True)
if RUN_FILE_PATH.is_file():
	RUN_FILE_PATH.unlink(missing_ok=True)
if ZIP_FILE_PATH.is_file():
	ZIP_FILE_PATH.unlink(missing_ok=True)
shutil.rmtree(VERSION_FILE_PATH, ignore_errors=True)

VERSION_FILE_PATH.write_text(version_data, encoding="utf-8")

run_data: str = """
from mapper.main import run

if __name__ == "__main__":
	run()
""".lstrip()
RUN_FILE_PATH.write_text(run_data, encoding="utf-8")

a: Analysis = Analysis(
	[str(RUN_FILE_PATH)],
	pathex=[str(APP_DEST_PATH.parent)],
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
	version=str(VERSION_FILE_PATH),
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
shutil.rmtree(ORIG_DEST_PATH, ignore_errors=True)
shutil.rmtree(APP_DEST_PATH.parent / "__pycache__", ignore_errors=True)
wp: Path = Path(workpath).expanduser().resolve()  # type: ignore[name-defined] # NOQA: F821
shutil.rmtree(wp, ignore_errors=True)
# The directory above workpath should now be empty.
# Using Path.rmdir to remove it instead of shutil.rmtree for safety.
wp.parent.rmdir()
shutil.rmtree(APP_DEST_PATH / "Include", ignore_errors=True)
shutil.rmtree(APP_DEST_PATH / "lib2to3" / "tests", ignore_errors=True)

include_files: list[tuple[list[Path], Path]] = [
	(
		[
			APP_DEST_PATH.parent / "LICENSE.txt",
			APP_DEST_PATH.parent / "README.md",
		],
		Path(),
	),
	(
		list(Path(speechlight.LIB_DIRECTORY).expanduser().resolve().glob("*.dll")),
		Path("speech_libs"),
	),
	(
		[
			*(APP_DEST_PATH.parent / "src" / "mapper_data").glob("*.sample"),
			*(APP_DEST_PATH.parent / "src" / "mapper_data").glob("*.schema"),
		],
		Path("mapper_data"),
	),
	(
		list((APP_DEST_PATH.parent / "src" / "mapper_data" / "tiles").glob("*")),
		Path("mapper_data/tiles"),
	),
]

for files, destination in include_files:
	dest_dir: Path = APP_DEST_PATH / destination
	if not dest_dir.exists():
		dest_dir.mkdir()
	for src in files:
		if src.is_file():
			shutil.copy(src, dest_dir)

# In order to insure reproducible zip files, the items inside the zip should have a fixed time.
# Inside zip files, dates and times are stored in local time in 16 bits, not UTC.
# Oldest allowed date for zip is 1980-01-01 0:00.
zip_epoch: int = int(datetime(1980, 1, 1, 0, 0, 0, tzinfo=None).timestamp())  # NOQA: DTZ001
source_epoch: int = int(os.getenv("SOURCE_DATE_EPOCH", zip_epoch))
os.utime(APP_DEST_PATH.resolve(), times=(source_epoch, source_epoch))
for child in APP_DEST_PATH.rglob("*"):
	os.utime(child.resolve(), times=(source_epoch, source_epoch))

print(f"Compressing the distribution to {ZIP_FILE_PATH}.")
shutil.make_archive(
	base_name=str(ZIP_FILE_PATH.with_suffix("")),
	format="zip",
	root_dir=APP_DEST_PATH.parent,
	base_dir=APP_DEST_PATH.name,
	owner=None,
	group=None,
)

if RUN_FILE_PATH.is_file():
	RUN_FILE_PATH.unlink(missing_ok=True)
shutil.rmtree(APP_DEST_PATH, ignore_errors=True)

print("Generating checksums.")
hashes: dict[str, hashlib._Hash] = {
	"sha256": hashlib.sha256(),
}
block_size: int = 2**16
with ZIP_FILE_PATH.open("rb") as zf:
	for block in iter(lambda: zf.read(block_size), b""):
		for func in hashes.values():
			func.update(block)
for hashtype, func in hashes.items():
	checksum_file_path = ZIP_FILE_PATH.with_suffix(f"{ZIP_FILE_PATH.suffix}.{hashtype}")
	checksum_file_path.write_text(f"{func.hexdigest().lower()} *{ZIP_FILE_PATH.name}\n", encoding="utf-8")

print("Done.")
