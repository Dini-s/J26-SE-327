import { useEffect, useState } from "react";

export function useQualityData(loader) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    Promise.resolve().then(loader)
      .then((value) => { if (active) setData(value); })
      .catch((reason) => { if (active) setError(reason.message || "The request failed."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [loader]);
  const refresh = async () => {
    setLoading(true);
    setError("");
    try { setData(await loader()); return true; }
    catch (reason) { setError(reason.message || "The request failed."); return false; }
    finally { setLoading(false); }
  };
  return { data, error, loading, refresh };
}

