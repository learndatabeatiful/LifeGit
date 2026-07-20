import test from "node:test";
import assert from "node:assert/strict";
import {sessionRecoveryTargets} from "./session-routing.js";


test("offers both unfinished and completed sessions as recovery targets", () => {
  const sessions = [
    {session_id: "ses_done", status: "completed", anchor: "看见海的那一天"},
    {session_id: "ses_active", status: "active", anchor: "还在写的片段"},
  ];

  assert.deepEqual(sessionRecoveryTargets(sessions), {
    resumable: sessions[1],
    completed: sessions[0],
  });
});
