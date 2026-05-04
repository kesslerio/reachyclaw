---
title: fix: Address Gemini Live review feedback
type: fix
status: active
date: 2026-05-04
---

# fix: Address Gemini Live review feedback

## Summary

This plan defines PR #2 after the Gemini Live integration merge: fix the two P1 Codex review findings from PR #1, add targeted regression coverage, and keep lint cleanup scoped to files touched by those fixes.

---

## Problem Frame

PR #1 merged Gemini Live support into the fork, but the post-merge review identified two correctness risks in the realtime voice path: OpenClaw chat turns can exceed the configured voice timeout, and Gemini microphone suppression can clear before the model turn is truly complete. Both issues can directly affect perceived latency and second-turn reliability on the robot.

---

## Requirements

- R1. OpenClaw voice chat calls must enforce `OPENCLAW_VOICE_TIMEOUT` as an absolute end-to-end budget for the turn after `chat.send` starts, not as a fresh timeout for each streamed event.
- R2. Gemini microphone input suppression must not clear on assistant transcription alone; it must remain active until Gemini reports turn completion, interruption, or a bounded safety timeout.
- R3. The fixes must preserve existing OpenClaw bridge response handling for normal final responses, partial streamed text, ack failures, and timeout failures.
- R4. The fixes must preserve Gemini transcript emission and OpenClaw conversation sync without reopening the microphone while assistant audio may still be playing.
- R5. The PR should keep Ruff cleanup targeted to files touched by these behavior fixes, leaving repo-wide mechanical lint cleanup for a separate PR.
- R6. The non-hardware test suite must continue to pass.

---

## Scope Boundaries

- This PR should not attempt a full repo-wide Ruff cleanup.
- This PR should not redesign Gemini Live or OpenAI Realtime provider abstractions.
- This PR should not change model selection, credentials, OpenClaw agent/session routing, or robot deployment configuration.
- This PR should not claim the live two-turn robot bug is fixed until a fresh robot smoke test proves two consecutive turns work.
- This PR should not prepare an upstream `EdLuxAI/reachyclaw` PR; it targets the fork first.

### Deferred to Follow-Up Work

- Repo-wide Ruff cleanup: open a separate mechanical PR after the behavior fixes land.
- Live robot validation/follow-up: if two-turn voice still fails after these fixes, use the added diagnostics to create a focused runtime debugging PR.
- Upstream splitting: after fork fixes settle, split into small upstream-friendly PRs for `EdLuxAI/reachyclaw`.
- Development dependency cleanup: handle the `pip install -e ".[dev]"` native `PyGObject`/`pycairo` issue separately unless this PR needs a tiny docs note.

---

## Context & Research

### Relevant Code and Patterns

- `src/reachy_mini_openclaw/openclaw_bridge.py` registers a per-run event queue and currently waits for streamed events inside a loop with the full `request_timeout` on every `event_queue.get()`.
- `src/reachy_mini_openclaw/gemini_live.py` currently calls `_clear_input_suppression("assistant_transcript")` from `_emit_assistant_transcript()`, before `_handle_turn_complete()` has necessarily run.
- `tests/test_openclaw_bridge.py` already covers OpenClaw bridge request/response behavior and should be extended for absolute timeout semantics.
- `tests/test_gemini_live_handler.py` already covers suppression, transcript emission, and Gemini send-failure logging and should be extended for turn-completion suppression semantics.
- `pyproject.toml` configures Ruff; current repo-wide Ruff debt is substantial, so this PR should only require touched-file cleanliness rather than performing all mechanical cleanup.

### PR Review Findings

- P1: OpenClaw streaming uses `request_timeout` for each individual event wait, allowing long-running streams with intermediate events to exceed the configured voice timeout.
- P1: Gemini suppression clears when output transcription finishes, but transcription can arrive before audio playback or turn completion, reopening the mic while the assistant is still speaking.

### Institutional Learnings

- No repo-local or shared `docs/solutions/` entries were found for ReachyClaw Gemini timeout/suppression handling.

### External References

- GitHub PR review: `https://github.com/kesslerio/reachyclaw/pull/1#pullrequestreview-4217866576`

---

## Key Technical Decisions

- Fix review feedback before broad lint cleanup. These are P1 behavior issues in the robot voice path, while Ruff cleanup is mechanical and can wait.
- Use one absolute monotonic deadline per OpenClaw chat turn. Each event wait should use the remaining budget, so intermediate lifecycle/assistant events cannot reset the overall timeout.
- Preserve useful partial responses only when the absolute deadline expires after some assistant text was received, matching the current intent to avoid throwing away partial spoken output.
- Keep Gemini suppression active across transcript emission. Transcript emission should update UI/log/OpenClaw sync state, but turn completion/interruption/timeout should own the microphone reopening decision.
- Keep a bounded suppression safety timeout so a missing Gemini completion event does not leave the robot permanently deaf.
- Keep Ruff cleanup local to files touched by the behavior fixes; do not use this PR as a full formatting sweep.

---

## Open Questions

### Resolved During Planning

- Should the review comments be active PR #2 scope or deferred? Active scope, because both comments are P1 and affect latency/second-turn reliability.
- Should full repo Ruff cleanup stay in this plan? No. It is deferred to keep PR #2 reviewer-friendly and behavior-focused.

### Deferred to Implementation

- Exact helper shape for computing remaining OpenClaw timeout budget; choose the simplest local expression that keeps the streaming loop readable.
- Exact Gemini suppression state naming; choose names that make the transcript-vs-turn-completion distinction obvious without introducing a larger state machine.
- Whether a live robot smoke test after implementation proves the second turn or only narrows the next failure source.

---

## Implementation Units

- U1. **Enforce absolute OpenClaw turn deadlines**

**Goal:** Ensure one OpenClaw voice turn cannot exceed the configured timeout budget just because intermediate events keep arriving.

**Requirements:** R1, R3, R6

**Dependencies:** None

**Files:**
- Modify: `src/reachy_mini_openclaw/openclaw_bridge.py`
- Test: `tests/test_openclaw_bridge.py`

**Approach:**
- Establish a single monotonic deadline for the chat turn after the `chat.send` request begins.
- Inside the streaming event loop, compute remaining time before each queue wait.
- If the remaining budget is exhausted, follow the existing timeout behavior: return a timeout error when no assistant text exists, or break and return partial text when assistant text exists.
- Keep trace logging tied to total elapsed time, not per-event wait duration.

**Patterns to follow:**
- Existing `started_at`, `elapsed_ms`, and trace logging in `OpenClawBridge.chat()`.
- Existing partial-text handling in the timeout path.

**Test scenarios:**
- Happy path: a final chat event arriving before the absolute deadline returns the final text with no error.
- Edge case: multiple non-final events arrive before the deadline, but no final/end event arrives before the total budget expires; the bridge times out based on total elapsed budget, not the last event time.
- Edge case: assistant text arrives before the deadline, then the deadline expires before final/end; the bridge returns the partial text rather than an empty timeout response.
- Error path: no assistant text arrives before the absolute deadline; the bridge returns `error="Response timeout"` with the run id and elapsed metadata.

**Verification:**
- OpenClaw bridge tests prove the event loop cannot extend the turn indefinitely with repeated intermediate events.
- Existing bridge behavior for ack failures and normal final responses remains intact.

---

- U2. **Keep Gemini mic suppression until turn completion**

**Goal:** Prevent Gemini output transcription from reopening microphone streaming before assistant audio/turn completion is done.

**Requirements:** R2, R4, R6

**Dependencies:** None

**Files:**
- Modify: `src/reachy_mini_openclaw/gemini_live.py`
- Test: `tests/test_gemini_live_handler.py`

**Approach:**
- Stop clearing input suppression from assistant transcript emission.
- Keep transcript emission responsible only for logging, UI output, and last-assistant-response state.
- Clear suppression from Gemini turn completion, interruption, and the existing safety timeout path.
- Preserve OpenClaw conversation sync after turn completion so memory continuity still sees the completed user/assistant pair.

**Patterns to follow:**
- Existing `_handle_turn_complete()`, `_handle_interrupted()`, `_is_input_suppressed()`, and `_trace_input_frames()` helpers.
- Existing Gemini handler tests using dummy connections and `SimpleNamespace` event payloads.

**Test scenarios:**
- Happy path: output transcription finishes while suppression is active; the assistant transcript is emitted, but `_is_input_suppressed()` still returns true immediately afterward.
- Happy path: turn completion after transcription clears suppression and syncs the conversation state.
- Error path: interruption clears suppression and queued audio as it does today.
- Edge case: suppression safety timeout expires without turn completion; suppression clears via the timeout path so the robot does not stay deaf permanently.

**Verification:**
- Tests prove transcription alone does not reopen the mic.
- Existing audio queueing/tool-call tests continue to pass.

---

- U3. **Run targeted Ruff cleanup on touched files**

**Goal:** Keep the behavior-fix PR tidy without absorbing the full repo-wide mechanical Ruff cleanup.

**Requirements:** R5, R6

**Dependencies:** U1, U2

**Files:**
- Modify: `src/reachy_mini_openclaw/openclaw_bridge.py`
- Modify: `src/reachy_mini_openclaw/gemini_live.py`
- Modify: `tests/test_openclaw_bridge.py`
- Modify: `tests/test_gemini_live_handler.py`

**Approach:**
- Run Ruff against the files modified by U1 and U2.
- Apply only cleanup directly caused by or adjacent to the behavior fixes in those files.
- Do not reformat unrelated modules or perform a repository-wide mechanical sweep in this PR.

**Patterns to follow:**
- Existing `pyproject.toml` Ruff configuration.

**Test scenarios:**
- Test expectation: none -- this unit is lint hygiene for files already covered by U1/U2 tests.

**Verification:**
- Touched files pass Ruff or have only pre-existing findings explicitly called out in the PR description.
- The PR diff remains reviewable as a behavior fix, not a broad formatting change.

---

- U4. **Verify non-hardware regressions and document PR status**

**Goal:** Prove the fixes are covered locally and leave clear follow-up notes for live robot validation.

**Requirements:** R3, R4, R5, R6

**Dependencies:** U1, U2, U3

**Files:**
- Test: `tests/test_audio.py`
- Test: `tests/test_config.py`
- Test: `tests/test_gemini_live_handler.py`
- Test: `tests/test_openclaw_bridge.py`
- Test: `tests/test_realtime_provider.py`

**Approach:**
- Run the existing non-hardware pytest suite after the behavior and targeted lint fixes.
- If practical, deploy the changed runtime files to the robot and perform a two-turn smoke test; if not practical in the PR implementation pass, clearly mark live validation as pending.
- Update the PR description with the review comments addressed, tests run, touched-file Ruff status, and live robot validation status.

**Patterns to follow:**
- PR #1 testing notes and `docs/reachyclaw-latency-smoke.md`.

**Test scenarios:**
- Integration: Gemini handler tests cover suppression, transcript emission, turn completion, interruption, tool calls, and audio queueing.
- Integration: OpenClaw bridge tests cover final response, absolute timeout, partial streamed text, and no-text timeout.
- Regression: full non-hardware pytest suite passes.

**Verification:**
- The PR description can honestly state that both Codex review P1s were addressed.
- Any remaining live robot uncertainty is explicit rather than implied fixed.

---

## System-Wide Impact

- **Interaction graph:** Gemini Live, OpenClaw bridge, robot mic capture, playback, and OpenClaw conversation sync are affected. OpenAI Realtime should remain behaviorally unchanged except for shared tests or lint if touched.
- **Error propagation:** OpenClaw timeout errors must remain visible to the voice relay and trace logs. Gemini interruption and timeout recovery must keep clearing suppression.
- **State lifecycle risks:** The main risk is leaving suppression active too long if Gemini omits turn completion. The existing bounded safety timeout remains the fallback.
- **API surface parity:** No environment variables, CLI flags, public entry points, or app entry points should change.
- **Integration coverage:** Unit tests should cover the exact review scenarios; live robot testing is still needed for end-to-end confidence.
- **Unchanged invariants:** Provider selection, OpenClaw credentials, OpenClaw agent/session routing, Gemini/OpenAI model configuration, and audio sample-rate conversion stay as merged in PR #1.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Absolute timeout starts at the wrong moment and shortens the useful OpenClaw budget too much | Define the deadline around the existing `started_at`/request timeout semantics and assert elapsed behavior in tests |
| Partial text behavior changes unexpectedly | Add a test where assistant text arrives before timeout but final/end does not |
| Suppression remains active after Gemini omits turn completion | Keep the safety timeout path and test it |
| Transcript no longer reaches UI/OpenClaw sync | Keep transcript emission separate from suppression clearing and test turn completion sync behavior |
| Ruff cleanup expands the PR beyond the review fixes | Restrict lint cleanup to files touched by U1/U2 and defer repo-wide cleanup |

---

## Documentation / Operational Notes

- PR #2 should reference the two Codex review comments from PR #1.
- `docs/reachyclaw-latency-smoke.md` does not need to change unless implementation changes the interpretation of trace logs.
- If live robot testing is performed, record whether two consecutive turns worked and include any relevant trace snippets in the PR description.

---

## Sources & References

- Related PR: `https://github.com/kesslerio/reachyclaw/pull/1`
- Related review: `https://github.com/kesslerio/reachyclaw/pull/1#pullrequestreview-4217866576`
- Related code: `src/reachy_mini_openclaw/openclaw_bridge.py`
- Related code: `src/reachy_mini_openclaw/gemini_live.py`
- Related tests: `tests/test_openclaw_bridge.py`, `tests/test_gemini_live_handler.py`
- Related docs: `docs/reachyclaw-latency-smoke.md`
