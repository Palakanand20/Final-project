# Setup Guide

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `pip3` (comes with Python)
- A terminal and a browser

No Docker, no Node.js, no build tools required.

---

## Step-by-Step Installation

### 1. Get the code

```bash
git clone <repo-url>
cd wiki-explorer
```

Or download and unzip the archive, then `cd` into the directory.

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip3 install fastapi uvicorn requests rich httpx pytest pytest-cov
```

Or install from `pyproject.toml`:

```bash
pip3 install -e .
```

### 4. Start the server

```bash
python3 -m uvicorn server.app:app --reload --port 8001
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
```

The database (`server/wiki.db`) is created automatically on first run.

### 5. Verify each interface

**Web UI:**
```bash
open http://localhost:8001   # macOS
# or xdg-open http://localhost:8001  # Linux
# or just paste http://localhost:8001 into any browser
```

Type "Black hole" in the search box and click **Explore**. You should see a graph appear within a few seconds.

**CLI:**
```bash
python3 cli/main.py search "Nikola Tesla"
```

Expected output: a numbered list of Wikipedia article titles.

**TUI:**
```bash
python3 tui/main.py
```

Expected: a menu with five options in the terminal. Press `q` to exit.

**GUI:**
```bash
python3 gui/main.py
```

Expected: a dark-themed window with a search bar and an empty canvas.

---

## Running on a Different Port

If port 8001 is already in use:

```bash
python3 -m uvicorn server.app:app --reload --port 8002
```

Then update `client/api.py` line 7:
```python
BASE_URL = "http://localhost:8002"   # was 8001
```

The web UI reads the API from the same origin, so no change is needed there.

---

## Common Errors and Fixes

### `ModuleNotFoundError: No module named 'fastapi'`

You forgot to install dependencies or the virtual environment is not activated.

```bash
source .venv/bin/activate
pip3 install fastapi uvicorn requests rich httpx
```

### Port 8001 already in use

```
ERROR:    [Errno 48] Address already in use
```

Either kill the existing process or use a different port:

```bash
# Find what's using port 8001
lsof -i :8001
kill <PID>
# or just use a different port
python3 -m uvicorn server.app:app --reload --port 8002
```

### Wikipedia returns 403 Forbidden

Wiki Explorer sends a `User-Agent` header to comply with Wikipedia's API policy. If you see 403 errors, your IP may be temporarily blocked due to too many requests. Wait a few minutes and try again. Do not remove the `User-Agent` header.

### Blank page in the browser at `http://localhost:8001`

Check that the server is actually running (`python3 -m uvicorn ...`). If the server is running but the page is blank, open the browser's developer console (F12) and look for errors. The most common cause is a CORS issue from a stale browser cache — do a hard refresh (Ctrl+Shift+R / Cmd+Shift+R).

### `cli/main.py: command not found`

You need to run it with Python:
```bash
python3 cli/main.py search "test"
# not: ./cli/main.py search "test"  (unless you chmod +x it)
```

### GUI window doesn't open (Linux)

Tkinter requires a display. On a headless server:
```bash
sudo apt-get install python3-tk
# or use a virtual display:
Xvfb :99 & DISPLAY=:99 python3 gui/main.py
```

---

## Clearing the Cache

The SQLite database at `server/wiki.db` grows as you explore articles. To clear it:

```bash
rm server/wiki.db
```

The server will recreate an empty database on the next request.
