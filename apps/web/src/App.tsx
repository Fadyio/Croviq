import React, { useEffect, useState } from "react";
import { CroviqLogo } from "./components/CroviqLogo";

interface HealthData {
  status: string;
  service: string;
  git_sha: string;
}

type ApiStatus = "loading" | "connected" | "unavailable";

export const App: React.FC = () => {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("loading");
  const [healthData, setHealthData] = useState<HealthData | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch("/api/health");
        if (!res.ok) {
          setApiStatus("unavailable");
          return;
        }
        const data = (await res.json()) as HealthData;
        if (data.status === "ok") {
          setHealthData(data);
          setApiStatus("connected");
        } else {
          setApiStatus("unavailable");
        }
      } catch {
        setApiStatus("unavailable");
      }
    };

    fetchHealth();
  }, []);

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col font-sans selection:bg-primary/30">
      {/* Top Application Bar */}
      <header className="h-12 bg-surface-1 border-b border-border-subtle px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <CroviqLogo height={24} className="h-6 w-auto" />
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-surface-3 border border-border-subtle text-xs font-mono text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-success inline-block" aria-hidden="true" />
            <span>Local Development</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-surface-1 border border-border-subtle rounded-md p-6 shadow-sm">
          {/* Header */}
          <div className="border-b border-border-subtle pb-4 mb-5">
            <h1 className="text-lg font-semibold tracking-tight text-text-primary">Croviq</h1>
            <p className="text-xs text-text-secondary mt-0.5 font-normal">
              Creator workflow system
            </p>
          </div>

          {/* Status Section */}
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-text-muted mb-3 font-mono">
              Status
            </div>

            <div className="space-y-2">
              {/* Frontend Status */}
              <div className="flex items-center justify-between px-3 py-2.5 rounded-sm bg-surface-2 border border-border-subtle">
                <span className="text-xs font-medium text-text-primary">Frontend</span>
                <span className="inline-flex items-center gap-1.5 text-xs font-mono text-success">
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-success inline-block"
                    aria-hidden="true"
                  />
                  Running
                </span>
              </div>

              {/* API Status */}
              <div className="flex flex-col gap-1.5 px-3 py-2.5 rounded-sm bg-surface-2 border border-border-subtle">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-text-primary">API</span>
                  {apiStatus === "connected" ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-mono text-success">
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-success inline-block"
                        aria-hidden="true"
                      />
                      Connected
                    </span>
                  ) : apiStatus === "unavailable" ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-mono text-danger">
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-danger inline-block"
                        aria-hidden="true"
                      />
                      Unavailable
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs font-mono text-text-muted">
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-text-muted/60 inline-block"
                        aria-hidden="true"
                      />
                      Connecting...
                    </span>
                  )}
                </div>
                {apiStatus === "connected" && healthData && (
                  <div className="flex items-center justify-between text-[11px] font-mono text-text-muted pt-1.5 border-t border-border-subtle/50">
                    <span>{healthData.service}</span>
                    <span title={healthData.git_sha} className="text-text-secondary">
                      {healthData.git_sha.length > 7
                        ? healthData.git_sha.slice(0, 7)
                        : healthData.git_sha}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
