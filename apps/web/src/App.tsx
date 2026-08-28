import React, { useEffect, useState, useCallback } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AuthGuard } from "./components/AuthGuard";
import { LoginPage } from "./pages/LoginPage";
import { AppPage } from "./pages/AppPage";
import { NewProjectPage } from "./pages/NewProjectPage";
import { EditorPage } from "./pages/EditorPage";
import { LoadingScreen } from "./components/LoadingScreen";

const parseProductionEditorRoute = (pathname: string): string | null => {
  const match = pathname.match(/^\/productions\/([^/]+)(?:\/editor)?\/?$/);
  return match ? match[1] : null;
};

const normalizePath = (pathname: string): string => {
  if (pathname === "" || pathname === "/") return "/";
  if (pathname.startsWith("/app")) return "/app";
  if (pathname.startsWith("/login")) return "/login";
  if (pathname.startsWith("/projects/new")) return "/projects/new";
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
    setCurrentPath(to);
  }, []);

  // Listen to browser navigation (back/forward)
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(normalizePath(window.location.pathname));
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

  const productionId = parseProductionEditorRoute(currentPath);
  if (productionId) {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <EditorPage productionId={productionId} onNavigateHome={() => navigate("/app")} />
      </AuthGuard>
    );
  }

  if (currentPath === "/app") {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <AppPage onNavigateNewProject={() => navigate("/projects/new")} />
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
