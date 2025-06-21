# Instant Scribe – Troubleshooting Guide

> This document addresses the most common hiccups reported during installation and daily use.

---

## 1. The application starts but shows `CUDA is not available!`

**Symptoms**
- `scripts/system_check.py` prints a red ❌ next to CUDA.
- Toast notification: *"GPU not detected – Instant Scribe cannot run."*

**Fix**
1. Verify that an NVIDIA driver **526.xx** or later is installed:
   ```powershell
   nvidia-smi
   ```
   If the command is missing or the version field is blank, download the latest **Game Ready** or **Studio** driver from [NVIDIA.com](https://www.nvidia.com/Download/index.aspx).
2. Re-run `scripts/check_cuda.py`. If the output still shows ❌, reinstall PyTorch using the wheel that matches your CUDA version:
   ```powershell
   pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

---

## 2. `torch.cuda.OutOfMemoryError` during transcription

**Possible causes**
- Another application (Chrome, a game, etc.) is consuming VRAM.
- Multiple recordings are being processed simultaneously.

**Work-arounds**
1. Press **Ctrl + Alt + F6** to unload the model, freeing ~3 GB VRAM, then reload it when needed.
2. Close other GPU-intensive applications.
3. If the error occurs persistently even on idle desktop, ensure your GPU has at least **6 GB total VRAM**.

---

## 3. `pyaudio` fails to open microphone (Error code -9996)

1. Check that the microphone is not being used exclusively by another app.
2. Set the default recording device in **Sound Settings → Input**.
3. Restart Instant Scribe from the tray icon.

---

## 4. Slow model download (> 5 minutes)

Downloads originate from the Hugging Face CDN and can be ~1 GB. If the download stalls:

- Verify your internet connection.
- Temporarily disable VPNs or proxies.
- Manually download the model archive (`.nemo` file) from
  https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2 and place it into
  `%USERPROFILE%\.cache\torch\NeMo\models\`.

---

## 5. Still stuck?

1. Enable verbose logging by adding `"log_level": "DEBUG"` to `config.json` and restart the app.
2. Open an issue on GitHub with the generated `logs/app.log` and `crash.log` files attached.

---

## 6. Clipboard integrity failures (CRC32 mismatch)

**Symptoms**
- After pressing the copy notification, a fallback `.txt` file appears in the archive directory instead of the text being available on the clipboard.
- Logs contain a line similar to `Clipboard verification mismatch` or `CRC32 verification failed`.

**Why this happens**
Windows' clipboard is occasionally locked or modified by third-party clipboard managers or remote-desktop sessions. In very rare edge-cases the data returned by `Ctrl+V` differs from what was written. Instant Scribe now protects users by attaching a CRC32 checksum to every copy operation and verifying the round-trip.

**Fix / Mitigation**
1. Close aggressive clipboard utilities (e.g. password managers with history, cloud-sync clipboards).
2. Retry the copy action – Instant Scribe will attempt three times by default before falling back.
3. If you routinely work in remote sessions (RDP / VM), consider increasing the `clipboard_retry_delay` in `config.json` to `0.5` seconds.
4. If fallback files are still created, copy the desired text manually from the generated `.txt` file (located in the working directory) and report the incident with the relevant `logs/app.log` excerpt. 