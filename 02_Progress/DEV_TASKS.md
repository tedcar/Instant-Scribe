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
- [ ] 1.7 Extend `check_cuda.py` to become `system_check.py`, adding verification for `sox` and `ffmpeg` command availability.
- [x] 1.8 Pin `nemo_toolkit[asr]` to v2.1.0 and align Torch/TorchAudio/TorchVision to 2.7.1 + cu118 for Windows wheel compatibility. (commit: pending)

## 2  Logging & Configuration Framework
- [ ] 2.1 Implement `logging_config.py` that initialises rotating file logger (`logs/app.log`).
- [ ] 2.2 Develop `config_manager.py` with default settings & JSON persistence (see PRD §4.1).
- [ ] 2.3 Unit-test save/load round-trip for `ConfigManager`.

## 3  Resource Helper Utilities
- [ ] 3.1 Add `resource_manager.py` with `resource_path()` helper for frozen/ dev modes.
- [ ] 3.2 Write unit test covering both frozen & non-frozen path resolution.

## 4  Audio Capture & VAD Gate
- [ ] 4.1 Create `audio_listener.py` with `AudioStreamer` class (blueprint §3.1.1).
- [ ] 4.2 Integrate WebRTC VAD state machine (blueprint §3.1.2); expose events `on_speech_start`, `on_speech_end`.
- [ ] 4.3 Expose aggressiveness & silence-threshold to `ConfigManager`.
- [ ] 4.4 Write unit tests simulating audio frames to validate gate behaviour.

## 5  Inter-Process Queues & Message Protocol
- [ ] 5.1 Define `ipc/messages.py` with typed dataclasses for commands (`Transcribe`, `Shutdown`, etc.).
- [ ] 5.2 Prototype simple `multiprocessing.Queue` wrapper with timeout & error propagation.
- [ ] 5.3 Integration test: enqueue dummy audio, expect echo response.

## 6  Transcription Worker Process
- [ ] 6.1 Implement `transcription_worker.py` with `TranscriptionEngine.load_model()` (blueprint §2.3.1).
- [ ] 6.2 Add `get_plain_transcription` & `get_detailed_transcription` APIs.
    - [ ] 6.2.1 Ensure `get_detailed_transcription` uses the `timestamps=True` flag in the `transcribe()` call as per latest NeMo docs.
- [ ] 6.3 Warm-up run after model load to reduce first-call latency.
- [ ] 6.4 Handle CUDA OOM gracefully; return structured error via IPC.
- [ ] 6.5 Bench-mark RTFx on sample audio (< 2 s target).

## 7  Global Hotkey Manager
- [ ] 7.1 Create `hotkey_manager.py` wrapping `keyboard` library with start/stop.
- [ ] 7.2 Load hotkey string from config; provide runtime reload.
- [ ] 7.3 Conflict detection: warn if registration fails.

## 8  System Tray UI
- [ ] 8.1 Design 32×32 & 16×16 icon assets (`assets/icon.ico`).
- [ ] 8.2 Implement `tray_app.py` hosting `pystray.Icon` & dynamic menu entries.
- [ ] 8.3 Bind menu actions to same callbacks as hotkeys.

## 9  Notification Manager
- [ ] 9.1 Create `notification_manager.py` using `windows-toasts`.
- [ ] 9.2 Implement clickable action to copy transcription to clipboard (`pyperclip`).
- [ ] 9.3 Fallback path: log warning if WinRT unavailable.

## 10  Application Orchestrator
- [ ] 10.1 Build `instant_scribe.py` main script that spins up threads/processes & event loop.
- [ ] 10.2 Implement graceful shutdown: flush queues, stop audio, join processes.
- [ ] 10.3 Global `sys.excepthook` → `crash.log` (PRD §4.3.4).

## 11  VRAM Toggle Feature
- [ ] 11.1 Expose `Ctrl+Alt+F6` hotkey to unload/reload model via worker IPC.
- [ ] 11.2 Emit toast notifications reflecting state.
- [ ] 11.3 Regression test ensuring memory freed (use `nvidia-smi` snapshot).

## 12  Persistence – "Never Lose a Word"
- [ ] 12.1 Implement spooler writing numbered PCM chunks to `%APPDATA%/Instant Scribe/temp`.
- [ ] 12.2 On crash start-up, detect incomplete session & surface recovery toast.
- [ ] 12.3 Add CLI flag `--recover` to force resume logic in tests.

## 13  Archive Manager
- [ ] 13.1 Implement session folder naming (`[n]_[YYYY-MM-DD_HH-MM-SS]`).
- [ ] 13.2 Write `.wav` original & generated `.txt` with first-7-words filename.
- [ ] 13.3 Unit-test naming collisions & unicode handling.

## 14  Watchdog & Autostart
- [ ] 14.1 Create `watchdog.pyw` launching `instant_scribe.py` & relaunch on exit.
- [ ] 14.2 Self-log to `watchdog.log` and back-off 5 s on crash loops.
- [ ] 14.3 PowerShell script to register watchdog in Windows startup.

## 15  Packaging – PyInstaller
- [ ] 15.1 Generate initial `Instant Scribe.spec` with `--noconsole`.
- [ ] 15.2 Customise `datas` to include Parakeet model cache.
- [ ] 15.3 Implement `resource_path` calls throughout codebase.
- [ ] 15.4 Produce first working `dist/Instant Scribe/Instant Scribe.exe`.

## 16  Installer – Pynsist
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

---

**End of task list – keep adding below this line, never delete history.** 