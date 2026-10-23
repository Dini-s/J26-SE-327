
import {
  CalendarDays,
  Database,
  Play,
  RefreshCw,
} from "lucide-react";
import { useState,useEffect } from "react";

import { useRepository } from "../../context/RepositoryContext";
import { analyzeRepository } from "../../services/repositoryApi";

const ContentHeader = ({ title, subtitle, onRefresh }) => {
  const [refreshing, setRefreshing] = useState(false);

  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const intervalId = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(intervalId);
  }, []);

  const formattedDateTime = new Intl.DateTimeFormat("en-LK", {
    timeZone: "Asia/Colombo",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(currentTime);

  const {
    selectedRepository,
    analysisResults,
    setAnalysisResults,
    analyzing,
    setAnalyzing,
    setAnalysisError,
    analysisError,
  } = useRepository();

  const handleRefresh = async () => {
    if (onRefresh) {
      setRefreshing(true);
      try {
        await onRefresh();
      } finally {
        setRefreshing(false);
      }
      return;
    }

    // Refresh the current page's displayed state.
    setRefreshing(true);
    window.setTimeout(() => setRefreshing(false), 500);
  };

  const handleAnalyze = async () => {
    if (!selectedRepository?.id) {
      setAnalysisError("Please select a repository before analyzing.");
      return;
    }

    setAnalyzing(true);
    setAnalysisError("");

    try {
      const result = await analyzeRepository(selectedRepository.id);
      setAnalysisResults(result);
    } catch (error) {
      setAnalysisError(error.message || "Repository analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">
          {title}
        </h1>
        <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-[10px] font-medium text-slate-700 shadow-sm">
          <Database size={14} className="text-indigo-600" />
          <span>
            {selectedRepository?.name || "No repository selected"}
          </span>
        </div>

        <CalendarDays size={14} className="text-slate-500" />
        {formattedDateTime}

        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-[10px] font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-600 disabled:opacity-50"
        >
          <RefreshCw
            size={14}
            className={refreshing ? "animate-spin" : ""}
          />
          Refresh
        </button>

        <button
          type="button"
          onClick={handleAnalyze}
          disabled={analyzing || !selectedRepository?.id}
          className="flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-4 text-[10px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play size={13} fill="currentColor" />
          {analyzing ? "Analyzing..." : "Analyze Repository"}
        </button>
      </div>

      {analysisError && (
        <p className="text-xs text-red-600">{analysisError}</p>
      )}
    </div>
  );
};

export default ContentHeader;
