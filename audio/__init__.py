# --- Audio domain package ---------------------------------------------------
"""Domain-focused *audio* package.

This package provides a stable public API by re-exporting audio-related
classes and helpers from the original *InstanceScrubber* monolithic
namespace.

It allows imports such as::

    from audio import AudioStreamer, VADAudioGate

while maintaining full backwards-compatibility for existing code that still
references ``InstanceScrubber.audio_listener`` or other legacy modules.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Re-export public classes / helpers from legacy modules
# ---------------------------------------------------------------------------

from InstanceScrubber.audio_listener import (  # type: ignore
    AudioStreamer,  # noqa: F401 – re-export
    VADAudioGate,   # noqa: F401 – re-export
)
from InstanceScrubber.silence_pruner import SilencePruner  # type: ignore  # noqa: F401
from InstanceScrubber.audio_enhancement import (  # type: ignore  # noqa: F401
    apply_agc_pcm,
    apply_noise_suppression_pcm,
)
from InstanceScrubber.batch_transcriber import BatchTranscriber  # type: ignore  # noqa: F401

__all__: list[str] = [
    "AudioStreamer",
    "VADAudioGate",
    "SilencePruner",
    "apply_agc_pcm",
    "apply_noise_suppression_pcm",
    "BatchTranscriber",
] 