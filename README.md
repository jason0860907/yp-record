# yp-record

Lightweight recording pipeline: **ASR → Forced Alignment → Speaker Diarization → Notion**

A full-stack application that captures audio, transcribes it in real time, aligns timestamps, identifies speakers, generates meeting notes with LLM, and exports everything to Notion.

## Features

- **Real-time recording** — stream audio via WebSocket from microphone and browser tab
- **Automatic Speech Recognition** — Qwen3-ASR powered by vLLM
- **Forced alignment** — word-level timestamps via Qwen3-ForcedAligner
- **Speaker diarization** — multi-speaker identification via pyannote.audio
- **LLM extraction** — transcript polishing and structured meeting note generation
- **Notion export** — one-click publish to a Notion database
- **Screenshot capture** — attach screenshots to recording sessions
- **Event-driven architecture** — async pipeline with decoupled components

## Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Python | >= 3.11 |
| Node.js | >= 18 |
| NVIDIA GPU + CUDA | CUDA 12.8 recommended |
| [uv](https://github.com/astral-sh/uv) | latest |
| [vLLM](https://github.com/vllm-project/vllm) | latest |
| tmux | any |
| HuggingFace token | for pyannote diarization model |

### 1. Install

```bash
git clone <repo-url> && cd yp-record
make install        # installs backend (uv + torch + GPU deps) and frontend (npm)
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in required values:

```bash
# Required
ASR_BASE_URL=http://localhost:8006/v1      # vLLM ASR endpoint
DIARIZATION_HF_TOKEN=hf_your_token_here    # HuggingFace access token
NOTION_API_KEY=secret_your_notion_key       # Notion integration token
NOTION_DATABASE_ID=your_database_id         # Target Notion database

# Optional — enable LLM extraction (transcript polish + meeting notes)
# EXTRACT_ENABLED=true
# EXTRACT_BASE_URL=http://localhost:8000/v1
# EXTRACT_MODEL=cyankiwi/Qwen3.5-9B-AWQ-4bit
```

### 3. Start AI services

```bash
./services.sh start    # launches LLM + ASR vLLM servers in tmux sessions
./services.sh status   # check if services are healthy
```

### 4. Run the app

```bash
make dev    # starts backend (:8080) and frontend (:5173) with hot-reload
```

Open **http://localhost:5173** in your browser.

### Service management

```bash
./services.sh stop            # stop all vLLM services
./services.sh logs asr-vllm   # attach to ASR server logs
./services.sh logs llm-vllm   # attach to LLM server logs
```

## Pipeline

```
Browser Audio ──WebSocket──▸ AudioReceiver
                                │
                          split stereo channels
                                │
                          ┌─────▼─────┐
                          │  Qwen ASR  │  real-time speech-to-text
                          └─────┬─────┘
                                │
                       TranscriptSegments
                          (event bus)
                                │
                    ┌───────────▼───────────┐
                    │   Session ends        │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
      Forced Aligner    Diarization        LLM Extraction
     (word timestamps)  (speaker IDs)   (polish + meeting note)
              │                 │                  │
              └─────────────────┼──────────────────┘
                                ▼
                          Notion Export
```

1. **Audio capture** — PCM audio streamed from browser via WebSocket
2. **ASR** — buffered audio chunks sent to Qwen3-ASR (vLLM) for real-time transcription
3. **On session end** — forced alignment, speaker diarization, and LLM extraction run in parallel
4. **Export** — aligned transcript and meeting notes published to Notion

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ASR_BASE_URL` | `http://localhost:8006/v1` | vLLM ASR server endpoint |
| `ASR_MODEL` | `Qwen/Qwen3-ASR-1.7B` | ASR model name |
| `ASR_TIMEOUT` | `20.0` | ASR request timeout (seconds) |
| `SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `BUFFER_SECONDS` | `3.0` | Audio buffer before ASR call |
| `ALIGNER_ENABLED` | `true` | Enable forced alignment |
| `ALIGNER_MODEL` | `Qwen/Qwen3-ForcedAligner-0.6B` | Aligner model |
| `ALIGNER_DEVICE` | `auto` | Device: `auto`, `cuda`, or `cpu` |
| `ALIGNER_LANGUAGE` | `zh` | Alignment language |
| `ALIGNER_AUTO_ON_SESSION_END` | `true` | Auto-align when session ends |
| `DIARIZATION_ENABLED` | `true` | Enable speaker diarization |
| `DIARIZATION_HF_TOKEN` | — | HuggingFace token (required) |
| `DIARIZATION_DEVICE` | `auto` | Device for diarization model |
| `EXTRACT_ENABLED` | `false` | Enable LLM extraction |
| `EXTRACT_BASE_URL` | `http://localhost:8000/v1` | vLLM LLM server endpoint |
| `EXTRACT_MODEL` | `cyankiwi/Qwen3.5-9B-AWQ-4bit` | LLM model name |
| `EXTRACT_TEMPERATURE` | `0.3` | LLM sampling temperature |
| `EXTRACT_TIMEOUT` | `120.0` | LLM request timeout (seconds) |
| `EXTRACT_AUTO_ON_SESSION_END` | `true` | Auto-extract when session ends |
| `NOTION_API_KEY` | — | Notion integration secret |
| `NOTION_DATABASE_ID` | — | Target Notion database ID |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8080` | Server port |
| `STORAGE_DIR` | `storage/sessions` | Session data directory |
