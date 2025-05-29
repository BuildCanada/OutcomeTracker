"use client";

import React, { createContext, useContext, ReactNode } from "react";
import { DepartmentConfig } from "@/lib/types";

interface DepartmentContextType {
  allDeptConfigs: DepartmentConfig[];
  mainTabConfigs: DepartmentConfig[];
  sessionId: string;
  governingParty: string;
}

const DepartmentContext = createContext<DepartmentContextType | undefined>(
  undefined,
);

interface DepartmentProviderProps {
  children: ReactNode;
  allDeptConfigs: DepartmentConfig[];
  mainTabConfigs: DepartmentConfig[];
  sessionId: string;
  governingParty: string;
}

export const DepartmentProvider: React.FC<DepartmentProviderProps> = ({
  children,
  allDeptConfigs,
  mainTabConfigs,
  sessionId,
  governingParty,
}) => {
  return (
    <DepartmentContext.Provider
      value={{
        allDeptConfigs,
        mainTabConfigs,
        sessionId,
        governingParty,
      }}
    >
      {children}
    </DepartmentContext.Provider>
  );
};

export const useDepartments = (): DepartmentContextType => {
  const context = useContext(DepartmentContext);
  if (context === undefined) {
    throw new Error("useDepartments must be used within a DepartmentProvider");
  }
  return context;
};
