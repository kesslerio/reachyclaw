---
title: ReachyClaw
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: static
pinned: false
short_description: OpenClaw AI agent with a Reachy Mini robot body
tags:
 - reachy_mini
 - reachy_mini_python_app
 - openclaw
 - robotics
 - embodied-ai
 - ai-assistant
 - openai-realtime
 - voice-assistant
 - conversational-ai
 - physical-ai
 - robot-body
 - speech-to-speech
 - multimodal
 - vision
 - expressive-robot
 - face-tracking
 - human-robot-interaction
---

# ReachyClaw

**Your OpenClaw AI agent, embodied in a Reachy Mini robot.**

ReachyClaw makes OpenClaw the actual brain of a Reachy Mini robot. Unlike typical setups where GPT-4o handles conversations and only calls OpenClaw occasionally, ReachyClaw routes **every** user message through OpenClaw. The robot speaks, moves, and sees — all controlled by your OpenClaw agent.

Realtime voice APIs are used purely for voice I/O (speech-to-text and text-to-speech). OpenAI Realtime remains the default provider, and Gemini Live can be selected for lower-cost audio. Your OpenClaw agent decides what to say **and** how the robot moves.

## Architecture

```
User speaks -> Realtime voice provider (STT only)
            -> Provider calls ask_openclaw with the user's message
            -> OpenClaw (the actual brain) responds with text + action tags
            -> ReachyClaw parses action tags -> robot moves (emotions, look, dance)
            -> Clean text -> Realtime voice provider (TTS only) -> Robot speaks
```

OpenClaw can include action tags like `[EMOTION:happy]`, `[LOOK:left]`, `[DANCE:excited]` in its responses. These are parsed and executed on the robot, then stripped so only the spoken words go to TTS.

## Features

- **OpenClaw is the brain** — every message goes through your OpenClaw agent, not GPT-4o
- **Full body control** — OpenClaw controls head movement, emotions, dances, and camera
- **Real-time voice** — OpenAI Realtime or Gemini Live for low-latency speech I/O
- **Face tracking** — robot tracks your face and maintains eye contact
- **Camera vision** — robot can see through its camera and describe what it sees
- **Conversation memory** — OpenClaw maintains full context across sessions and channels
- **Works with simulator** — no physical robot required

## Available Robot Actions

OpenClaw can use these action tags in responses:

| Action | Tags |
|--------|------|
| **Look** | `[LOOK:left]` `[LOOK:right]` `[LOOK:up]` `[LOOK:down]` `[LOOK:front]` |
| **Emotion** | `[EMOTION:happy]` `[EMOTION:sad]` `[EMOTION:surprised]` `[EMOTION:curious]` `[EMOTION:thinking]` `[EMOTION:confused]` `[EMOTION:excited]` |
| **Dance** | `[DANCE:happy]` `[DANCE:excited]` `[DANCE:wave]` `[DANCE:nod]` `[DANCE:shake]` `[DANCE:bounce]` |
| **Camera** | `[CAMERA]` |
| **Face Tracking** | `[FACE_TRACKING:on]` `[FACE_TRACKING:off]` |
| **Stop** | `[STOP]` |

## Prerequisites

### Option A: With Physical Robot
- [Reachy Mini](https://www.pollen-robotics.com/reachy-mini/) robot (Wireless or Lite)

### Option B: With Simulator
- Any computer with Python 3.11+
- Install: `pip install "reachy-mini[mujoco]"`

### Software (Both Options)
- Python 3.11+
- [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini)
- [OpenClaw](https://github.com/openclaw/openclaw) gateway running
- OpenAI API key with Realtime API access or Gemini API key with Live API access

## Installation

### From the Reachy Mini App Store (recommended)

Install ReachyClaw directly from the Reachy Mini Control app. After installation, you must create a `.env` config file inside the app's venv so it can connect to your realtime voice provider and OpenClaw gateway.

The file goes here (on macOS):

```
~/Library/Application Support/com.pollen-robotics.reachy-mini/reachyclaw_venv/lib/python3.12/.env
```

Create it with:

```bash
cat > ~/Library/Application\ Support/com.pollen-robotics.reachy-mini/reachyclaw_venv/lib/python3.12/.env << EOF
OPENAI_API_KEY=sk-...your-key...
REALTIME_PROVIDER=openai
OPENCLAW_GATEWAY_URL=ws://localhost:18789
OPENCLAW_TOKEN=your-gateway-token
OPENCLAW_AGENT_ID=main
EOF
```

**Where to find these values:**

- **`OPENAI_API_KEY`** — from [platform.openai.com/api-keys](https://platform.openai.com/api-keys). If you already have the Conversation app installed, you can copy the key from its `.env` file (same parent directory, under `conversation_venv`).
- **`REALTIME_PROVIDER`** — `openai` by default, or `gemini` to use Gemini Live.
- **`GEMINI_API_KEY`** — from [Google AI Studio](https://aistudio.google.com/app/apikey), required only when `REALTIME_PROVIDER=gemini`.
- **`OPENCLAW_TOKEN`** — your gateway auth token, found in `~/.openclaw/openclaw.json` under `gateway.auth.token`.
- **`OPENCLAW_GATEWAY_URL`** — defaults to `ws://localhost:18789` if OpenClaw runs on the same machine.

That's it — launch ReachyClaw from the app and it will work.

### From Source (CLI / development)

```bash
# Clone ReachyClaw
git clone https://github.com/EdLuxAI/reachyclaw
cd reachyclaw

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install
pip install -e ".[mediapipe_vision]"

# Configure
cp .env.example .env
# Edit .env with your keys
```

## Configuration

Edit `.env` (see `.env.example` for all options):

```bash
# Realtime voice provider (required)
REALTIME_PROVIDER=openai

# OpenAI provider
OPENAI_API_KEY=sk-...your-key...
OPENAI_MODEL=gpt-4o-realtime-preview-2024-12-17
OPENAI_VOICE=cedar

# Gemini provider
# REALTIME_PROVIDER=gemini
# GEMINI_API_KEY=...your-key...
# GEMINI_MODEL=gemini-3.1-flash-live-preview
# GEMINI_VOICE=Kore

# OpenClaw Gateway (required)
OPENCLAW_GATEWAY_URL=ws://localhost:18789
OPENCLAW_TOKEN=your-gateway-token       # from ~/.openclaw/openclaw.json → gateway.auth.token
OPENCLAW_AGENT_ID=main
OPENCLAW_SESSION_KEY=main
OPENCLAW_VOICE_TIMEOUT=25
REACHYCLAW_TRACE_LATENCY=false

ENABLE_FACE_TRACKING=true
HEAD_TRACKER_TYPE=mediapipe
```

### Realtime Provider Notes

OpenAI Realtime and Gemini Live both act as voice relays. They should call `ask_openclaw` for every user utterance, wait for OpenClaw, and speak the returned answer verbatim.

Gemini Live uses raw 16-bit PCM audio. Its native input rate is 16 kHz and output is 24 kHz, so ReachyClaw resamples microphone input before sending it to Gemini and plays Gemini output at 24 kHz. Gemini Live is currently a preview API; validate turn-taking, interruption behavior, voice quality, and tool-call reliability on your robot before making it your default.

### Latency and Dedicated OpenClaw Agents

For a robot that should know one user's identity while staying responsive, use a dedicated OpenClaw agent such as `niemand-family-reachyclaw`. Keep that agent's workspace pointed at the source identity files (`AGENTS.md`, `USER.md`, `SOUL.md`, `MEMORY.md`) instead of copying personal context into ReachyClaw.

Voice turns can be bounded with `OPENCLAW_VOICE_TIMEOUT` and traced with `REACHYCLAW_TRACE_LATENCY=true`. Tracing emits correlated `traceId`, OpenClaw `runId`, idempotency key, and elapsed-millisecond log lines around provider tool calls, OpenClaw acknowledgement, first OpenClaw event, final OpenClaw response, and local body-action execution.

Dynamic memory search can dominate voice latency. For a dedicated robot route, prefer an OpenClaw per-agent memory override that disables or tightly bounds memory search for the robot agent while identity continues to come from the workspace bootstrap files.

Run a gateway-only smoke test before debugging the realtime provider:

```bash
python scripts/reachyclaw-smoke-openclaw.py \
  --agent-id niemand-family-reachyclaw \
  --session-key reachyclaw \
  --gateway-url ws://localhost:18789 \
  --timeout 25 \
  --include-body-context
```

See [docs/reachyclaw-latency-smoke.md](docs/reachyclaw-latency-smoke.md) for log interpretation and OpenClaw agent configuration notes.

## Usage

### With Simulator

```bash
# Terminal 1: Start simulator
reachy-mini-daemon --sim

# Terminal 2: Run ReachyClaw
reachyclaw --gradio
```

### With Physical Robot

```bash
reachyclaw

# With debug logging
reachyclaw --debug

# With specific robot
reachyclaw --robot-name my-reachy
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--gradio` | Launch web UI instead of console mode |
| `--robot-name NAME` | Specify robot name for connection |
| `--gateway-url URL` | OpenClaw gateway URL |
| `--no-camera` | Disable camera functionality |
| `--no-openclaw` | Disable OpenClaw integration |
| `--head-tracker TYPE` | Face tracker: `mediapipe` or `yolo` |
| `--no-face-tracking` | Disable face tracking |

## How It Differs from ClawBody

ClawBody (the stock app) uses GPT-4o as the brain and only calls OpenClaw occasionally for tools like calendar or weather. ReachyClaw inverts this:

| | ClawBody | ReachyClaw |
|---|---|---|
| **Brain** | GPT-4o (with OpenClaw context snapshot) | OpenClaw (every message) |
| **Body control** | GPT-4o decides movements | OpenClaw decides movements |
| **Startup** | 20-30s context fetch from OpenClaw | Instant (no context fetch needed) |
| **Memory** | Stale snapshot from startup | Live OpenClaw memory |
| **Realtime model role** | Full agent | Voice relay only |

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Acknowledgments

Built on top of:

- [Pollen Robotics](https://www.pollen-robotics.com/) — Reachy Mini robot, SDK, and simulator
- [OpenClaw](https://github.com/openclaw/openclaw) — AI agent framework
- [OpenAI](https://openai.com/) — Realtime API for voice I/O
- [Google Gemini](https://ai.google.dev/gemini-api/docs/live-api) — Live API for voice I/O
- [ClawBody](https://github.com/tomrikert/clawbody) — Original Reachy Mini + OpenClaw app (Apache 2.0)
