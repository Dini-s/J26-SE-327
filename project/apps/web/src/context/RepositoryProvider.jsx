import { useCallback, useEffect, useState } from "react";
import { RepositoryContext } from "./RepositoryContext";
import {
  analyzeRepository as analyzeRequest,
  cloneRepository as cloneRequest,
  getRepositories,
  registerRepository as registerRequest,
} from "../services/repositoryService";

const RepositoryProvider = ({ children }) => {
  const [repositories, setRepositories] = useState([]);
  const [selectedRepository, setSelectedRepository] = useState(null);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [loadingRepositories, setLoadingRepositories] = useState(false);

  const refreshRepositories = useCallback(async () => {
    setLoadingRepositories(true);
    try {
      const list = await getRepositories();
      setRepositories(list);
      setSelectedRepository((current) =>
        current
          ? list.find((r) => r.id === current.id) || current
          : list[0] || null,
      );
      return list;
    } catch (error) {
      setAnalysisError(error.message || "Could not load repositories.");
      throw error;
    } finally {
      setLoadingRepositories(false);
    }
  }, []);

  useEffect(() => {
    refreshRepositories().catch(() => {});
  }, [refreshRepositories]);

  const selectRepository = useCallback((repository) => {
    setSelectedRepository(repository);
    setAnalysisResults(null);
    setAnalysisError("");
  }, []);

  const analyzeRepository = useCallback(
    async (repositoryId = selectedRepository?.id) => {
      if (!repositoryId) {
        const message = "Select a repository before running analysis.";
        setAnalysisError(message);
        throw new Error(message);
      }
      setAnalyzing(true);
      setAnalysisError("");
      try {
        const result = await analyzeRequest(repositoryId);
        setAnalysisResults(result);
        return result;
      } catch (error) {
        setAnalysisError(error.message || "Repository analysis failed.");
        throw error;
      } finally {
        setAnalyzing(false);
      }
    },
    [selectedRepository?.id],
  );

  const registerRepository = useCallback(
    async (data) => {
      const created = await registerRequest(data);
      await refreshRepositories();
      const repository = created?.repository || created;
      if (repository?.id) selectRepository(repository);
      return repository;
    },
    [refreshRepositories, selectRepository],
  );

  const cloneRepository = useCallback(
    async (id) => {
      const result = await cloneRequest(id);
      await refreshRepositories();
      return result;
    },
    [refreshRepositories],
  );

  return (
    <RepositoryContext.Provider
      value={{
        repositories,
        selectedRepository,
        setSelectedRepository,
        selectRepository,
        analysisResults,
        setAnalysisResults,
        analyzing,
        setAnalyzing,
        analysisError,
        setAnalysisError,
        loadingRepositories,
        refreshRepositories,
        analyzeRepository,
        registerRepository,
        cloneRepository,
      }}
    >
      {children}
    </RepositoryContext.Provider>
  );
};

export default RepositoryProvider;
