# Instant Scribe

**Ultra-fast, offline-first speech transcription powered by NVIDIA Parakeet TDT 0.6b-v2**

Instant Scribe is a Windows clipboard-based transcription tool that transforms audio and video content into text using state-of-the-art AI. With a single hotkey, capture audio from any source—microphone, system audio, or clipboard media—and get near-instantaneous transcription results copied directly to your clipboard.

## 🚀 Key Features

- **⚡ Ultra-Fast Transcription**: Process 60 minutes of audio in ~1 second using NVIDIA Parakeet TDT 0.6b-v2
- **🔒 100% Offline Operation**: No internet required after setup - your audio never leaves your device
- **📋 Clipboard-Centric Workflow**: Single hotkey operation with automatic clipboard integration
- **🎯 Word-Level Timestamps**: Precise timing information for each transcribed word
- **🔧 Highly Configurable**: Extensive customization options for power users
- **♿ Accessibility Ready**: High-contrast icons and screen reader support
- **🌍 Privacy-First Design**: Local processing ensures complete data privacy
- **💾 Smart Memory Management**: Automatic VRAM optimization and model unloading
- **📊 Real-Time Monitoring**: GPU resource tracking and performance metrics

## 📋 System Requirements

### Minimum Requirements
- **OS**: Windows 10 (1903+) or Windows 11
- **GPU**: NVIDIA GPU with 2+ GB VRAM (GTX 1060, RTX 2060, Tesla T4)
- **CUDA**: Compute Capability 6.1+ 
- **RAM**: 8 GB system memory
- **Storage**: 4 GB free space for model and dependencies

### Recommended Configuration
- **GPU**: NVIDIA RTX 3070/4070 (8+ GB VRAM) or better
- **RAM**: 16+ GB system memory
- **Storage**: SSD with 8+ GB free space

### Enterprise/High-Throughput
- **GPU**: NVIDIA A100, H100
- **RAM**: 32+ GB system memory
- **Storage**: NVMe SSD with 16+ GB free space

## 🛠️ Installation

### Option 1: Pre-built Installer (Recommended)
1. Download `InstantScribe_Setup.exe` from the [Releases](https://github.com/your-repo/instant-scribe/releases) page
2. Run installer **as Administrator**
3. Reboot or sign out/in to complete installation
4. Instant Scribe will auto-start and show: *"Instant Scribe is loaded and ready"*

### Option 2: Portable Installation
1. Download `InstantScribe_Portable.zip` from Releases
2. Extract to desired location (e.g., `C:\Tools\InstantScribe`)
3. Run `InstantScribe.exe` from the extracted folder
4. For auto-start, run: `scripts\register_watchdog_autostart.ps1`

### Option 3: Development Setup
Perfect for developers and advanced users who want to modify or contribute to the project.

```powershell
# 1. Clone the repository
git clone https://github.com/your-repo/instant-scribe.git
cd instant-scribe

# 2. Create Python 3.10+ virtual environment
python -m venv .venv

# 3. Activate environment (PowerShell)
. .\scripts\Activate-IS.ps1

# 4. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5. Verify installation
python scripts\system_check.py
python scripts\check_cuda.py
```

> **NumPy Compatibility Note**: PyTorch wheels require NumPy <2. If you encounter version conflicts, run: `pip install "numpy<2" --upgrade`

## 🎮 Quick Start Guide

### Basic Workflow
1. **Start Recording**: Press `Ctrl + Alt + F`
2. **Speak or Play Audio**: Capture from microphone, system audio, or clipboard media
3. **Stop Recording**: Press `Ctrl + Alt + F` again
4. **Get Results**: Transcription appears in notification and copies to clipboard automatically

### Advanced Usage
- **Pause/Resume**: Use `Ctrl + Alt + C` to pause recording without stopping
- **VRAM Management**: Press `Ctrl + Alt + F6` to unload/reload the AI model
- **Monitor Resources**: Press `Ctrl + Alt + F7` to toggle VRAM overlay display

## ⌨️ Hotkey Reference

| Action | Default Hotkey | Configurable | Description |
|--------|---------------|--------------|-------------|
| **Start/Stop Recording** | `Ctrl + Alt + F` | ✅ | Primary transcription toggle |
| **Pause/Resume** | `Ctrl + Alt + C` | ✅ | Pause without stopping session |
| **Model Management** | `Ctrl + Alt + F6` | ✅ | Unload/reload AI model (frees ~3GB VRAM) |
| **VRAM Overlay** | `Ctrl + Alt + F7` | ✅ | Toggle GPU resource monitor |

> 💡 **Tip**: All hotkeys can be customized in the configuration file. See [Configuration](#-configuration) section below.

## ⚙️ Configuration

Instant Scribe offers extensive customization through a JSON configuration file located at:
`%APPDATA%\Instant_Scribe\config.json`

### Core Settings

#### Audio & Recording
```json
{
  "vad_aggressiveness": 2,              // Voice activity detection (0-3, higher = more aggressive)
  "silence_threshold_ms": 120000,       // Auto-stop after silence (2 minutes default)
  "silence_prune_threshold_ms": 120000, // Remove long silence segments before transcription
  "batch_length_ms": 600000,            // Process audio in 10-minute chunks
  "batch_overlap_ms": 10000,            // 10-second overlap between chunks
  "spooler_chunk_interval_sec": 60      // Write audio to disk every 60 seconds
}
```

#### Hotkeys & Controls
```json
{
  "hotkey": "ctrl+alt+f",               // Main recording toggle
  "pause_hotkey": "ctrl+alt+c",         // Pause/resume recording
  "model_hotkey": "ctrl+alt+f6",        // Model management
  "vram_overlay_hotkey": "ctrl+alt+f7"  // Resource monitor toggle
}
```

#### User Experience
```json
{
  "show_notifications": true,           // Display Windows toast notifications
  "copy_to_clipboard_on_click": true,   // Auto-copy transcription to clipboard
  "archive_root": "C:\\Users\\%USERNAME%\\Documents\\[01] Documents\\[15] AI Recordings"
}
```

#### Performance & Resources
```json
{
  "vram_unload_threshold_mb": 1024,     // Auto-unload model when VRAM < 1GB
  "gpu_monitor_interval_sec": 5,        // GPU monitoring frequency
  "enable_agc": false,                  // Automatic Gain Control
  "enable_noise_suppression": false     // Audio noise reduction
}
```

#### Accessibility & Internationalization
```json
{
  "high_contrast_icons": false,         // Use high-contrast icon variants
  "locale": "en_US",                    // Application language
  "dpi_check_interval_sec": 5           // Multi-monitor DPI change detection
}
```

#### Privacy & Telemetry
```json
{
  "telemetry_enabled": false            // Optional usage metrics (opt-out by default)
}
```

### Configuration Management

#### Validate Configuration
```powershell
python scripts\upgrade_config.py --validate
```

#### Migrate Old Configuration
```powershell
python scripts\upgrade_config.py --migrate
```

#### Fix Configuration Issues
```powershell
python scripts\upgrade_config.py --fix
```

#### Generate Default Configuration
```powershell
python scripts\upgrade_config.py --generate-defaults --output new_config.json
```

## 🧠 AI Model: NVIDIA Parakeet TDT 0.6b-v2

Instant Scribe uses NVIDIA's state-of-the-art Parakeet TDT (Token Duration Transducer) 0.6b-v2 model, specifically optimized for ultra-fast, high-accuracy English transcription.

### Model Capabilities
- **600M Parameters**: Optimal balance of accuracy and efficiency
- **Ultra-Fast Processing**: Up to 3380x real-time speed (60 minutes audio in ~1 second)
- **High Accuracy**: Industry-leading Word Error Rates (WER):
  - LibriSpeech test-clean: 1.69% WER
  - LibriSpeech test-other: 3.19% WER
  - GigaSpeech: 9.74% WER
- **Word-Level Timestamps**: Precise timing for each transcribed word
- **Automatic Punctuation**: Built-in capitalization and punctuation
- **Noise Robustness**: Maintains accuracy across various audio conditions

### Technical Architecture
- **FastConformer Encoder**: 2.4-2.8x faster than standard Conformer
- **Token Duration Transducer**: Jointly predicts tokens and their durations
- **Optimized for NVIDIA GPUs**: Leverages Tensor Cores for maximum performance
- **Offline Operation**: No internet connectivity required after model download

### Supported Audio Formats
- **Input**: WAV, MP3, MP4, AVI, MOV, FLAC, OGG
- **Processing**: Automatically converted to 16kHz mono for optimal accuracy
- **Maximum Length**: 24 minutes per segment (longer audio auto-segmented)

## 📁 File Organization

### Application Structure
```
Instant Scribe/
├── instant_scribe/           # Core application modules
├── InstanceScrubber/         # Heavy-weight processing modules
├── data/                     # Configuration and user data
├── logs/                     # Application and crash logs
├── assets/                   # Icons and UI resources
├── scripts/                  # Utility and maintenance scripts
├── tests/                    # Test suites
└── docs/                     # Documentation
```

### User Data Locations
- **Configuration**: `%APPDATA%\Instant_Scribe\config.json`
- **Logs**: `%APPDATA%\Instant_Scribe\logs\`
- **Archives**: Configurable (default: `Documents\[01] Documents\[15] AI Recordings`)
- **Crash Reports**: `%APPDATA%\Instant_Scribe\reports\`

## 🔧 Advanced Features

### VRAM Management
Instant Scribe intelligently manages GPU memory:
- **Auto-unload**: Frees model when VRAM drops below threshold
- **Smart reload**: Automatically reloads model when needed
- **Resource monitoring**: Real-time VRAM usage display
- **Batch optimization**: Processes multiple files efficiently

### Audio Processing Pipeline
1. **Capture**: Multi-source audio input (microphone, system, clipboard)
2. **Preprocessing**: Noise reduction, gain control, format conversion
3. **Voice Activity Detection**: Intelligent speech segment detection
4. **Silence Pruning**: Removes long silence periods for efficiency
5. **Batch Processing**: Segments long audio with overlap for accuracy
6. **Transcription**: NVIDIA Parakeet TDT processing
7. **Post-processing**: Punctuation, capitalization, timestamp alignment

### Crash Recovery
- **Continuous Spooling**: Audio saved in small chunks during recording
- **Recovery Detection**: Automatic detection of incomplete recordings
- **User Choice**: Option to continue or discard interrupted sessions
- **Data Integrity**: Minimal audio loss even during system crashes

## 🛡️ Privacy & Security

### Data Privacy Guarantee
- **100% Offline Processing**: No audio data ever transmitted over network
- **Local Storage Only**: All files remain on your device
- **No Cloud Dependencies**: Operates completely independently after setup
- **Optional Telemetry**: Usage metrics are opt-out by default

### Security Features
- **Signed Executables**: Code-signed binaries for authenticity verification
- **Minimal Permissions**: Runs with standard user privileges
- **Secure Configuration**: JSON schema validation prevents malicious configs
- **Audit Logging**: Comprehensive activity logs for security review

## 🌐 Accessibility

Instant Scribe is designed with accessibility in mind:

### Visual Accessibility
- **High-Contrast Icons**: Dedicated icon set for visual impairments
- **DPI Awareness**: Automatic scaling for high-DPI displays
- **Multi-Monitor Support**: Consistent behavior across monitor setups

### Screen Reader Support
- **Notification Compatibility**: Toast notifications work with screen readers
- **Keyboard Navigation**: Full functionality via keyboard shortcuts
- **Status Announcements**: Audio feedback for state changes

### Compliance
- **WCAG 2.1 AA**: Targets Web Content Accessibility Guidelines compliance
- **Section 508**: Compatible with US federal accessibility requirements

## 🔍 Troubleshooting

### Common Issues

#### GPU Not Detected
```powershell
# Check CUDA availability
python scripts\check_cuda.py

# Update GPU drivers
# Download latest drivers from NVIDIA website
```

#### Model Loading Errors
```powershell
# Verify system requirements
python scripts\system_check.py

# Check VRAM availability
# Ensure at least 2GB VRAM free
```

#### Audio Input Issues
- **Check microphone permissions** in Windows Privacy Settings
- **Verify audio device** is set as default in Windows Sound settings
- **Test audio levels** using Windows Sound Recorder

#### Configuration Problems
```powershell
# Validate configuration
python scripts\upgrade_config.py --validate

# Reset to defaults
python scripts\upgrade_config.py --generate-defaults
```

### Performance Optimization

#### For Better Speed
- Use NVIDIA RTX series GPU (Tensor Cores)
- Enable GPU boost mode in NVIDIA Control Panel
- Close unnecessary applications to free VRAM
- Use SSD storage for faster model loading

#### For Better Accuracy
- Use high-quality microphone
- Record in quiet environment
- Speak clearly and at moderate pace
- Ensure audio levels are not clipping

### Log Analysis
```powershell
# View recent logs
python scripts\log_viewer.py

# Check for errors
python scripts\log_viewer.py --level ERROR

# Export logs for support
python scripts\log_viewer.py --export
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run test suite: `python -m pytest`
5. Submit pull request

### Code Standards
- **Python 3.10+** compatibility
- **Type hints** for all public APIs
- **Comprehensive tests** with 90%+ coverage
- **Documentation** for all features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses
- **NVIDIA Parakeet TDT 0.6b-v2**: CC-BY-4.0 License
- **NeMo Toolkit**: Apache 2.0 License
- **PyTorch**: BSD-3-Clause License

## 🙏 Acknowledgments

- **NVIDIA** for the Parakeet TDT model and NeMo toolkit
- **PyTorch** team for the deep learning framework
- **Open source community** for various dependencies and tools

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-repo/instant-scribe/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/instant-scribe/discussions)

---

**Made with ❤️ for seamless speech transcription**

## 🔍 Troubleshooting

### Common Issues

#### GPU Not Detected
```powershell
# Check CUDA availability
python scripts\check_cuda.py

# Update GPU drivers
# Download latest drivers from NVIDIA website
```

#### Model Loading Errors
```powershell
# Verify system requirements
python scripts\system_check.py

# Check VRAM availability
# Ensure at least 2GB VRAM free
```

#### Audio Input Issues
- **Check microphone permissions** in Windows Privacy Settings
- **Verify audio device** is set as default in Windows Sound settings
- **Test audio levels** using Windows Sound Recorder

#### Configuration Problems
```powershell
# Validate configuration
python scripts\upgrade_config.py --validate

# Reset to defaults
python scripts\upgrade_config.py --generate-defaults
```

### Performance Optimization

#### For Better Speed
- Use NVIDIA RTX series GPU (Tensor Cores)
- Enable GPU boost mode in NVIDIA Control Panel
- Close unnecessary applications to free VRAM
- Use SSD storage for faster model loading

#### For Better Accuracy
- Use high-quality microphone
- Record in quiet environment
- Speak clearly and at moderate pace
- Ensure audio levels are not clipping

### Log Analysis
```powershell
# View recent logs
python scripts\log_viewer.py

# Check for errors
python scripts\log_viewer.py --level ERROR

# Export logs for support
python scripts\log_viewer.py --export
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run test suite: `python -m pytest`
5. Submit pull request

### Code Standards
- **Python 3.10+** compatibility
- **Type hints** for all public APIs
- **Comprehensive tests** with 90%+ coverage
- **Documentation** for all features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses
- **NVIDIA Parakeet TDT 0.6b-v2**: CC-BY-4.0 License
- **NeMo Toolkit**: Apache 2.0 License
- **PyTorch**: BSD-3-Clause License

## 🙏 Acknowledgments

- **NVIDIA** for the Parakeet TDT model and NeMo toolkit
- **PyTorch** team for the deep learning framework
- **Open source community** for various dependencies and tools

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-repo/instant-scribe/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/instant-scribe/discussions)

---

**Made with ❤️ for seamless speech transcription**
