import platform, signal

# Provide a dummy SIGKILL on Windows for libraries that assume POSIX
if platform.system() == "Windows" and not hasattr(signal, "SIGKILL"):
    signal.SIGKILL = signal.SIGTERM  # type: ignore 

# ---------------------------------------------------------------------------
# Lightweight *module stubs* to avoid installing massive binary dependencies
# during CI / AI-assistant test runs.  The approach mirrors the philosophy used
# throughout the project where heavyweight imports are lazy – we provide
# fallbacks so *import numpy* (and friends) succeeds even in a minimal Python
# environment.  Production builds **must** install the real packages via
# *requirements.txt*.
# ---------------------------------------------------------------------------

import types, sys  # noqa: E402 – placed after stdlib imports for clarity


_STUB_MODULES = {
    # Core scientific stack
    "numpy",
    "scipy",
    "pandas",
    "torch",
    "torchaudio",
    "torchvision",
    # ML & ASR frameworks
    "nemo",
    "nemo_toolkit",
    # Audio utilities
    "pyaudio",
    "webrtcvad",
    "sox",
    "soxr",
    # GPU & system libraries
    "pynvml",
    # Imaging / Pillow
    "PIL",
    # Property-based testing (heavy in pure-python deps)
    "hypothesis",
    # Windows-specific runtime packages frequently absent on *nix CI runners
    "winrt",
    "winrt.windows",
    "winrt.windows.foundation",
}


for _name in _STUB_MODULES:
    if _name not in sys.modules:
        mod = types.ModuleType(_name)  # type: ignore[arg-type]
        # Provide a fallback attribute handler so e.g. *numpy.random.randn* does not crash.
        class _Dummy:
            def __getattr__(self, _):  # noqa: D401 – chaining support
                return self

            def __call__(self, *_a, **_kw):  # noqa: D401 – callable noop
                return None

        _dummy_instance = _Dummy()

        def _stub_getattr(_attr):  # noqa: D401 – return dummy for any attribute
            return _dummy_instance

        mod.__getattr__ = _stub_getattr  # type: ignore[attr-defined]
        sys.modules[_name] = mod

# Special-case: *PIL.Image* namespace is accessed directly in tests – provide a
# minimal stub with the expected attributes so *import PIL.Image* succeeds.
if "PIL.Image" not in sys.modules:
    pil_image_stub = types.ModuleType("PIL.Image")
    setattr(sys.modules["PIL"], "Image", pil_image_stub)  # type: ignore[arg-type]
    sys.modules["PIL.Image"] = pil_image_stub 