import React, { useEffect, useState, useCallback } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AuthGuard } from "./components/AuthGuard";
import { LoginPage } from "./pages/LoginPage";
import { AppPage } from "./pages/AppPage";
import { Loader2 } from "lucide-react";
import { CroviqLogo } from "./components/CroviqLogo";

const normalizePath = (pathname: string): string => {
  if (pathname === "" || pathname === "/") return "/";
  if (pathname.startsWith("/app")) return "/app";
  if (pathname.startsWith("/login")) return "/login";
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
      } else if (
        !user &&
        (currentPath === "/" || (currentPath !== "/login" && currentPath !== "/app"))
      ) {
        navigate("/login");
      }
    }
  }, [user, isLoading, currentPath, navigate]);

  // Initial loading screen during session verification
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

  if (currentPath === "/app") {
    return (
      <AuthGuard onRedirectToLogin={() => navigate("/login")}>
        <AppPage />
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
