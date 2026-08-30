import { Loader2 } from "lucide-react";
import React from "react";
import { CroviqLogo } from "./CroviqLogo";

export const LoadingScreen: React.FC = () => {
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
};
