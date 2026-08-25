import React, { useEffect, useState } from "react";
import { LogOut, User as UserIcon, Building2, CheckCircle2, RefreshCw } from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import type { components } from "../api/generated";

type Workspace = components["schemas"]["Workspace"];

export const AppPage: React.FC = () => {
  const { user, firebaseUser, logout } = useAuth();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState<boolean>(true);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchWorkspace = async () => {
      if (!firebaseUser) {
        setIsLoadingWorkspace(false);
        return;
      }

      setIsLoadingWorkspace(true);
      try {
        const token = await firebaseUser.getIdToken();
        const res = await fetch("/api/workspace", {
          headers: {
            Authorization: `Bearer ${token}`,
            "x-request-id": `web-ws-${Date.now()}`,
          },
        });

        if (res.ok) {
          const data = (await res.json()) as Workspace;
          if (isMounted) {
            setWorkspace(data);
            setWorkspaceError(null);
          }
        } else {
          if (isMounted) {
            setWorkspaceError("Failed to load workspace configuration.");
          }
        }
      } catch {
        if (isMounted) {
          setWorkspaceError("Network error fetching workspace.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingWorkspace(false);
        }
      }
    };

    fetchWorkspace();

    return () => {
      isMounted = false;
    };
  }, [firebaseUser]);

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col font-sans selection:bg-primary/30">
      {/* Top Application Bar */}
      <header className="h-14 bg-surface-1 border-b border-border-subtle px-4 md:px-6 flex items-center justify-between shrink-0">
        {/* Left: Brand + Active Workspace */}
        <div className="flex items-center gap-4">
          <CroviqLogo height={24} className="h-6 w-auto" />
          <div className="h-4 w-px bg-border-subtle" />
          <div className="flex items-center gap-2 text-xs md:text-sm font-medium text-text-secondary">
            <Building2 className="w-4 h-4 text-text-muted" />
            <span className="text-text-primary font-semibold">
              {workspace ? workspace.name : "Croviq Demo Workspace"}
            </span>
          </div>
        </div>

        {/* Right: API Status, User Identity & Sign Out */}
        <div className="flex items-center gap-3 md:gap-5">
          {/* API Connected Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-2 border border-border-subtle text-xs text-text-secondary">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="font-mono font-medium text-text-primary">API Connected</span>
          </div>

          {/* User Identity Chip */}
          {user && (
            <div className="flex items-center gap-2 pl-2">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.display_name}
                  className="w-7 h-7 rounded-full border border-border-subtle object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-surface-3 border border-border-subtle flex items-center justify-center text-text-muted">
                  <UserIcon className="w-4 h-4" />
                </div>
              )}
              <div className="hidden sm:flex flex-col text-left">
                <span className="text-xs font-medium text-text-primary leading-tight">
                  {user.display_name}
                </span>
                <span className="text-[11px] font-mono text-text-muted leading-tight">
                  {user.email}
                </span>
              </div>
            </div>
          )}

          {/* Logout Button */}
          <button
            type="button"
            onClick={logout}
            className="h-8 px-3 rounded-md bg-surface-2 hover:bg-surface-3 active:bg-elevated border border-border-subtle text-xs font-medium text-text-secondary hover:text-text-primary flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Logout"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Logout</span>
          </button>
        </div>
      </header>

      {/* Main Studio Workspace Content */}
      <main className="flex-1 p-6 md:p-10 max-w-5xl w-full mx-auto flex flex-col gap-6">
        {/* Welcome Banner */}
        <div className="p-6 rounded-lg bg-surface-1 border border-border-subtle shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">
              Welcome back, {user?.display_name || "Creator"}
            </h1>
            <p className="mt-1 text-sm text-text-secondary">
              Authorized studio session active. Production pipeline is initialized and operational.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-3 py-1 rounded-md bg-surface-3 border border-border-subtle text-xs font-mono text-text-secondary">
              Authorized: {user?.email}
            </span>
          </div>
        </div>

        {/* Workspace & Studio Overview Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Workspace Details Card */}
          <div className="p-6 rounded-lg bg-surface-1 border border-border-subtle flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                <Building2 className="w-4 h-4 text-primary" />
                <span>Workspace Information</span>
              </div>
              {isLoadingWorkspace && (
                <RefreshCw className="w-3.5 h-3.5 text-text-muted animate-spin" />
              )}
            </div>

            {workspaceError ? (
              <div className="text-xs text-danger p-3 bg-danger/10 border border-danger/20 rounded-md">
                {workspaceError}
              </div>
            ) : (
              <div className="flex flex-col gap-3 text-xs">
                <div className="flex justify-between py-1 border-b border-surface-3">
                  <span className="text-text-muted">Name</span>
                  <span className="font-medium text-text-primary">
                    {workspace?.name || "Croviq Demo Workspace"}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-surface-3">
                  <span className="text-text-muted">Workspace ID</span>
                  <span className="font-mono text-text-secondary">
                    {workspace?.workspace_id || "ws_default_creator"}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-surface-3">
                  <span className="text-text-muted">Owner User ID</span>
                  <span className="font-mono text-text-secondary">
                    {workspace?.owner_user_id || user?.user_id || "uid_unknown"}
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-text-muted">Status</span>
                  <span className="text-success font-medium flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* BrandKit Summary Card */}
          <div className="p-6 rounded-lg bg-surface-1 border border-border-subtle flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                <CheckCircle2 className="w-4 h-4 text-success" />
                <span>BrandKit Configuration</span>
              </div>
            </div>

            <div className="flex flex-col gap-3 text-xs">
              <div className="flex justify-between py-1 border-b border-surface-3">
                <span className="text-text-muted">Tone</span>
                <span className="font-medium text-text-primary">
                  {workspace?.brand_kit?.tone?.join(", ") || "concise, informative"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-surface-3">
                <span className="text-text-muted">Target Audience</span>
                <span className="font-medium text-text-secondary">
                  {workspace?.brand_kit?.target_audience || "Video creators & developers"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-surface-3">
                <span className="text-text-muted">Content Style</span>
                <span className="font-medium text-text-secondary">
                  {workspace?.brand_kit?.content_style || "Technical walkthrough"}
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-text-muted">Single-Origin Origin</span>
                <span className="font-mono text-text-muted">https://app.croviq.app</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
