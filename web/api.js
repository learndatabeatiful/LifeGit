async function call(path, options = {}) {
  const response = await fetch(path, {credentials: "same-origin", ...options});
  const type = response.headers.get("content-type") || "";
  const value = type.includes("application/json")
    ? await response.json()
    : await response.blob();
  if (!response.ok) {
    throw new Error(value.message || `请求失败：${response.status}`);
  }
  return value;
}

function jsonOptions(method, value = {}) {
  return {
    method,
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(value),
  };
}

export const api = {
  bootstrap: () => call("/api/bootstrap"),
  session: id => call(`/api/sessions/${id}`),
  start: value => call("/api/sessions", jsonOptions("POST", value)),
  answer: (id, value) => call(`/api/sessions/${id}/answers`, jsonOptions("POST", value)),
  pause: id => call(`/api/sessions/${id}/pause`, jsonOptions("POST")),
  resume: id => call(`/api/sessions/${id}/resume`, jsonOptions("POST")),
  complete: id => call(`/api/sessions/${id}/complete`, jsonOptions("POST")),
  updateCard: (id, value) => call(`/api/sessions/${id}/card`, jsonOptions("PATCH", value)),
  exportCard: (id, blob) => call(`/api/sessions/${id}/card-export`, {
    method: "POST",
    headers: {"Content-Type": "image/png"},
    body: blob,
  }),
  privacyReview: (id, value) => call(
    `/api/sessions/${id}/privacy-reviews`,
    jsonOptions("POST", value),
  ),
  confirmPrivacy: (id, reviewId) => call(
    `/api/sessions/${id}/privacy-reviews/${reviewId}/confirm`,
    jsonOptions("POST"),
  ),
  createJob: (id, value) => call(`/api/sessions/${id}/jobs`, jsonOptions("POST", value)),
  job: jobId => call(`/api/jobs/${jobId}`),
  jobAsset: jobId => call(`/api/jobs/${jobId}/asset`),
};
