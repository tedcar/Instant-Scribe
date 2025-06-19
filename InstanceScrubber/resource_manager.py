"""Resource helper utilities.

This module centralises the logic for locating non-Python *data files* that
ship with Instant Scribe.  In the normal development environment (running the
source checkout directly) resources live on disk relative to the repository
root.  Once the application is packaged with **PyInstaller** the files are
embedded inside the frozen bundle and are unpacked into a temporary directory
exposed via the :pydataattr:`sys._MEIPASS` attribute.

The :func:`resource_path` helper below hides these differences by returning an
*absolute* :class:`~pathlib.Path` for an input path that is **always** valid in
both scenarios:

>>> resource_path("assets/icon.ico")
PosixPath('/abs/path/to/assets/icon.ico')

If you need the *directory* containing resources use::

    resource_path("")  # returns the bundle / repo root as Path
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Union, AnyStr

__all__ = ["resource_path"]

_PathLike = Union[str, Path, 'os.PathLike[AnyStr]']  # noqa: UP035 – Python < 3.12 compatibility


def _determine_base_path() -> Path:
    """Return the directory that forms the root for bundled data files.

    * In **frozen** mode (PyInstaller, cx_Freeze, etc.) we rely on the private
      :pydataattr:`sys._MEIPASS` path exposed by the bootloader.
    * Otherwise we assume we are running from an editable source checkout and
      take the parent directory of this *resource_manager.py* file which
      corresponds to the repository root (`.../Instant Scribe`).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # noinspection PyProtectedMember
        return Path(sys._MEIPASS)  # type: ignore[arg-type] – provided by bootloader

    # Development / unit-test scenario – repo root = <package_parent>
    return Path(__file__).resolve().parent.parent


def resource_path(relative_path: _PathLike) -> Path:
    """Resolve *relative_path* against the application bundle root.

    The returned :class:`~pathlib.Path` is **always absolute** and therefore
    safe to pass directly to file-handling APIs without worrying about the
    current working directory.

    Parameters
    ----------
    relative_path:
        Path to the desired resource **relative** to the bundle root – for
        example ``"assets/icon.ico"``.  An empty string returns the root
        directory itself.

    Examples
    --------
    >>> # Fetch icon while running from source checkout
    >>> icon = resource_path("assets/icon.ico")
    >>> icon.is_file()
    True
    """

    base_path = _determine_base_path()
    return (base_path / Path(relative_path)).resolve()