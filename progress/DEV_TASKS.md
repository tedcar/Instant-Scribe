# Instant Scribe – Development Task List

> This file enumerates every actionable step required to translate the PRD, Blueprint, and Final Product Vision into a shippable Windows-10 desktop application.  
> • All tasks use Markdown check-boxes so progress can be tracked with simple `[ ]` / `[x]` toggles.  
> • Keep tasks in order; append new tasks rather than deleting historical ones.  
> • When a task is completed, mark it `[x]` **and** include a one-line reference to the commit / PR that fulfilled it.  
> • If project direction changes, update both this file **and** the PRD accordingly.

---

## 0  Meta & Project Management
- [x] 0.1 Create `.cursor/rules/progress_tracker.mdc` to enforce automatic task-list maintenance (commit: initial setup)
- [x] 0.2 Set up initial GitHub project board and map each numbered task as an issue (deprecated – user already handled)
- [x] 0.3 Configure branch-naming convention (`feat/`, `fix/`, `docs/`, etc.) and PR template (deprecated – user opted out)

## 1  Development Environment
- [x] 1.1 Create **Python 3.10** virtual‐environment bootstrap script (`scripts/setup_env.ps1`). (commit: c254f81)
- [x] 1.2 Pin all core dependencies and generate `requirements.txt` via `pip-compile`.
	- [x] 1.2.1 Ensure `nemo_toolkit[asr]` is not pinned to a specific version initially to allow `pip-compile` to select the latest stable release compatible with the Parakeet model. (commit: pending)
- [x] 1.3 Write smoke test verifying PyTorch can see CUDA (`python scripts/check_cuda.py`). (commit: 3eeee16)
- [x] 1.4 Document environment setup in `README.md` (dev section). (commit: c254f81)
- [x] 1.5 Enforce GPU presence at startup – application exits with error if `torch.cuda.is_available()` is False. (commit: pending)
- [x] 1.6 Update `setup_env.ps1` to include installation of system-level audio dependencies (e.g., using Chocolatey for `sox`, `ffmpeg`). (commit: pending)
- [x] 1.7 Extend `check_cuda.py` to become `system_check.py`, adding verification for `sox` and `ffmpeg` command availability. (commit: pending)
- [x] 1.8 Pin `nemo_toolkit[asr]` to v2.1.0 and align Torch/TorchAudio/TorchVision to 2.7.1 + cu118 for Windows wheel compatibility. (commit: pending)
- [x] 1.9 Resolve NeMo **ASR collection import failure** detected by `system_check.py`. (commit: env-fix-nemo-asr)
	- [x] 1.9.1 Reinstall Pillow from binary wheels to restore `PIL._imaging` extension (commit: env-fix-pillow)
	- [x] 1.9.2 Verify secondary dependencies (`torchmetrics`, `matplotlib`, `pyannote.audio`, `pydantic<2.0`, etc.) import without errors; pin versions as needed in `requirements.in`. (commit: env-fix-nemo-asr)
	- [x] 1.9.3 Update `system_check.py` status output to turn NeMo line green. (commit: env-fix-nemo-asr)
- [x] 1.10 Ensure external **audio utilities** are available on every dev machine.
	- [x] 1.10.1 Install `sox` via Chocolatey (`choco install -y sox`) and confirm `sox --version` works in a fresh shell. (commit: env-fix-sox-ffmpeg)
	- [x] 1.10.2 Install `ffmpeg` via Chocolatey (`choco install -y ffmpeg`) and confirm `ffmpeg -version` output. (commit: env-fix-sox-ffmpeg)
	- [x] 1.10.3 Document manual install/ZIP-unpack + PATH steps in `README.md` for environments without Chocolatey. (commit: env-docs)
	- [x] 1.10.4 `system_check.py` line prints ✔ for both commands. (commit: env-fix-sox-ffmpeg)
	- [x] 1.10.5 Document that `choco install` commands **must** be executed from an *elevated* PowerShell/Command Prompt session to avoid lock-file errors. (commit: env-docs)
- [x] 1.11 Ensure Python **3.10** virtual-env is the interpreter used by all dev scripts. (commit: env-docs)
	- [x] 1.11.1 Add explicit shebang `#!/usr/bin/env python3.10` to `scripts/system_check.py` and any entry scripts. (commit: env-docs)
	- [x] 1.11.2 Document activation step (`& .venv\Scripts\Activate.ps1`) in README and setup script. (commit: env-docs)
	- [x] 1.11.3 CI job must fail if `python -V` ≠ 3.10.x. (commit: env-docs)
	- [x] 1.11.4 **Remove** any system-wide Python 3.11/3.12 installations and purge their directories from `PATH` (e.g. `winget uninstall --id Python.Python.3.12`).
- [x] 1.12 Resolve CUDA / PyTorch mismatch (GPU not detected) so `system_check.py` turns the CUDA line green. (commit: env-fix-cuda)
- [x] 1.13 Fix NeMo ASR import (install missing secondary deps, pin compatible versions) and turn NeMo ASR line green. (commit: env-fix-nemo-asr)

## 2  Logging & Configuration Framework
- [x] 2.1 Implement `logging_config.py` that initialises rotating file logger (`logs/app.log`).
- [x] 2.2 Develop `config_manager.py` with default settings & JSON persistence (see PRD §4.1). (commit: config-manager-impl)
- [x] 2.3 Unit-test save/load round-trip for `ConfigManager`. (commit: config-tests)

## 3  Resource Helper Utilities
- [x] 3.1 Add `resource_manager.py` with `resource_path()` helper for frozen/ dev modes. (commit: resource-manager-impl)
- [x] 3.2 Write unit test covering both frozen & non-frozen path resolution. (commit: resource-manager-tests)

## 4  Audio Capture & VAD Gate
- [x] 4.1 Create `audio_listener.py` with `AudioStreamer` class (blueprint §3.1.1). (commit: audio-listener-impl)
- [x] 4.2 Integrate WebRTC VAD state machine (blueprint §3.1.2); expose events `on_speech_start`, `on_speech_end`. (commit: audio-listener-impl)
- [x] 4.3 Expose aggressiveness & silence-threshold to `ConfigManager`. (commit: audio-listener-impl)
- [x] 4.4 Write unit tests simulating audio frames to validate gate behaviour. (commit: audio-listener-impl)

## 5  Inter-Process Queues & Message Protocol
- [x] 5.1 Define `ipc/messages.py` with typed dataclasses for commands (`Transcribe`, `Shutdown`, etc.). (commit: ipc-impl)
- [x] 5.2 Prototype simple `multiprocessing.Queue` wrapper with timeout & error propagation. (commit: ipc-impl)
- [x] 5.3 Integration test: enqueue dummy audio, expect echo response. (commit: ipc-impl)

## 6  Transcription Worker Process
- [x] 6.1 Implement `transcription_worker.py` with `TranscriptionEngine.load_model()` (blueprint §2.3.1). (commit: transcription-worker-impl)
- [x] 6.2 Add `get_plain_transcription` & `get_detailed_transcription` APIs. (commit: transcription-worker-impl)
    - [x] 6.2.1 Ensure `get_detailed_transcription` uses the `timestamps=True` flag in the `transcribe()` call as per latest NeMo docs. (commit: transcription-worker-impl)
- [x] 6.3 Warm-up run after model load to reduce first-call latency. (commit: transcription-worker-impl)
- [x] 6.4 Handle CUDA OOM gracefully; return structured error via IPC. (commit: transcription-worker-impl)
- [x] 6.5 Bench-mark RTFx on sample audio (< 2 s target). (commit: transcription-worker-impl)

## 7  Global Hotkey Manager
- [x] 7.1 Create `hotkey_manager.py` wrapping `keyboard` library with start/stop. (commit: hotkey-manager-impl)
- [x] 7.2 Load hotkey string from config; provide runtime reload. (commit: hotkey-manager-impl)
- [x] 7.3 Conflict detection: warn if registration fails. (commit: hotkey-manager-impl)

## 8  System Tray UI
- [x] 8.1 Design 32×32 & 16×16 icon assets (`assets/icon.ico`). (commit: tray-ui-impl)
- [x] 8.2 Implement `tray_app.py` hosting `pystray.Icon` & dynamic menu entries. (commit: tray-ui-impl)
- [x] 8.3 Bind menu actions to same callbacks as hotkeys. (commit: tray-ui-impl)

## 9  Notification Manager
- [x] 9.1 Create `notification_manager.py` using `windows-toasts`. (commit: notification-manager-impl)
- [x] 9.2 Implement clickable action to copy transcription to clipboard (`pyperclip`). (commit: notification-manager-impl)
- [x] 9.3 Fallback path: log warning if WinRT unavailable. (commit: notification-manager-impl)

## 10  Application Orchestrator
- [x] 10.1 Build `instant_scribe` orchestrator that spins up threads/processes & event loop. (commit: orchestrator-impl)
- [x] 10.2 Implement graceful shutdown: flush queues, stop audio, join processes. (commit: orchestrator-impl)
- [x] 10.3 Global `sys.excepthook` → `crash.log` (PRD §4.3.4). (commit: orchestrator-impl)

## 11  VRAM Toggle Feature
- [x] 11.1 Expose `Ctrl+Alt+F6` hotkey to unload/reload model via worker IPC. (commit: vram-toggle-impl)
- [x] 11.2 Emit toast notifications reflecting state. (commit: vram-toggle-impl)
- [x] 11.3 Regression test ensuring memory freed (use `nvidia-smi` snapshot). (commit: vram-toggle-impl)

## 12  Persistence – "Never Lose a Word"
- [x] 12.1 Implement spooler writing numbered PCM chunks to `%APPDATA%/Instant Scribe/temp`. (commit: task12-spooler)
- [x] 12.2 On crash start-up, detect incomplete session & surface recovery toast. (commit: task12-spooler)
- [x] 12.3 Add CLI flag `--recover` to force resume logic in tests. (commit: task12-spooler)

## 13  Archive Manager
- [ ] 13.1 Implement session folder naming (`[n]_[YYYY-MM-DD_HH-MM-SS]`).
- [ ] 13.2 Write `.wav` original & generated `.txt` with first-7-words filename.
- [ ] 13.3 Unit-test naming collisions & unicode handling.

## 14  Watchdog & Autostart
- [ ] 14.1 Create `watchdog.pyw` launching `instant_scribe.py` & relaunch on exit.
- [ ] 14.2 Self-log to `watchdog.log` and back-off 5 s on crash loops.
- [ ] 14.3 PowerShell script to register watchdog in Windows startup.

## 15  Packaging – PyInstaller (depends on Tasks 1–14 completed)
- [ ] 15.1 Generate initial `Instant Scribe.spec` with `--noconsole`.
- [ ] 15.2 Customise `datas` to include Parakeet model cache.
- [ ] 15.3 Implement `resource_path` calls throughout codebase.
- [ ] 15.4 Produce first working `dist/Instant Scribe/Instant Scribe.exe`.

## 16  Installer – Pynsist (depends on Task 15 completed)
- [ ] 16.1 Write `installer.cfg` referencing bundled wheel versions.
- [ ] 16.2 Build `.exe` installer; verify silent install & uninstall flows.
- [ ] 16.3 Add Post-install step to pin Start-up shortcut.
- [ ] 16.4 Verify installer bundles or correctly handles system dependencies (`sox`, `ffmpeg`).

## 17  Cursor Rule & Automation
- [ ] 17.1 Draft `progress_tracker.mdc` rule file (ties to Task 0.1).
- [ ] 17.2 Add CI job that fails build if any unchecked task references older than 30 days.

## 18  Quality Assurance
- [ ] 18.1 Write pytest suite (>= 80 % coverage gate).
- [ ] 18.2 Integration test recording-to-clipboard happy path.
- [ ] 18.3 Load-test long (30 min) recording – ensure memory stable.

## 19  Continuous Integration & Delivery
- [ ] 19.1 Configure GitHub Actions: lint, test, build executable, upload artefact.
- [ ] 19.2 Tag releases & attach installer to GitHub Releases page.

## 20  Documentation & Support
- [ ] 20.1 Update `README.md` with user quick-start & hotkey list.
- [ ] 20.2 Create `docs/TROUBLESHOOTING.md` covering common GPU/driver issues.
- [ ] 20.3 Generate architecture diagram (`docs/diagram.mmd`) using Mermaid.

## 21  Background Batch Transcription
- [ ] 21.1 Implement `batch_transcriber.py` consuming 10-minute audio slices in parallel during recording.
- [ ] 21.2 Merge partial transcriptions on recording stop and maintain correct order.
- [ ] 21.3 Expose batch length & overlap to `ConfigManager`.
- [ ] 21.4 Integration test: 30-min dummy recording returns text in < 3 s.

## 22  Silence Removal Pre-Processor
- [ ] 22.1 Add `silence_pruner.py` that trims > 2 min silence segments prior to transcription.
- [ ] 22.2 User-configurable silence threshold via config.
- [ ] 22.3 Unit test ensuring trimmed output length ≤ input length ‑ 2 min silence.

## 23  Clipboard Robustness
- [ ] 23.1 Create `clipboard_manager.py` with `copy_with_verification()` and retry logic.
- [ ] 23.2 Fallback: write `.txt` file named after first 7 words if copy fails.
- [ ] 23.3 Stress test: copy 1 billion-char string to ensure no crash.
- [ ] 23.4 Integration test: simulate clipboard access denial.

## 24  Enhanced Recording Spooler
- [ ] 24.1 Configure spooler chunk interval to 60 s default, value in config.
- [ ] 24.2 Implement chunk merge utility for recovery workflow.
- [ ] 24.3 Unit test merge of 120 sequential PCM chunks.

## 25  Pause & Resume Workflow
- [ ] 25.1 Bind `Ctrl+Alt+C` hotkey in `hotkey_manager.py` to toggle pause state.
- [ ] 25.2 Persist pause state in config/state for crash recovery.
- [ ] 25.3 Toast notifications reflecting pause/resume.
- [ ] 25.4 Regression test: pause mid-sentence, resume, ensure no audio drop.

## 26  Self-Healing Dependency Checker
- [ ] 26.1 Extend `system_check.py` to detect missing CUDA/NVIDIA driver actionable fixes.
- [ ] 26.2 Attempt silent reinstall/update of critical dependencies; log outcome.
- [ ] 26.3 Unit test: simulate missing driver to validate error path.

## 27  Dependency Management & Automated Pinning
- [ ] 27.1 Audit all direct and transitive dependencies; record minimum compatible versions in `requirements.in`.
- [ ] 27.2 Automate weekly `pip-compile` run; open PR when the lockfile diff exceeds two patches.
- [ ] 27.3 Add CI gate that fails if `pip check` reports vulnerabilities or version mismatches.
- [ ] 27.4 Document upgrade policy and review checklist in `docs/DEPENDENCIES.md`.

## 28  Code Style, Linting & Static Analysis
- [ ] 28.1 Adopt `black` + `isort` for formatting; enforce via pre-commit hook.
- [ ] 28.2 Integrate `flake8` with custom rules mirroring project cursor-rules.
- [ ] 28.3 Introduce `mypy` type-checking across all modules; target `strict` mode for new code.
- [ ] 28.4 CI job fails on style or typing errors; annotate offending lines in PR review.

## 29  Continuous Performance Benchmarking
- [ ] 29.1 Implement `benchmarks/rtf_benchmark.py` measuring Real-Time-Factor (RTF) for 30-s sample audio.
- [ ] 29.2 Store baseline metrics in `benchmark_baselines.json`; flag CI failure if regression > 10 %.
- [ ] 29.3 Generate GitHub Actions artifact containing GPU-utilisation timeline and VRAM graph.

## 30  Security & Code Signing
- [ ] 30.1 Acquire Authenticode certificate; store encrypted PFX in repository secrets.
- [ ] 30.2 Automate `signtool` signing of `Instant Scribe.exe` within the release workflow.
- [ ] 30.3 Add PowerShell script `verify_signature.ps1`; CI job fails if signature missing or invalid.

## 31  Privacy Audit & Network Guard
- [ ] 31.1 Static-scan codebase for network calls (`socket`, `requests`, `http.client`).
- [ ] 31.2 Unit-test asserting that no outbound connections occur during a full recording/transcription cycle.
- [ ] 31.3 Document privacy guarantee in `docs/PRIVACY.md`; include audit script results.

## 32  Crash Reporting & Exception Analytics
- [ ] 32.1 Implement `crash_reporter.py` capturing uncaught exceptions to rotating `crash.log` (10 × 1 MB).
- [ ] 32.2 Attach most recent `crash.log` to a ZIP in `%APPDATA%/Instant Scribe/reports` for manual user share.
- [ ] 32.3 Regression test: induce `ZeroDivisionError`, ensure log file generated and application restarts via watchdog.

## 33  GPU Resource Management Enhancements
- [ ] 33.1 Integrate `pynvml` to monitor real-time VRAM utilisation.
- [ ] 33.2 Auto-unload model when VRAM free < configurable threshold (default 1 GB).
- [ ] 33.3 Notify user via toast and tray icon badge when automatic unload occurs.

## 34  Advanced Testing Infrastructure
- [ ] 34.1 Reach 90 % line coverage using `pytest-cov` (up from 80 %).
- [ ] 34.2 Add property-based tests with `hypothesis` for VAD gate edge cases.
- [ ] 34.3 Introduce `pytest-benchmark` for performance regressions (ties to Task 29).

## 35  Archive Backup & Restore Utilities
- [ ] 35.1 Implement scheduled ZIP backup of session archive to user-defined location.
- [ ] 35.2 Provide `archive_restore.py` CLI restoring backups into the canonical folder structure.
- [ ] 35.3 Integration test: backup-then-restore cycle preserves file hashes.

## 36  Clipboard Integrity Enhancements
- [ ] 36.1 Add CRC32 checksum to clipboard payload; verify after paste.
- [ ] 36.2 On checksum mismatch, trigger fallback file write (leverages Task 23 logic).
- [ ] 36.3 Document rare clipboard failure scenarios and mitigation steps.

## 37  Audio Quality Optimisations
- [ ] 37.1 Implement optional automatic gain control (AGC) using `pydub`.
- [ ] 37.2 Add noise suppression toggle leveraging RNNoise; expose in config.
- [ ] 37.3 Comparative benchmark: WER before/after AGC + noise suppression.

## 38  Continuous Integration & Release Automation
- [ ] 38.1 Consolidate lint, test, benchmark, build, sign, and upload steps into a single reusable GitHub Actions workflow.
- [ ] 38.2 Publish signed installer to GitHub Releases; auto-increment semantic version.
- [ ] 38.3 Slack/Teams webhook notification on successful release (configurable, defaults to disabled).

## 39  Parakeet Model Update Checker
- [ ] 39.1 Weekly background job checks Hugging Face for newer Parakeet TDT checkpoints.
- [ ] 39.2 Prompt user via toast to download & benchmark candidate model.
- [ ] 39.3 Provide CLI flag `--force-model-update` to bypass prompt.

## 40  End-to-End System Load Testing
- [ ] 40.1 Simulate 8-hour continuous recording; monitor CPU/GPU/RAM for leaks.
- [ ] 40.2 Fail test if cumulative VRAM usage drifts > 5 % post-GC.
- [ ] 40.3 Generate HTML report with Grafana-style graphs.

## 41  Codebase Modularisation & Documentation
- [ ] 41.1 Refactor monolithic modules into domain-focused packages (`audio`, `ipc`, `ui`, `core`).
- [ ] 41.2 Auto-generate API docs with `pdoc`; publish to GitHub Pages.
- [ ] 41.3 Add architectural decision records (ADRs) following the MADR template.

## 42  Legal & Compliance Review
- [ ] 42.1 Conduct license audit for all dependencies; record SPDX identifiers.
- [ ] 42.2 Add NOTICE file and third-party license aggregation step to installer.
- [ ] 42.3 Verify export-control compliance for cryptographic components.

## 43  Telemetry & Observability
- [ ] 43.1 Integrate optional runtime metrics collection via OpenTelemetry (opt-out by default); log to `metrics/` folder.
- [ ] 43.2 Unit-test that disabling telemetry removes any outbound network calls (depends on Task 31).

## 44  Accessibility & UX Enhancements
- [ ] 44.1 Produce high-contrast tray icons and 32×32, 16×16 variants; validate against Windows high-contrast themes.
- [ ] 44.2 Ensure toast notifications are readable by Windows Narrator; add `aria-label` equivalents where available.
- [ ] 44.3 Document accessibility compliance strategy in `docs/ACCESSIBILITY.md`.

## 45  High-DPI & Multi-Monitor Support
- [ ] 45.1 Verify tray icon renders crisply on 4K and 8K displays; supply `.ico` containing 256×256 asset.
- [ ] 45.2 Detect DPI changes at runtime and reload icon without app restart.

## 46  Portable Mode Distribution
- [ ] 46.1 Provide ZIP-based portable build skipping registry writes (depends on Task 15 Packaging).
- [ ] 46.2 Update `system_check.py` to locate resources relative to executable in portable mode.

## 47  GPU Capability Fallback
- [ ] 47.1 Detect GPUs with < 3 GB free VRAM; display blocking notification advising unsupported hardware.
- [ ] 47.2 Add CLI flag `--cpu-mode` for future research but keep hard-disabled in v1.0 (logged warning).

## 48  Dependency Auto-Update Service
- [ ] 48.1 Weekly background job checks PyPI for security patches to pinned dependencies (depends on Task 27).
- [ ] 48.2 Open automated PRs with updated `requirements.in` & `requirements.txt`; assign `security` label.

## 49  Compliance & Data Residency
- [ ] 49.1 Add config option allowing users to relocate archive directory to non-system drive.
- [ ] 49.2 Produce GDPR data-export script `scripts/gdpr_export.py` generating ZIP of all user data (depends on Task 13).

## 50  Internationalisation & Localisation Framework
- [ ] 50.1 Externalise user-visible strings to `locale/en_US.json`.
- [ ] 50.2 Provide sample `es_ES.json`; implement runtime language switch via config (depends on Task 9 Notifications).

## 51  Background-Agent Metadata
- [ ] 51.1 Encode task dependency graph in `metadata/tasks.yaml` for Cursor background-agent scheduling.
- [ ] 51.2 CI checks that any new tasks include `depends_on` field.

## 52  Concurrent Batch Transcription Pipeline
- [ ] 52.1 Refactor worker to transcribe batches asynchronously using `asyncio` (depends on Task 6).
- [ ] 52.2 Benchmark throughput improvements; update baseline JSON (Task 29).

## 53  Live VRAM Overlay
- [ ] 53.1 Optional small on-screen overlay showing live VRAM usage (%); toggle via hotkey `Ctrl+Alt+F7`.
- [ ] 53.2 Implementation reuses `pynvml` polling loop (depends on Task 33).

## 54  Structured Log Export
- [ ] 54.1 Upgrade logging to JSON Lines format and rotate daily.
- [ ] 54.2 Provide log viewer CLI `scripts/log_viewer.py` with time-range filtering.

## 55  Crash Dump Processor
- [ ] 55.1 Generate minidump on unhandled exception using `faulthandler` (depends on Task 32).
- [ ] 55.2 Add PowerShell tool `scripts/dump_decoder.ps1` converting dumps to human-readable stack traces.

## 56  GPU Stress Test Harness
- [ ] 56.1 Implement `benchmarks/gpu_stress.py` loading/unloading model 100×; fail if VRAM leak > 5 MB.

## 57  Model Integrity Verification
- [ ] 57.1 Verify Parakeet checkpoint SHA-256 after download; store in `model_manifest.json`.
- [ ] 57.2 Abort startup if checksum mismatch; prompt re-download.

## 58  Config Schema & Validation
- [ ] 58.1 Define `config.schema.json` and validate user config at launch using `jsonschema`.
- [ ] 58.2 CLI tool `scripts/upgrade_config.py` migrates older configs.

## 59  Reproducible Build Pipeline
- [ ] 59.1 Capture build environment hash (Python, pip, Git) into `build_meta.json`.
- [ ] 59.2 CI job compares hash against release tag and fails on mismatch (depends on Task 19).

## 60  Public Release Checklist
- [ ] 60.1 Draft `RELEASE_CHECKLIST.md` enumerating manual QA steps, marketing assets, and support docs.
- [ ] 60.2 Require completion before `v1.0` Git tag can be created.

---

**End of task list – keep adding below this line, never delete history.** 