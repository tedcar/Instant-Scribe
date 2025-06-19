================================================================================
Instant Scribe: Product Requirements Document (PRD)
Version: 2.0
Status: Definitive
================================================================================

1.0 INTRODUCTION & VISION

1.1. PRODUCT PHILOSOPHY
Instant Scribe is not an application to be consciously run; it is a fundamental, integrated capability of the Windows 10 operating system. Its design philosophy is forged from three core tenets: unyielding longevity, absolute minimalism, and unimpeachable reliability. It is conceived as a "set it and forget it" utility—a permanent component of the user's digital life, engineered to be installed once and to function flawlessly for years. Its singular mission is to achieve a state of zero friction between spoken thoughts and clean, perfectly formatted, immediately usable text output.

1.2. PROBLEM DOMAIN
The contemporary workflow for transcribing audio is characterized by high friction. It involves web browsers, unstable network connections, user authentications, multiple clicks, and significant processing delays. Furthermore, cloud-based services engender valid concerns regarding data privacy and introduce recurring subscription costs. The target user requires a transcription utility that is private, immediate, and seamlessly integrated into their native OS environment.

1.3. PROPOSED SOLUTION
Instant Scribe is a local-first, high-performance, offline-capable Speech-to-Text (STT) engine that manifests as a silent icon in the Windows system tray. It is controlled entirely via global system hotkeys, leveraging the on-device NVIDIA GPU to provide near-instantaneous transcription. By performing all operations locally, it guarantees user privacy, eliminates network latency, and ensures perpetual availability, independent of internet connectivity. It is the antithesis of the cumbersome modern transcription workflow.

1.4. TARGET USER PROFILE
The intended user is a Windows 10 "power user." This includes professionals, content creators, writers, students, and developers who:
- Possess a Windows 10 machine equipped with a modern, CUDA-capable NVIDIA GPU (e.g., RTX 30-series or newer).
- Have a frequent and recurring need for audio transcription.
- Place a premium on data privacy and prefer self-contained, offline software.
- Favor a minimalist, keyboard-centric workflow that minimizes context switching and graphical user interface (GUI) interaction.


2.0 SYSTEM ARCHITECTURE & TECHNOLOGY STACK

2.1. CORE ARCHITECTURAL PRINCIPLES
- **MINIMALISM BY DEFAULT:** The application's baseline operational state is dormancy. It resides in the system tray consuming near-zero CPU, RAM, and GPU resources. The primary resource consumer—the transcription engine—is invoked only upon the detection of active speech. This is the cornerstone of its "lifelong" operational capability.
- **ROBUSTNESS THROUGH ISOLATION:** The application is architected as a multi-threaded, multi-process system. Core functions (Audio Capture, Voice Activity Detection, Transcription Engine, UI) are encapsulated. The AI model and its dependencies run in a dedicated, isolated worker process. A catastrophic failure or CUDA error within this process will not terminate the main application, allowing for graceful recovery and state preservation.
- **LOCAL-FIRST PROCESSING:** All operations, from audio capture to STT inference, occur on the local machine. This is a non-negotiable principle that guarantees privacy and offline functionality.

2.2. DEFINITIVE TECHNOLOGY STACK
--------------------------------------------------------------------------------
| Component                 | Selected Technology         | Version/Spec                    | Justification                                                                                             |
|---------------------------|-----------------------------|---------------------------------|-----------------------------------------------------------------------------------------------------------|
| ASR Model                 | NVIDIA Parakeet TDT         | nvidia/parakeet-tdt-0.6b-v2     | Industry-best WER (6.05%) & speed (RTFx ~3380) in a local-first, efficient (<3GB VRAM) package.          |
| ML Framework              | NVIDIA NeMo Toolkit         | nemo_toolkit[asr]==2.1.0        | Windows wheel available; avoids build-tool chain while remaining fully compatible with Parakeet.        |
| Language/Runtime          | Python & PyTorch            | Python 3.10, torch 2.7.1+cu118  | Version aligned with NeMo 2.1.0 and tested against CUDA 11.8 on RTX-30 series GPUs.                      |
| System Dependencies       | Sox, FFmpeg, libsndfile     | Latest stable                   | Essential underlying audio processing libraries required by NeMo for handling various audio formats.      |
| Audio Capture             | PyAudio                     | pyaudio==0.2.14                 | Stable, low-level bindings to PortAudio for reliable, direct microphone access on Windows.                |
| Voice Activity Detection  | webrtcvad-wheels            | webrtcvad-wheels==2.0.14        | Critical for efficiency. Lightweight, real-time VAD prevents constant GPU load from the ASR model.      |
| Global Hotkeys            | keyboard                    | keyboard==0.13.5                | Pure-Python, dependency-free global keyboard event hooking for a background application.                |
| System Tray UI            | pystray                     | pystray==0.19.0                 | Dedicated library for creating and managing a system tray icon for unobtrusive background operation.    |
| Notifications             | windows-toasts              | windows-toasts==1.3.1           | Modern library using WinRT for native Windows 10/11 toast notifications for seamless UX.                |
| Packaging                 | PyInstaller                 | pyinstaller==6.8.0              | Industry standard for bundling Python apps and dependencies into a standalone .exe.                     |
| Installer                 | Pynsist                     | pynsist==2.8                    | Creates a professional .msi Windows installer, capable of bundling the Python runtime.                  |
--------------------------------------------------------------------------------

3.0 DETAILED FUNCTIONAL REQUIREMENTS & USER EXPERIENCE

3.1. INSTALLATION & FIRST BOOT
- **FR-3.1.1:** The user journey begins with a single, self-contained installer executable: `InstantScribe_Setup.exe`.
- **FR-3.1.2:** The installer MUST execute with administrative privileges. The experience shall be devoid of options, checkboxes, or bundled offers.
- **FR-3.1.3:** The installer MUST deploy the application and all dependencies (including a sandboxed Python environment) into a protected program directory (e.g., `C:\Program Files\Instant Scribe`).
- **FR-3.1.4:** The installer MUST register the application's watchdog process (`watchdog.pyw`) to launch automatically and silently at every system boot.
- **FR-3.1.5:** Upon the first (and every subsequent) boot, the application MUST awaken silently and perform system checks (see Section 4.1).
- **FR-3.1.6:** The primary startup task is to load the `nvidia/parakeet-tdt-0.6b-v2` model into the GPU's VRAM. The model is loaded once and MUST remain resident.
- **FR-3.1.7:** A single, transient Windows toast notification MUST appear to confirm successful initialization: "Instant Scribe is loaded and ready."

3.2. THE CORE WORKFLOW (USER INTERACTION MODEL)
The entire user experience is mediated through global hotkeys and system notifications. There is no primary application window.

- **FR-3.2.1: To Begin Recording (`Ctrl+Alt+F`)**
    - The application MUST first verify that the ASR model is resident in VRAM.
    - If the model is loaded, recording from the default system microphone MUST start instantaneously.
    - A Windows toast notification with a clear "Recording" indicator (e.g., green icon) MUST appear with the text: "Recording started."
    - If the model is not loaded, recording MUST NOT start. A specific error notification MUST appear: "Error: Model is not loaded. Press Ctrl+Alt+F6 to load the model."

- **FR-3.2.2: To Pause/Resume Recording (`Ctrl+Alt+C`)**
    - When an active recording is in progress, pressing `Ctrl+Alt+C` MUST pause the audio capture.
    - A notification with a "Paused" indicator (e.g., yellow icon) MUST appear with the text: "Recording paused."
    - Pressing `Ctrl+Alt+C` again MUST resume audio capture seamlessly.
    - The "Recording started" notification MUST reappear.

- **FR-3.2.3: To Stop & Transcribe (Second `Ctrl+Alt+F`)**
    - Pressing `Ctrl+Alt+F` while a recording is active triggers the finalization sequence.
    - Audio recording MUST cease immediately.
    - The captured audio data MUST be passed to the isolated transcription worker process.
    - The Parakeet model, already in VRAM, performs the transcription.
    - Upon completion, a final notification MUST appear: "Transcription complete. Text copied to clipboard."
    - Simultaneously, the full, clean, punctuated, and capitalized text (with no timestamps) MUST be placed onto the system clipboard.
    - **Technical Note:** While the primary output is timestamp-free, detailed word-level timestamps for diagnostic or future features can be obtained by passing `timestamps=True` to the model's `transcribe` method.

- **FR-3.2.4: Background Batch Transcription**
    - While a recording is in progress, the application MUST automatically slice the audio stream into 10-minute batches and begin transcribing each batch in the background.
    - When the user finally stops the recording, only the final, un-transcribed batch MAY remain for processing, ensuring near-instantaneous completion regardless of total recording length.

- **FR-3.2.5: Long-Silence Pruning**
    - Prior to sending any audio batch to the ASR model, the application MUST detect and remove continuous periods of silence longer than 2 minutes.
    - The silence-length threshold MUST be configurable via `config.json` (default: `120000` ms).

- **FR-3.2.6: Clipboard Robustness & Fallback**
    - After each transcription, the application MUST verify that the clipboard operation succeeded by immediately reading back the clipboard contents and confirming the byte-length matches the intended text.
    - If the clipboard verification fails, the application MUST write the transcription to a `.txt` file inside the session folder, using the naming convention defined in FR-4.4.5.
    - This fallback MUST guarantee that the transcription is never lost, even for extremely large texts.

3.3. ON-DEMAND RESOURCE MANAGEMENT
The user has direct control over the application's VRAM footprint without exiting the application.

- **FR-3.3.1: The VRAM Toggle (`Ctrl+Alt+F6`)**
    - This hotkey acts as a dedicated switch for the ASR model's residency in VRAM.
    - **To Unload:** Pressing `Ctrl+Alt+F6` when the model is loaded MUST unload it from VRAM, freeing the resource (~3GB). A notification MUST confirm: "Model unloaded from VRAM. Instant Scribe is now in standby."
    - **To Reload:** Pressing `Ctrl+Alt+F6` when the model is unloaded MUST trigger the loading process. A notification MUST confirm success: "Model loaded and ready."

3.4. SYSTEM PRESENCE & EXIT
- **FR-3.4.1:** The application's only persistent visual footprint MUST be a single icon in the system tray.
- **FR-3.4.2:** Right-clicking the tray icon MUST display a minimal context menu.
- **FR-3.4.3:** The menu MUST contain:
    - A non-interactive status indicator (e.g., "Status: Listening").
    - A "Toggle Listening" option that mirrors the `Ctrl+Alt+F` functionality.
    - An "Exit" option.
- **FR-3.4.4:** Clicking "Exit" MUST perform a graceful shutdown: unload the model from VRAM, terminate all threads and processes.
- **FR-3.4.5:** A confirmation dialog ("Are you sure you want to close Instant Scribe?") MUST prevent accidental closure.


4.0 RELIABILITY, DATA INTEGRITY & ERROR HANDLING

4.1. STARTUP VERIFICATION
- **FR-4.1.1:** On every launch, the application MUST programmatically check for a compatible NVIDIA driver by executing `nvidia-smi` and parsing the output.
- **FR-4.1.2:** It MUST also verify that PyTorch can access a usable CUDA environment via `torch.cuda.is_available()`.
- **FR-4.1.3:** If these checks fail, the application MUST display a user-friendly notification guiding them to the NVIDIA driver download page.
- **FR-4.1.4:** The application MUST terminate immediately after displaying the notification; CPU-only operation is explicitly unsupported.

4.2. THE "NEVER LOSE A WORD" GUARANTEE
- **FR-4.2.1:** From the moment recording starts, the application MUST continuously spool the raw audio stream into small, sequentially numbered temporary files in a hidden application data directory.
- **FR-4.2.2:** In the event of a catastrophic system failure (power loss, OS crash), only the last few seconds of speech in the buffer should be at risk.
- **FR-4.2.3:** The application's next boot cycle MUST trigger a recovery protocol. It will detect the orphaned temporary files.
- **FR-4.2.4:** A unique, high-priority notification MUST be presented to the user with two clickable buttons: "An incomplete recording was found. Resume?" and "Discard".

4.3. CRASH RESILIENCE & LIFELONG OPERATION
- **FR-4.3.1:** The main application (`Instant Scribe.py`) MUST be launched and monitored by a separate, minimal `watchdog.pyw` script.
- **FR-4.3.2:** The `.pyw` extension MUST be used to ensure the watchdog runs without a console window.
- **FR-4.3.3:** If the main application process terminates for any reason, the watchdog MUST log the event and restart the main application after a 5-second delay.
- **FR-4.3.4:** A global, top-level exception handler (`sys.excepthook`) MUST be set. Any unhandled exception will be logged to a `crash.log` file before the application attempts to terminate.

4.4. PERMANENT ARCHIVE
- **FR-4.4.1:** All completed recording sessions MUST be meticulously archived.
- **FR-4.4.2:** The master archive directory MUST be created if it does not exist at: `C:\Users\Admin\Documents\[01] Documents\[15] AI Recordings`.
- **FR-4.4.3:** Each session MUST result in the creation of a new, uniquely named folder using the convention: `[recording_number]_[YYYY-MM-DD_HH-MM-SS]`. (e.g., `42_2027-10-31_15-45-10`).
- **FR-4.4.4:** Inside each session folder, exactly two files MUST be present:
    - `recording.wav`: The original, high-quality, full-length audio file.
    - A `.txt` file containing the final, clean transcription.
- **FR-4.4.5:** The filename of the `.txt` file MUST be algorithmically generated from its own content: it is named after the first seven words of the transcription, with spaces replaced by underscores. (e.g., "The_primary_objective_for_the_next.txt").

4.5. CLIPBOARD ROBUSTNESS GUARANTEE

- **FR-4.5.1:** After every clipboard copy attempt, the application MUST validate success by re-reading the clipboard and comparing the text length.
- **FR-4.5.2:** On validation failure, the application MUST invoke the fallback mechanism specified in FR-3.2.6 without user intervention.
- **FR-4.5.3:** All clipboard failures MUST be logged to `app.log` with a timestamp and error details to aid debugging.


5.0 NON-FUNCTIONAL REQUIREMENTS

5.1. PERFORMANCE
- **Idle State:** When not recording, resource consumption (CPU, RAM, GPU) must be negligible.
- **Transcription Latency:** For typical utterances (< 30 seconds), the time from pressing `Ctrl+Alt+F` (stop) to the "Complete" notification should feel instantaneous, ideally under 2 seconds.
- **VRAM Footprint:** The application must plan for a VRAM footprint of ~3.0 GB for the loaded model.

5.2. COMPATIBILITY
- **Operating System:** Microsoft Windows 10 (64-bit).
- **Hardware:** NVIDIA GPU with CUDA support (Ampere, Blackwell, Hopper, or Volta architecture recommended). A minimum of 3GB of dedicated, available VRAM is required.

5.3. PRIVACY & SECURITY
- **Data Locality:** 100% of user data, including all audio, temporary files, and final transcriptions, MUST remain on the local machine.
- **Network:** The application MUST NOT make any outbound network calls, except for the one-time download of the ASR model by the NeMo toolkit upon first use.

6.0 OUT OF SCOPE (FOR VERSION 1.0)
- Support for operating systems other than Windows 10.
- Support for non-NVIDIA (AMD, Intel) or non-CUDA GPUs.
- A graphical user interface for settings (all configuration via `config.json`).
- Cloud synchronization, backup, or sharing features.
- Real-time "live" transcription display.
- Support for languages other than English.
- User accounts, profiles, or authentication systems. 