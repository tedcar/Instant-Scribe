import argparse
import json
import sys
from pathlib import Path
import logging

import numpy as np  # type: ignore

from InstanceScrubber.audio_processing import preprocess_audio
from InstanceScrubber.transcription_worker import TranscriptionEngine

# ---------------------------------------------------------------------------
# Small helper – naïve WER implementation (adapted from open-source snippets)
# ---------------------------------------------------------------------------

def _edit_distance(ref, hyp):
    m, n = len(ref), len(hyp)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost,  # substitution
            )
    return dp[m][n]


def _wer(ref: str, hyp: str) -> float:  # noqa: D401 – helper
    ref_words = ref.split()
    hyp_words = hyp.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = _edit_distance(ref_words, hyp_words)
    return dist / len(ref_words)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv=None):  # noqa: D401 – CLI convention
    parser = argparse.ArgumentParser(description="Audio-quality benchmark (Task 37)")
    parser.add_argument("--use-stub", action="store_true", help="Run with stub engine")
    parser.add_argument("--output-json", type=Path, default=None, help="Write results to file")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Generate 5 seconds of low-amplitude white-noise to exercise AGC.
    rng = np.random.default_rng(seed=12345)
    noise = (rng.normal(scale=0.05, size=16_000 * 5) * 32767).astype(np.int16)
    raw_pcm = noise.tobytes()

    # Reference transcript – irrelevant for stub but required for WER calc
    reference_text = "hello world"

    # Prepare engine
    engine = TranscriptionEngine()
    engine.load_model(use_stub=args.use_stub)

    # --- Baseline inference (no processing) ---------------------------------
    baseline_pred = engine.get_plain_transcription(noise)
    wer_baseline = _wer(reference_text, baseline_pred)
    logging.info("Baseline transcript: %s", baseline_pred)
    logging.info("Baseline WER: %.3f", wer_baseline)

    # --- Processed inference (AGC + noise-suppression) ----------------------
    processed_pcm = preprocess_audio(
        raw_pcm, enable_agc=True, enable_noise_suppression=True
    )
    processed_np = np.frombuffer(processed_pcm, dtype=np.int16)
    processed_pred = engine.get_plain_transcription(processed_np)
    wer_processed = _wer(reference_text, processed_pred)
    logging.info("Processed transcript: %s", processed_pred)
    logging.info("Processed WER: %.3f", wer_processed)

    improvement = wer_baseline - wer_processed
    logging.info("WER improvement: %.3f", improvement)

    if args.output_json:
        args.output_json.write_text(
            json.dumps(
                {
                    "baseline": wer_baseline,
                    "processed": wer_processed,
                    "improvement": improvement,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover – CLI only
    main()