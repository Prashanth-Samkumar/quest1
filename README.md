# Quest1 - Video Search & Frame Matcher

An end-to-end full-stack application that downloads, transcribes, and searches videos for specific spoken phrases. When a match is found, the system extracts the exact frame image where the phrase was spoken, presenting the timestamp, matched text, and visual frame back to the user.

---

## System Architecture & Overview

The project uses a background worker model to process long-running media jobs without blocking the web server:

1. **Frontend (React + Vite)**: A premium UI built with vanilla CSS design tokens and dark mode. Users provide a video URL (YouTube, OK.ru, etc.) and a target phrase.
2. **FastAPI Web Server**: Serves as the API layer, accepting requests and queuing Celery jobs. It also polls the status of queued jobs.
3. **Celery Worker & Redis**: The message broker/backend (Redis) queues tasks executed asynchronously by the Celery worker process.
4. **Processing Pipeline**:
   - **Download**: Uses `yt-dlp` to download the audio stream (or full video if needed).
   - **Transcription**: Uses `faster-whisper` (on CPU) to produce word-level timestamps.
   - **Fuzzy Matcher**: Uses `rapidfuzz` to search and match the user's phrase against the transcription segments.
   - **Frame Extraction**: Uses `ffmpeg` & `ffprobe` to seek to the precise timestamp and extract a single frame.
   - **Caching**: Saves transcription segments in Redis with a 7-day TTL to avoid redundant downloads.

---

## 📂 Project Directory Structure

```text
quest1/
├── DESIGN.md                 # Design & architecture documentation
├── PROMPTS.md                # System prompts references
├── README.md                 # Project root documentation (this file)
│
├── backend/                  # Python backend application
│   ├── .env                  # Configuration variables (Redis URL & credentials)
│   ├── .gitignore            # Git ignore rules for Python files & caches
│   ├── .python-version       # Python environment definition
│   ├── config.py             # Config loader for environment variables
│   ├── main.py               # FastAPI server entry point
│   ├── pyproject.toml        # Declarative Python project metadata & dependencies
│   ├── requirements.txt      # Text requirements listing for package managers
│   │
│   ├── src/                  # Source code packages
│   │   ├── __pycache__/      # Python compilation cache
│   │   ├── cache_manager.py  # Redis cache integration (7-day TTL, volatile-lfu)
│   │   ├── celery_app.py     # Celery app initialization & pipeline task definitions
│   │   ├── downloader.py     # yt-dlp wrapper for duration checking & downloading
│   │   ├── frame_extractor.py# FFmpeg frame extractor with sub-second offsets
│   │   ├── matcher.py        # RapidFuzz fuzzy token-matching on transcripts
│   │   ├── pipeline.py       # Cohesive orchestration pipeline
│   │   ├── schemas.py        # Pydantic schemas and pipeline dataclasses
│   │   ├── transcriber.py    # faster-whisper API integration
│   │   └── utils.py          # Utility helpers (Redis URLs, file cleaning, etc.)
│   │
│   └── tests/                # Pytest unit & integration test suites
│       ├── fixtures/         # Test media files & assets
│       ├── test_api.py       # API endpoints tests
│       ├── test_cache_manager.py # Redis caching unit tests
│       ├── test_frame_extractor.py # FFmpeg frame extraction unit tests
│       ├── test_matcher.py   # Fuzzy matching unit tests
│       └── test_pipeline.py  # Full integration pipeline tests
│
└── frontend/                 # Frontend React + Vite SPA
    ├── .gitignore            # Git ignore rules for node_modules & dist
    ├── .oxlintrc.json        # Oxlint configuration
    ├── index.html            # Entrypoint template for Vite
    ├── package.json          # Frontend packages & scripts definition
    ├── package-lock.json     # Node lockfile
    ├── README.md             # Frontend template documentation
    ├── vite.config.js        # Vite build tool configurations
    │
    ├── public/               # Public assets directory
    │   ├── favicon.svg       # Application icon
    │   └── icons.svg         # SVG icon sprite sheets
    │
    └── src/                  # React source files
        ├── App.css           # Local component styles
        ├── App.jsx           # Main interface structure & API polling client
        ├── index.css         # Typography, custom dark-theme variables, & utility classes
        └── main.jsx          # React app DOM mounting anchor
```

---

## Prerequisites

Before running the application, make sure you have installed:

1. **Python**: Version `3.12` or higher.
2. **Node.js & npm**: Node.js `v18+` is recommended.
3. **FFmpeg & FFprobe**: Critical for audio conversion, duration calculation, and frame extraction.
   - *Windows*: Download from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or run `winget install Gyan.FFmpeg`. Ensure both `ffmpeg` and `ffprobe` are added to your System Environment variables under `PATH`.
   - *macOS*: `brew install ffmpeg`
   - *Linux*: `sudo apt update && sudo apt install ffmpeg`
4. **Redis Server**: Local Redis instance or a cloud-hosted Redis database (e.g. Redis Labs).

---

##  How to Run

### 1. Set Up Environment Config

Navigate to the `backend/` directory. You will find a `.env` file containing Redis configuration:

```env
redis_username="default"
redis_password="your_redis_password"
REDIS_URL="redis://your-redis-server-url:port"
```
Ensure this file has valid connection strings for your local or cloud Redis instance.

---

### 2. Run the Backend

Open a terminal window and navigate to the `backend/` directory:

```bash
cd backend
```

#### Step A: Install dependencies
If you are using `uv`, you can sync/run directly. Alternatively, set up a standard virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

#### Step B: Start the Celery Worker
Start the Celery worker queue to process audio and video downloads in the background.

> [!IMPORTANT]
> **Windows Execution Constraint:**
> On Windows, Celery's default `prefork` pool is unsupported and will fail. You **MUST** run the Celery worker using the `-P solo` pool flag to handle tasks synchronously inside the worker thread:
> ```bash
> celery -A src.celery_app worker --loglevel=info -P solo
> ```

On macOS/Linux, you can run:
```bash
celery -A src.celery_app worker --loglevel=info
```

#### Step C: Start the FastAPI Server
In a **new** terminal window (with the virtual environment activated), run the Web API server:

```bash
cd backend
# Activation:
# .venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate (macOS/Linux)

# Run FastAPI
python main.py
```
The backend API server will start running locally at: **`http://127.0.0.1:8000`**

---

### 3. Run the Frontend

Open a **new** terminal window and navigate to the `frontend/` directory:

```bash
cd frontend
```

#### Step A: Install Node packages
```bash
npm install
```

#### Step B: Launch Vite Dev Server
```bash
npm run dev
```
Open your browser and navigate to the local address displayed in your terminal (typically **`http://localhost:5173`**).

---

## 🧪 Running Automated Tests

A comprehensive suite of tests is included in the project to verify API endpoints, the transcriber, cache layer, matcher, and frame extractor.

To execute tests:
1. Navigate to the `backend/` directory in your terminal.
2. Activate your virtual environment.
3. Run the test suite:

```bash
pytest -v
```

---

## 🔍 Troubleshooting & FAQs

* **Error: Connection refused to Redis**
  Ensure that Redis is running. If you are using a cloud-hosted Redis database, double-check the URL, port, username, and password parameters in the `backend/.env` file.
* **Error: FFmpeg or FFprobe not found**
  Confirm that `ffmpeg` and `ffprobe` are installed. Run `ffmpeg -version` and `ffprobe -version` in your terminal. If they are not recognized, you must add the path to the directory containing their binaries into your system's `PATH` environment variable.
* **Celery tasks are stuck in PENDING**
  This usually means the Celery worker process is not running. Make sure you started the worker with `celery -A src.celery_app worker...` in a separate command prompt.
* **Whisper model loading takes too long**
  On the first run, `faster-whisper` downloads the `base` model (~140MB) to your machine. Subsequent runs will use the cached local files and load instantly.
