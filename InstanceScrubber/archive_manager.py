from __future__ import annotations

"""Session archive manager – fulfils *DEV_TASKS.md – Task 13* requirements.

Responsibilities
----------------
1. Create uniquely named *session* folders using the pattern ``[n]_[YYYY-MM-DD_HH-MM-SS]``.
2. Store the original ``recording.wav`` file inside the session folder.
3. Persist transcription text in a ``.txt`` file whose name is derived from the *first seven words*
   of the transcription (spaces → underscores).  Collisions are handled by appending ``_1``, ``_2`` ….

The implementation purposefully avoids external dependencies so that unit-tests can exercise the
full code-path on any CI runner.
"""

from pathlib import Path
from datetime import datetime
import logging
import os
import re
import shutil
from typing import Final

__all__ = [
    "ArchiveManager",
]


class ArchiveManager:  # pylint: disable=too-few-public-methods
    """High-level helper for persisting finished recordings to disk."""

    _TIMESTAMP_FMT: Final[str] = "%Y-%m-%d_%H-%M-%S"
    _SESSION_REGEX: Final[re.Pattern[str]] = re.compile(r"^(\d+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")
    _MAX_WORDS: Final[int] = 7

    # ..................................................................
    def __init__(self, *, base_dir: Path | str | None = None, config_manager=None) -> None:  # noqa: D401
        if base_dir is None:
            if config_manager is not None:
                # ConfigManager may contain Windows-style env vars (e.g. %USERNAME%). Expand them.
                raw = str(config_manager.get("archive_root", ""))
                base_dir = Path(os.path.expandvars(raw)) if raw else Path.home() / "Instant Scribe" / "archive"
            else:
                base_dir = Path.home() / "Instant Scribe" / "archive"
        self.base_dir: Path = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._log = logging.getLogger(self.__class__.__name__)
        self._log.debug("Archive root set to %s", self.base_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def archive(self, *, wav_path: Path | str, transcription: str) -> Path:  # noqa: D401 – imperative API
        """Archive *wav_path* and *transcription*, returning the session folder *Path*."""
        wav_path = Path(wav_path)
        if not wav_path.is_file():
            raise FileNotFoundError(f"Recording file not found: {wav_path}")

        session_dir = self._create_session_dir()

        # 1. Copy / move original WAV file
        target_wav = session_dir / "recording.wav"
        shutil.copy2(wav_path, target_wav)

        # 2. Persist transcription text
        txt_path = session_dir / self._derive_txt_filename(transcription, session_dir)
        txt_path.write_text(transcription, encoding="utf-8", errors="surrogatepass")

        self._log.info("Archived session at %s", session_dir)
        return session_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_session_dir(self) -> Path:
        """Return a newly created session directory following the naming convention."""
        next_idx = self._next_session_index()
        timestamp = datetime.now().strftime(self._TIMESTAMP_FMT)
        dir_name = f"{next_idx}_{timestamp}"
        session_dir = self.base_dir / dir_name
        session_dir.mkdir(parents=True, exist_ok=False)
        return session_dir

    # ..................................................................
    def _next_session_index(self) -> int:
        """Compute the next *n* by inspecting existing session folders."""
        max_idx = 0
        for entry in self.base_dir.iterdir():
            if not entry.is_dir():
                continue
            match = self._SESSION_REGEX.match(entry.name)
            if match:
                try:
                    idx = int(match.group(1))
                    max_idx = max(max_idx, idx)
                except ValueError:
                    continue
        return max_idx + 1

    # ..................................................................
    @classmethod
    def _sanitize_word(cls, word: str) -> str:
        """Return **word** stripped of filesystem-hostile characters."""
        # Allow unicode letters, numbers, dash and underscore. Replace others with nothing.
        return re.sub(r"[^\w\-]", "", word, flags=re.UNICODE)

    def _derive_txt_filename(self, transcription: str, session_dir: Path) -> str:
        """Generate a unique filename for the transcription within *session_dir*."""
        words = transcription.strip().split()
        first_words = words[: self._MAX_WORDS]
        if not first_words:
            first_words = ["empty"]
        sanitized = [self._sanitize_word(w) or "_" for w in first_words]
        base_name = "_".join(sanitized)
        candidate = f"{base_name}.txt"

        # Disambiguate collisions by appending _1, _2 …
        counter = 1
        while (session_dir / candidate).exists():
            candidate = f"{base_name}_{counter}.txt"
            counter += 1
        return candidate 