# ReachyClaw Latency Smoke Test

Use this when the realtime voice provider can hear and speak, but ReachyClaw feels slow or you need to prove the OpenClaw route is working.

## Runtime Settings

Set these in the ReachyClaw `.env`:

```bash
REALTIME_PROVIDER=gemini
OPENCLAW_AGENT_ID=niemand-family-reachyclaw
OPENCLAW_SESSION_KEY=reachyclaw
OPENCLAW_VOICE_TIMEOUT=25
REACHYCLAW_TRACE_LATENCY=true
```

`OPENCLAW_VOICE_TIMEOUT` bounds one voice turn waiting on OpenClaw. `REACHYCLAW_TRACE_LATENCY=true` adds correlated log lines with `traceId`, OpenClaw `runId`, idempotency key, and elapsed milliseconds.

## Smoke Test

Run from the repo on the robot or any machine that can reach the gateway:

```bash
python scripts/reachyclaw-smoke-openclaw.py \
  --agent-id niemand-family-reachyclaw \
  --session-key reachyclaw \
  --gateway-url ws://localhost:18789 \
  --timeout 25 \
  --include-body-context
```

The script prints JSON. A healthy result has `"ok": true`, a non-empty `run_id`, no `error`, and `openclaw_elapsed_ms` below the configured timeout.

## Reading Logs

With tracing enabled, the useful sequence is:

```text
Voice trace tool_start ...
OpenClaw trace start ...
OpenClaw trace ack ...
OpenClaw trace first_event ...
OpenClaw trace complete ...
Voice trace openclaw_done ...
Voice trace actions_done ...
Voice trace tool_done ...
```

Interpretation:

- Slow before `OpenClaw trace ack`: gateway connection or request acceptance.
- Slow between `ack` and `first_event`: OpenClaw agent startup, memory search, tool bootstrap, or model queueing.
- Slow between `first_event` and `complete`: model generation or OpenClaw tools.
- Slow after `openclaw_done`: local robot action dispatch or realtime provider tool-response handling.

## Dedicated Robot Agent

For a personal robot route, use a dedicated OpenClaw agent such as `niemand-family-reachyclaw` with the family workspace as its source of identity. The agent should read identity from the workspace bootstrap files (`AGENTS.md`, `USER.md`, `SOUL.md`, `MEMORY.md`) instead of copying that identity into ReachyClaw.

For low-latency voice turns, avoid slow dynamic memory on this robot agent. Prefer a per-agent memory override in OpenClaw, for example:

```json
{
  "id": "niemand-family-reachyclaw",
  "workspace": "/home/art/niemand-family",
  "model": {
    "primary": "ollama/deepseek-v4-flash:cloud"
  },
  "memorySearch": {
    "enabled": false
  }
}
```

If memory search must stay enabled, keep it bounded and disable session memory for this agent so the voice path does not wait on large cross-session searches.
