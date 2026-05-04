#!/usr/bin/env python3
"""Run a bounded OpenClaw smoke turn through ReachyClaw's gateway bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from reachy_mini_openclaw.config import config  # noqa: E402
from reachy_mini_openclaw.openclaw_bridge import OpenClawBridge  # noqa: E402

REACHY_BODY_CONTEXT = """\
User is talking to you through your Reachy Mini robot body. Keep responses concise for voice.

You can control your robot body by including action tags anywhere in your response.
The tags will be executed and stripped before your words are spoken aloud.

Available actions:
  [LOOK:left]  [LOOK:right]  [LOOK:up]  [LOOK:down]  [LOOK:front]
  [EMOTION:happy]  [EMOTION:sad]  [EMOTION:surprised]  [EMOTION:curious]  [EMOTION:thinking]  [EMOTION:confused]  [EMOTION:excited]
  [DANCE:happy]  [DANCE:excited]  [DANCE:wave]  [DANCE:nod]  [DANCE:shake]  [DANCE:bounce]
  [CAMERA]
  [FACE_TRACKING:on]  [FACE_TRACKING:off]
  [STOP]
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke test ReachyClaw's OpenClaw gateway path.",
    )
    parser.add_argument(
        "--message",
        default="ReachyClaw smoke test: say who you are in one short sentence.",
        help="Message to send to OpenClaw.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=config.OPENCLAW_VOICE_TIMEOUT,
        help="Response timeout in seconds.",
    )
    parser.add_argument(
        "--agent-id",
        default=config.OPENCLAW_AGENT_ID,
        help="OpenClaw agent ID.",
    )
    parser.add_argument(
        "--session-key",
        default=config.OPENCLAW_SESSION_KEY,
        help="OpenClaw session key.",
    )
    parser.add_argument(
        "--gateway-url",
        default=config.OPENCLAW_GATEWAY_URL,
        help="OpenClaw gateway URL.",
    )
    parser.add_argument(
        "--include-body-context",
        action="store_true",
        help="Prefix the same Reachy body context used by live voice turns.",
    )
    return parser


async def run_smoke(args: argparse.Namespace) -> dict:
    bridge = OpenClawBridge(
        gateway_url=args.gateway_url,
        agent_id=args.agent_id,
        timeout=args.timeout,
    )
    bridge.session_key = args.session_key

    trace_id = f"smoke.{uuid.uuid4().hex[:12]}"
    started_at = time.monotonic()
    connected = await bridge.connect()
    connect_elapsed_ms = int((time.monotonic() - started_at) * 1000)
    if not connected:
        return {
            "ok": False,
            "trace_id": trace_id,
            "agent_id": args.agent_id,
            "session_key": args.session_key,
            "connect_elapsed_ms": connect_elapsed_ms,
            "error": "OpenClaw gateway connection failed",
        }

    try:
        response = await bridge.chat(
            args.message,
            system_context=REACHY_BODY_CONTEXT if args.include_body_context else None,
            timeout=args.timeout,
            trace_id=trace_id,
        )
        total_elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "ok": response.error is None,
            "trace_id": trace_id,
            "agent_id": args.agent_id,
            "session_key": args.session_key,
            "connect_elapsed_ms": connect_elapsed_ms,
            "openclaw_elapsed_ms": response.elapsed_ms,
            "total_elapsed_ms": total_elapsed_ms,
            "run_id": response.run_id,
            "idempotency_key": response.idempotency_key,
            "error": response.error,
            "content": response.content,
        }
    finally:
        await bridge.disconnect()


async def main_async() -> int:
    args = build_parser().parse_args()
    result = await run_smoke(args)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
