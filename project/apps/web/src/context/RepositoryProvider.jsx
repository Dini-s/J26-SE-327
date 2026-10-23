import { useState } from "react";
import { RepositoryContext } from "./RepositoryContext";


const RepositoryProvider = ({ children }) => {
  const [selectedRepository, setSelectedRepository] = useState(null);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  const selectRepository = (repository) => {
    setSelectedRepository(repository);
    setAnalysisResults(null);
    setAnalysisError("");
  };

  return (
    <RepositoryContext.Provider
      value={{
        selectedRepository,
        setSelectedRepository,
        selectRepository,
        analysisResults,
        setAnalysisResults,
        analyzing,
        setAnalyzing,
        analysisError,
        setAnalysisError,
      }}
    >
      {children}
    </RepositoryContext.Provider>
  );
};

export default RepositoryProvider;