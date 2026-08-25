import React, { useEffect } from "react";
import { useAuth } from "../auth/AuthContext";
import { LoadingScreen } from "./LoadingScreen";

export const AuthGuard: React.FC<{
  children: React.ReactNode;
  onRedirectToLogin: () => void;
}> = ({ children, onRedirectToLogin }) => {
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) {
      onRedirectToLogin();
    }
  }, [user, isLoading, onRedirectToLogin]);

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
};
