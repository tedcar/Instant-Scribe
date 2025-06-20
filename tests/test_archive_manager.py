import tempfile
from pathlib import Path

import pytest

from InstanceScrubber.archive_manager import ArchiveManager


@pytest.fixture()
def temp_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("archive_root")


def _create_dummy_wav(path: Path) -> None:  # helper
    # Minimum valid WAV header (44 bytes) with no data for tests
    # RIFF header structure: see https://ccrma.stanford.edu/courses/422/projects/WaveFormat/
    header = (
        b"RIFF"  # Chunk ID
        + (36).to_bytes(4, "little")  # ChunkSize
        + b"WAVE"  # Format
        + b"fmt "  # Subchunk1ID
        + (16).to_bytes(4, "little")  # Subchunk1Size
        + (1).to_bytes(2, "little")  # AudioFormat (PCM)
        + (1).to_bytes(2, "little")  # NumChannels
        + (16000).to_bytes(4, "little")  # SampleRate
        + (16000 * 2).to_bytes(4, "little")  # ByteRate
        + (2).to_bytes(2, "little")  # BlockAlign
        + (16).to_bytes(2, "little")  # BitsPerSample
        + b"data"  # Subchunk2ID
        + (0).to_bytes(4, "little")  # Subchunk2Size – no data
    )
    path.write_bytes(header)


# -----------------------------------------------------------------------------
# Test cases
# -----------------------------------------------------------------------------

def test_session_folder_increment(temp_dir: Path):
    manager = ArchiveManager(base_dir=temp_dir)
    wav1 = temp_dir / "dummy1.wav"
    _create_dummy_wav(wav1)

    first_dir = manager.archive(wav_path=wav1, transcription="Hello world")
    assert first_dir.name.startswith("1_")

    wav2 = temp_dir / "dummy2.wav"
    _create_dummy_wav(wav2)
    second_dir = manager.archive(wav_path=wav2, transcription="Another recording")
    assert second_dir.name.startswith("2_")


def test_transcription_filename_first_seven_words(temp_dir: Path):
    text = "The primary objective for the next quarter is increased"  # 9 words
    manager = ArchiveManager(base_dir=temp_dir)
    wav = temp_dir / "dummy.wav"
    _create_dummy_wav(wav)

    session_dir = manager.archive(wav_path=wav, transcription=text)
    expected_prefix = "The_primary_objective_for_the_next_quarter.txt"
    files = list(session_dir.iterdir())
    # Locate txt file
    txt_files = [f for f in files if f.suffix == ".txt"]
    assert len(txt_files) == 1
    assert txt_files[0].name == expected_prefix


def test_collision_resolution(temp_dir: Path):
    manager = ArchiveManager(base_dir=temp_dir)

    wav = temp_dir / "dummy.wav"
    _create_dummy_wav(wav)

    text = "Collision test text"
    dir1 = manager.archive(wav_path=wav, transcription=text)
    txt1 = next(dir1.glob("*.txt"))

    # Archive again with same transcription
    dir2 = manager.archive(wav_path=wav, transcription=text)
    txt2 = next(dir2.glob("*.txt"))

    assert txt1.name == "Collision_test_text.txt"
    assert txt2.name == "Collision_test_text.txt"


def test_unicode_handling(temp_dir: Path):
    manager = ArchiveManager(base_dir=temp_dir)
    wav = temp_dir / "dummy.wav"
    _create_dummy_wav(wav)

    text = "Привет мир это тестовое сообщение"
    session_dir = manager.archive(wav_path=wav, transcription=text)
    txt_files = list(session_dir.glob("*.txt"))
    assert len(txt_files) == 1
    # File exists and path is Unicode-capable
    assert txt_files[0].exists(), "Unicode filename should be created successfully" 