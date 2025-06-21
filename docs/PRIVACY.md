# Instant Scribe – Privacy & Network Usage Guarantee

> **Last updated:** 2025-06-21

Instant Scribe is engineered to operate *entirely* on the local machine. All
speech-to-text processing is performed offline using an on-device GPU; **no
outbound network traffic is ever initiated by the application at
runtime.**

## 1. Design Principles Ensuring Offline Operation

* **Local-First Architecture:**
  Every subsystem – audio capture, VAD, transcription, notifications – runs
  inside the local process space.  The NVIDIA Parakeet model is downloaded
  once during development and bundled with the installer; it is never
  fetched at runtime.
* **No Cloud End-Points:**
  Instant Scribe deliberately omits SDKs or libraries that phone home (e.g.
  `requests`, telemetry clients, auto-update daemons).
* **Strict Dependency Pinning:**
  The locked `requirements.txt` ensures no latent dependency upgrades can
  introduce hidden network calls.

## 2. Automated Privacy Audit

A **static privacy-audit** script (`scripts/privacy_audit.py`) is executed on
every CI run and as part of the test-suite.  It scans all production Python
modules and fails the build if it detects imports of known outbound network
libraries such as `socket`, `requests`, or `http.client`.

To run it manually:

```bash
python scripts/privacy_audit.py --fail-on-detected
```

### Latest Audit Result

```
$ python scripts/privacy_audit.py --fail-on-detected
Privacy audit passed – no forbidden network imports found.
```

## 3. Runtime Network Guard

An additional unit-test (`tests/test_task31_privacy_guard.py`) monkey-patches
`socket.socket.connect` during a complete transcription cycle (stub engine)
and asserts that **zero** outbound connection attempts occur.

## 4. User Data Residency

All transient and permanent artefacts (audio chunks, logs, transcripts) are
stored exclusively under the user-controlled directories described in
`02_Final_Product_Vision.md` (§*The Meticulous, Permanent Archive*).  No data
leaves the computer unless the user manually shares it.

## 5. Revision History

| Date | Version | Notes |
|------|---------|-------|
| 2025-06-21 | 1.0 | Initial privacy statement & automated audit results. | 