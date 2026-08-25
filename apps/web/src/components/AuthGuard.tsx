import React, { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { CroviqLogo } from "./CroviqLogo";

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
    return (
      <div className="min-h-screen bg-background text-text-primary flex flex-col items-center justify-center p-6 select-none">
        <div className="flex flex-col items-center gap-4">
          <CroviqLogo height={28} className="h-7 w-auto opacity-80 animate-pulse" />
          <div className="flex items-center gap-2 text-xs font-mono text-text-muted mt-2">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            <span>Verifying session...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
};
