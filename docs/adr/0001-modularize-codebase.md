# 1. Modularise Codebase into Domain-Focused Packages

Date: 2025-06-21

## Status

Accepted

## Context

The original Instant Scribe codebase grew organically during the first 40
development tasks which resulted in a **flat module hierarchy** with many
single-file utilities living in the top-level *InstanceScrubber* package.
While functional, this structure caused:

* _Low discoverability_ – related classes (e.g. *AudioStreamer* and
  *VADAudioGate*) were scattered across different folders.
* _Tight coupling_ – cross-domain imports made future refactors risky.
* _Documentation friction_ – automatic tooling like **pdoc** prefers
  well-defined packages.

## Decision

We introduce four domain-focused top-level packages:

* `audio` – microphone capture, VAD gate, enhancement and batch
  transcription.
* `ipc` – typed messages and queue abstractions.
* `ui` – system tray UI and toast notifications.
* `core` – configuration, logging and archival utilities.

For the sake of **backwards compatibility** all public symbols are *re-exported*
from the legacy `InstanceScrubber.*` modules.  This allows existing imports and
unit-tests to continue operating unchanged while providing a clean API for new
code.

## Consequences

* New development must import from the domain packages – e.g.
  `from audio import AudioStreamer`.
* Legacy import paths remain functional but are considered _deprecated_ and
  will be removed in a future major release (tracked in DEV_TASKS.md).
* API documentation can now be generated via `scripts/generate_api_docs.py`
  producing a navigable HTML site under `docs/api/`.
* The modular layout simplifies future initiatives such as asynchronous batch
  transcription (Task 52) and observability hooks (Task 43). 