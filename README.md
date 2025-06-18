# Instant Scribe

A minimalist, high-performance, local-first transcription tool for Windows.

---

## Development Setup

This project uses Python 3.10+ and `pip-tools` for dependency management.

1.  **Clone the repository:**
    ```sh
    git clone <repository-url>
    cd Instant-Scribe
    ```

2.  **Create the virtual environment:**
    Run the PowerShell script to create an isolated virtual environment.
    ```powershell
    ./scripts/setup_env.ps1
    ```

3.  **Activate the environment:**
    ```powershell
    ./.venv/Scripts/Activate.ps1
    ```

4.  **Install dependencies:**
    The `requirements.txt` file is generated from `requirements.in`. To install the pinned dependencies, run:
    ```sh
    pip install -r requirements.txt
    ```

5.  **Running Tools:**
    With the environment activated, you can run tools like `pytest`.

---

*This README will be updated with user-facing documentation upon first release.*