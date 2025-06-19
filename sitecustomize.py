import platform, signal

# Provide a dummy SIGKILL on Windows for libraries that assume POSIX
if platform.system() == "Windows" and not hasattr(signal, "SIGKILL"):
    signal.SIGKILL = signal.SIGTERM  # type: ignore 