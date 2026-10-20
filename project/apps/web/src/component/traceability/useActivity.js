import { useEffect, useRef } from "react";
import { useApi } from "../../api/c4";

/** What the Python API is doing right now (linking or re-checking). `onFinished` runs once when a job ends. */
export function useActivity(onFinished) {
  const api = useApi("/api/activity", { pollMs: 2500 });
  const busy = api.data ? api.data.state !== "idle" : false;
  const was = useRef(false);
  useEffect(() => {
    if (was.current && !busy && onFinished) onFinished();
    was.current = busy;
  }, [busy, onFinished]);
  return { activity: api.data, busy, error: api.error, reload: api.reload };
}
