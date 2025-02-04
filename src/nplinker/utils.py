# Copyright 2021 The NPLinker Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
import bz2
import csv
import gzip
import hashlib
import lzma
import math
import os
import os.path
import sys
import tarfile
import zipfile
from os import PathLike
from pathlib import Path
from typing import IO
from typing import Callable
import httpx
from tqdm import tqdm


# CG: it's only used by metabolomics, should move it there
# code to normalise peaks for spectral matching ("rosetta stone" stuff)
def sqrt_normalise(peaks):
    temp = []
    total = 0.0
    for mz, intensity in peaks:
        temp.append((mz, math.sqrt(intensity)))
        total += intensity
    norm_facc = math.sqrt(total)
    normalised_peaks = []
    for mz, intensity in temp:
        normalised_peaks.append((mz, intensity / norm_facc))
    return normalised_peaks


def find_delimiter(file: str | PathLike) -> str:
    """Detect the delimiter for the given tabular file.

    Args:
        file(str | PathLike): Path to tabular file.

    Returns:
        str: Detected delimiter character.

    Examples:
        >>> delim = find_delimiter("~/table.csv")
    """
    sniffer = csv.Sniffer()
    with open(file, mode="rt", encoding="utf-8") as fp:
        delimiter = sniffer.sniff(fp.read(5000)).delimiter
    return delimiter


def get_headers(file: str | PathLike) -> list[str]:
    """Read headers from the given tabular file.

    Args:
        file(str): Path to the file to read the header from.

    Returns:
        list[str]: list of column names from the header.
    """
    with open(file) as f:
        headers = f.readline().strip()
        dl = find_delimiter(file)
        return headers.split(dl)


def is_file_format(file: str | PathLike, format: str = "tsv") -> bool:
    """Check if the file is in the given format.

    Args:
        file(str): Path to the file to check.
        format(str): The format to check for, either "tsv" or "csv".

    Returns:
        bool: True if the file is in the given format, False otherwise.
    """
    try:
        with open(file, "rt") as f:
            if format == "tsv":
                reader = csv.reader(f, delimiter="\t")
            elif format == "csv":
                reader = csv.reader(f, delimiter=",")
            else:
                raise ValueError(f"Unknown format '{format}'.")
            for _ in reader:
                pass
        return True
    except csv.Error:
        return False


# Functions below are adapted from torchvision library,
# see: https://github.com/pytorch/vision/blob/main/torchvision/datasets/utils.py.
#
# BSD 3-Clause License
# Copyright (c) Soumith Chintala 2016
# You may obtain a copy of the License at
#    https://github.com/pytorch/vision/blob/main/LICENSE


def calculate_md5(fpath: str | PathLike, chunk_size: int = 1024 * 1024) -> str:
    if sys.version_info >= (3, 9):
        md5 = hashlib.md5(usedforsecurity=False)
    else:
        md5 = hashlib.md5()
    with open(fpath, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


def check_md5(fpath: str | PathLike, md5: str) -> bool:
    return md5 == calculate_md5(fpath)


def check_integrity(fpath: str | PathLike, md5: str | None = None) -> bool:
    if not os.path.isfile(fpath):
        return False
    if md5 is None:
        return True
    return check_md5(fpath, md5)


def download_url(
    url: str,
    root: str | PathLike,
    filename: str | None = None,
    md5: str | None = None,
    http_method: str = "GET",
    allow_http_redirect: bool = True,
) -> None:
    """Download a file from a url and place it in root.

    Args:
        url (str): URL to download file from
        root (str): Directory to place downloaded file in
        filename (str, optional): Name to save the file under. If None, use the
            basename of the URL.
        md5 (str, optional): MD5 checksum of the download. If None, do not check.
        http_method (str, optional): HTTP request method, e.g. "GET", "POST".
            Defaults to "GET".
        allow_http_redirect (bool, optional): If true, enable following redirects
         for all HTTP ("http:") methods.
    """
    root = Path(root).expanduser()
    if not filename:
        filename = Path(url).name
    fpath = root / filename

    Path.mkdir(root, exist_ok=True)

    # check if file is already present locally
    if check_integrity(fpath, md5):
        print("Using downloaded and verified file: " + str(fpath))
        return

    # download the file
    with open(fpath, "wb") as fh:
        with httpx.stream(http_method, url, follow_redirects=allow_http_redirect) as response:
            if not response.is_success:
                fpath.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Failed to download url {url} with status code {response.status_code}"
                )
            total = int(response.headers.get("Content-Length", 0))
            with tqdm(total=total, unit_scale=True, unit_divisor=1024, unit="B") as progress:
                num_bytes_downloaded = response.num_bytes_downloaded
                for chunk in response.iter_bytes():
                    fh.write(chunk)
                    progress.update(response.num_bytes_downloaded - num_bytes_downloaded)
                    num_bytes_downloaded = response.num_bytes_downloaded

    # check integrity of downloaded file
    if not check_integrity(fpath, md5):
        raise RuntimeError("File not found or corrupted, or md5 validation failed.")


def list_dirs(root: str | PathLike, keep_parent: bool = True) -> list[str]:
    """List all directories at a given root.

    Args:
        root (str or Path): Path to directory whose folders need to be listed
        prefix (bool, optional): If true, prepends the path to each result, otherwise
            only returns the name of the directories found
    """
    root = Path(root).expanduser()
    directories = [str(p) for p in root.iterdir() if p.is_dir()]
    if not keep_parent:
        directories = [os.path.basename(d) for d in directories]
    return directories


def list_files(
    root: str | PathLike,
    prefix: str | tuple[str, ...] = "",
    suffix: str | tuple[str, ...] = "",
    keep_parent: bool = True,
) -> list[str]:
    """List all files at a given root.

    Args:
        root (str or Path): Path to directory whose files need to be listed
        prefix (str or tuple): Prefix of the file names to match,
            Defaults to empty string '""'.
        suffix (str or tuple): Suffix of the files to match, e.g. ".png" or
            (".jpg", ".png").
            Defaults to empty string '""'.
        keep_parent (bool, optional): If true, prepends the parent path to each
            result, otherwise only returns the name of the files found.
            Defaults to False.
    """
    root = Path(root).expanduser()
    files = [
        str(p)
        for p in root.iterdir()
        if p.is_file() and p.name.startswith(prefix) and p.name.endswith(suffix)
    ]

    if not keep_parent:
        files = [os.path.basename(f) for f in files]

    return files


def _extract_tar(
    from_path: str | PathLike,
    to_path: str | PathLike,
    members: list[tarfile.TarInfo] | None,
    compression: str | None,
) -> None:
    with tarfile.open(from_path, f"r:{compression[1:]}" if compression else "r") as tar:
        tar.extractall(to_path, members)


_ZIP_COMPRESSION_MAP: dict[str, int] = {
    ".bz2": zipfile.ZIP_BZIP2,
    ".xz": zipfile.ZIP_LZMA,
}


def _extract_zip(
    from_path: str | PathLike,
    to_path: str | PathLike,
    members: list[str | zipfile.ZipInfo] | None,
    compression: str | None,
) -> None:
    with zipfile.ZipFile(
        from_path,
        "r",
        compression=_ZIP_COMPRESSION_MAP[compression] if compression else zipfile.ZIP_STORED,
    ) as zf:
        zf.extractall(to_path, members)


_ARCHIVE_EXTRACTORS: dict[str, Callable[[str, str, list | None, str | None], None]] = {
    ".tar": _extract_tar,
    ".zip": _extract_zip,
}
_COMPRESSED_FILE_OPENERS: dict[str, Callable[..., IO]] = {
    ".bz2": bz2.open,
    ".gz": gzip.open,
    ".xz": lzma.open,
}
_FILE_TYPE_ALIASES: dict[str, tuple[str | None, str | None]] = {
    ".tbz": (".tar", ".bz2"),
    ".tbz2": (".tar", ".bz2"),
    ".tgz": (".tar", ".gz"),
}


def _detect_file_type(file: str | Path) -> tuple[str, str | None, str | None]:
    """Detect the archive type and/or compression of a file.

    Args:
        file (str, Path): the filename

    Returns:
        (tuple): tuple of suffix, archive type, and compression

    Raises:
        RuntimeError: if file has no suffix or suffix is not supported
    """
    suffixes = Path(file).suffixes
    if not suffixes:
        raise RuntimeError(
            f"File '{file}' has no suffixes that could be used to detect the archive type and compression."
        )
    suffix = suffixes[-1]

    # check if the suffix is a known alias
    if suffix in _FILE_TYPE_ALIASES:
        return (suffix, *_FILE_TYPE_ALIASES[suffix])

    # check if the suffix is an archive type
    if suffix in _ARCHIVE_EXTRACTORS:
        return suffix, suffix, None

    # check if the suffix is a compression
    if suffix in _COMPRESSED_FILE_OPENERS:
        # check for suffix hierarchy
        if len(suffixes) > 1:
            suffix2 = suffixes[-2]

            # check if the suffix2 is an archive type
            if suffix2 in _ARCHIVE_EXTRACTORS:
                return suffix2 + suffix, suffix2, suffix

        return suffix, None, suffix

    valid_suffixes = sorted(
        set(_FILE_TYPE_ALIASES) | set(_ARCHIVE_EXTRACTORS) | set(_COMPRESSED_FILE_OPENERS)
    )
    raise RuntimeError(
        f"Unknown compression or archive type: '{suffix}'.\nKnown suffixes are: '{valid_suffixes}'."
    )


def _decompress(
    from_path: Path | str, to_path: Path | str | None = None, remove_finished: bool = False
) -> str:
    r"""Decompress a file.

    The compression is automatically detected from the file name.

    Args:
        from_path (str or Path): Path to the file to be decompressed.
        to_path (str Path): Path to the decompressed file. If omitted, `from_path` without compression extension is used.
        remove_finished (bool): If `True`, remove the file after the extraction.

    Returns:
        (str): Path to the decompressed file.
    """
    suffix, archive_type, compression = _detect_file_type(from_path)
    if not compression:
        raise RuntimeError(f"Couldn't detect a compression from suffix {suffix}.")

    if to_path is None:
        to_path = str(from_path).replace(suffix, archive_type if archive_type is not None else "")

    compressed_file_opener = _COMPRESSED_FILE_OPENERS[compression]

    with compressed_file_opener(from_path, "rb") as rfh, open(to_path, "wb") as wfh:
        wfh.write(rfh.read())

    if remove_finished:
        os.remove(from_path)

    return str(to_path)


def extract_archive(
    from_path: str | PathLike,
    extract_root: str | PathLike | None = None,
    members: list | None = None,
    remove_finished: bool = False,
) -> str:
    """Extract an archive.

    The archive type and a possible compression is automatically detected from
    the file name. If the file is compressed but not an archive the call is
    dispatched to :func:`decompress`.

    Args:
        from_path: Path to the file to be extracted.
        extract_root: Path to the directory the file will be extracted to.
            If omitted, the directory of the archive file is used.
        members: Optional selection of members to extract. If not specified,
            all members are extracted.
            Memers must be a subset of the list returned by
            - `zipfile.ZipFile.namelist()` or a list of strings for zip file
            - `tarfile.TarFile.getmembers()` for tar file
        remove_finished: If `True`, remove the file after the extraction.

    Returns:
        (str): Path to the directory the file was extracted to.
    """
    from_path = Path(from_path)

    if extract_root is None:
        extract_root = from_path.parent
    else:
        extract_root = Path(extract_root)

    suffix, archive_type, compression = _detect_file_type(from_path)
    if not archive_type:
        return _decompress(
            from_path,
            extract_root / from_path.name.replace(suffix, ""),
            remove_finished=remove_finished,
        )

    extractor = _ARCHIVE_EXTRACTORS[archive_type]

    extractor(str(from_path), str(extract_root), members, compression)
    if remove_finished:
        from_path.unlink()

    return str(extract_root)


def download_and_extract_archive(
    url: str,
    download_root: str | PathLike,
    extract_root: str | Path | None = None,
    filename: str | None = None,
    md5: str | None = None,
    remove_finished: bool = False,
) -> None:
    """Download a file from url and extract it.

       This method is a wrapper of `download_url` and `extract_archive` methods.

    Args:
        url (str): URL to download file from
        download_root (str or Path): Path to the directory to place downloaded
            file in
        extract_root (str or Path, optional): Path to the directory the file
            will be extracted to. If omitted, the `download_root` is used.
        filename (str, optional): Name to save the downloaded file under.
            If None, use the basename of the URL
        md5 (str, optional): MD5 checksum of the download. If None, do not check
        remove_finished (bool, optional): If `True`, remove the downloaded file
             after the extraction. Defaults to False.
    """
    download_root = Path(download_root).expanduser()
    if extract_root is None:
        extract_root = download_root
    else:
        extract_root = Path(extract_root)
    if not filename:
        filename = Path(url).name

    download_url(url, download_root, filename, md5)

    archive = download_root / filename
    print(f"Extracting {archive} to {extract_root}")
    extract_archive(archive, extract_root, remove_finished=remove_finished)
