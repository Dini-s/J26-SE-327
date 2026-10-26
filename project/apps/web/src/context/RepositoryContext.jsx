import { createContext, useContext } from "react";

export const RepositoryContext = createContext(null);

export const useRepository = () => {
  const context = useContext(RepositoryContext);

  if (!context) {
    throw new Error(
      "useRepository must be used inside RepositoryProvider"
    );
  }

  return context;
};