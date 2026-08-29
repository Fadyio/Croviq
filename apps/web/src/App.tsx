import React, { useEffect, useLayoutEffect, useState, useCallback } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AuthGuard } from "./components/AuthGuard";
import { LoginPage } from "./pages/LoginPage";
import { AppPage } from "./pages/AppPage";
import { NewProjectPage } from "./pages/NewProjectPage";
import { EditorPage } from "./pages/EditorPage";
import { ReleasePage } from "./pages/ReleasePage";
import { LoadingScreen } from "./components/LoadingScreen";
import { AgentWorkspacePage } from "./pages/AgentWorkspacePage";
import type { AgentId } from "./components/AgentTeamSelector";

const parseProductionReleaseRoute = (pathname: string): string | null => {
  const match = pathname.match(/^\/productions\/([^/]+)\/release\/?$/);
  return match ? match[1] : null;
};

const parseProductionEditorRoute = (pathname: string): string | null => {
  const match = pathname.match(/^\/productions\/([^/]+)(?:\/editor)?\/?$/);
  return match ? match[1] : null;
};

const parseAgentRoute = (pathname: string): AgentId | null => {
  const match = pathname.match(/^\/app\/agents\/(alex|leo|iris)\/?$/);
  return match ? (match[1] as AgentId) : null;
};
const normalizePath = (pathname: string): string => {
  if (pathname === "" || pathname === "/") return "/";
  if (pathname === "/app" || pathname === "/app/") return "/app";
  if (
    pathname.startsWith("/app/performance") ||
    pathname.startsWith("/app/experiments") ||
    pathname.startsWith("/app/overview")
  ) {
    if (typeof window !== "undefined" && window.location.pathname !== "/app") {
      window.history.replaceState(null, "", "/app");
    }
    return "/app";
  }
  const agentId = parseAgentRoute(pathname);
  if (agentId) return `/app/agents/${agentId}`;
  if (pathname.startsWith("/login")) return "/login";
  if (pathname.startsWith("/projects/new")) return "/projects/new";
  if (parseProductionReleaseRoute(pathname)) return pathname;
  if (parseProductionEditorRoute(pathname)) return pathname;
  return pathname;
};

const AppRoutes: React.FC = () => {
  const { user, isLoading } = useAuth();
  const [currentPath, setCurrentPath] = useState<string>(() =>
    normalizePath(window.location.pathname),
  );

  const navigate = useCallback((to: string) => {
    if (window.location.pathname !== to) {
      window.history.pushState(null, "", to);
    }
    setCurrentPath(normalizePath(to));
  }, []);

  // Immediate layout redirect for legacy tab URLs
  useLayoutEffect(() => {
    if (
      window.location.pathname.startsWith("/app/performance") ||
      window.location.pathname.startsWith("/app/experiments") ||
      window.location.pathname.startsWith("/app/overview")
    ) {
      window.history.replaceState(null, "", "/app");
      setCurrentPath("/app");
    }
  }, []);

  // Listen to browser navigation (back/forward)
  useEffect(() => {
    const handlePopState = () => {
      const normalized = normalizePath(window.location.pathname);
      setCurrentPath(normalized);
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);
  // Auto-redirect logic for authenticated users navigating to / or /login
  useEffect(() => {
    if (!isLoading) {
      if (user && (currentPath === "/login" || currentPath === "/")) {
        navigate("/app");
      } else if (!user && (currentPath === "/" || currentPath !== "/login")) {
        navigate("/login");
      }
    }
  }, [user, isLoading, currentPath, navigate]);

  // Initial loading screen during session verification
  if (isLoading) {
    return <LoadingScreen />;
  }

  const releaseProductionId = parseProductionReleaseRoute(currentPath);
  if (releaseProductionId) {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <ReleasePage
          productionId={releaseProductionId}
          onNavigateHome={() => navigate("/app")}
          onNavigateEditor={() => navigate(`/productions/${releaseProductionId}`)}
        />
      </AuthGuard>
    );
  }

  const productionId = parseProductionEditorRoute(currentPath);
  if (productionId) {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <EditorPage
          productionId={productionId}
          onNavigateHome={() => navigate("/app")}
          onNavigateRelease={() => navigate(`/productions/${productionId}/release`)}
        />
      </AuthGuard>
    );
  }

  const agentId = parseAgentRoute(currentPath);
  if (agentId) {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <AgentWorkspacePage agentId={agentId} onNavigate={navigate} />
      </AuthGuard>
    );
  }
  if (currentPath === "/app") {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <AppPage
          onNavigateRoute={(route) => navigate(route)}
          onNavigateNewProject={() => navigate("/projects/new")}
        />
      </AuthGuard>
    );
  }

  if (currentPath === "/projects/new") {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <NewProjectPage
          onNavigateHome={() => navigate("/app")}
          onNavigateToEditor={(prodId) => navigate(`/productions/${prodId}/editor`)}
        />
      </AuthGuard>
    );
  }

  // Default to Login view for unauthenticated visitors
  return <LoginPage />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
};

export default App;
