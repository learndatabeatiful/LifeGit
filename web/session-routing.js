export function sessionRecoveryTargets(sessions = []) {
  return {
    resumable: sessions.find(item => ["active", "paused"].includes(item.status)) || null,
    completed: sessions.find(item => item.status === "completed") || null,
  };
}
