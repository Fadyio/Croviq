import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  type User as FirebaseUser,
} from "firebase/auth";
import { auth, googleProvider } from "../lib/firebase";
import type { components } from "../api/generated";

export type User = components["schemas"]["User"];

export interface AuthContextValue {
  user: User | null;
  firebaseUser: FirebaseUser | null;
  idToken: string | null;
  isLoading: boolean;
  error: string | null;
  authErrorCode: string | null;
  loginWithGoogle: () => Promise<boolean>;
  logout: () => Promise<void>;
  clearError: () => void;
  // Test helper to inject mock auth state without hitting Firebase
  setMockUser: (mockUser: User | null) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const DEMO_RESTRICTED_MESSAGE = "This Croviq demo is restricted to the approved account.";

declare global {
  interface Window {
    __CROVIQ_MOCK_USER__?: User | null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window !== "undefined") {
      if (window.__CROVIQ_MOCK_USER__) return window.__CROVIQ_MOCK_USER__;
      const stored = sessionStorage.getItem("__CROVIQ_MOCK_USER__");
      if (stored) {
        try {
          return JSON.parse(stored) as User;
        } catch {
          return null;
        }
      }
    }
    return null;
  });

  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);
  const [idToken, setIdToken] = useState<string | null>(() => {
    if (typeof window !== "undefined" && window.__CROVIQ_MOCK_USER__) {
      return "mock-jwt-token-croviq";
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [authErrorCode, setAuthErrorCode] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
    setAuthErrorCode(null);
  }, []);

  const setMockUser = useCallback((mockUser: User | null) => {
    setUser(mockUser);
    if (mockUser) {
      setIdToken("mock-jwt-token-croviq");
      sessionStorage.setItem("__CROVIQ_MOCK_USER__", JSON.stringify(mockUser));
    } else {
      setIdToken(null);
      sessionStorage.removeItem("__CROVIQ_MOCK_USER__");
    }
    setIsLoading(false);
  }, []);

  /**
   * Verify token with backend /api/auth/me endpoint.
   * Backend remains authoritative source of truth for demo-locked policy.
   */
  const verifyTokenWithBackend = useCallback(async (token: string): Promise<User | null> => {
    try {
      const res = await fetch("/api/auth/me", {
        headers: {
          Authorization: `Bearer ${token}`,
          "x-request-id": `web-auth-${Date.now()}`,
        },
      });

      if (res.ok) {
        const userData = (await res.json()) as User;
        return userData;
      }

      if (res.status === 403) {
        const errorBody = await res.json().catch(() => ({}));
        setError(DEMO_RESTRICTED_MESSAGE);
        setAuthErrorCode(errorBody.error_code || "demo_access_restricted");
        // Sign out Firebase session if account is not authorized
        try {
          await signOut(auth);
        } catch {
          // ignore signout errors
        }
        return null;
      }

      if (res.status === 401) {
        setError("Sign-in expired or invalid. Please sign in again.");
        setAuthErrorCode("unauthorized");
        try {
          await signOut(auth);
        } catch {
          // ignore
        }
        return null;
      }

      setError("Unable to complete sign-in. Please try again.");
      setAuthErrorCode("server_error");
      return null;
    } catch {
      setError("Network error contacting Croviq API. Please check your connection.");
      setAuthErrorCode("network_error");
      return null;
    }
  }, []);

  // Listen for Firebase Auth state changes
  useEffect(() => {
    // If mock auth is active (e.g. during Playwright automated tests), bypass Firebase listener
    if (
      typeof window !== "undefined" &&
      (window.__CROVIQ_MOCK_USER__ || sessionStorage.getItem("__CROVIQ_MOCK_USER__"))
    ) {
      setIsLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
      setFirebaseUser(fbUser);
      if (fbUser) {
        try {
          const token = await fbUser.getIdToken();
          setIdToken(token);
          const domainUser = await verifyTokenWithBackend(token);
          if (domainUser) {
            setUser(domainUser);
            clearError();
          } else {
            setUser(null);
            setIdToken(null);
          }
        } catch {
          setUser(null);
          setIdToken(null);
        } finally {
          setIsLoading(false);
        }
      } else {
        setUser(null);
        setIdToken(null);
        setIsLoading(false);
      }
    });

    return () => unsubscribe();
  }, [verifyTokenWithBackend, clearError]);

  const loginWithGoogle = useCallback(async (): Promise<boolean> => {
    setIsLoading(true);
    clearError();

    try {
      const userCredential = await signInWithPopup(auth, googleProvider);
      const fbUser = userCredential.user;
      setFirebaseUser(fbUser);

      const token = await fbUser.getIdToken();
      setIdToken(token);

      const domainUser = await verifyTokenWithBackend(token);
      if (domainUser) {
        setUser(domainUser);
        clearError();
        setIsLoading(false);
        return true;
      } else {
        setUser(null);
        setIdToken(null);
        setIsLoading(false);
        return false;
      }
    } catch (err: unknown) {
      setIsLoading(false);
      const firebaseError = err as { code?: string; message?: string };
      if (
        firebaseError.code === "auth/popup-closed-by-user" ||
        firebaseError.code === "auth/cancelled-popup-request"
      ) {
        // User voluntarily dismissed popup, no alarm banner needed
        return false;
      }

      if (firebaseError.code === "auth/popup-blocked") {
        setError("Sign-in popup was blocked by your browser. Please allow popups for Croviq.");
        setAuthErrorCode("popup_blocked");
        return false;
      }

      setError(firebaseError.message || "Google sign-in could not be completed.");
      setAuthErrorCode("auth_failed");
      return false;
    }
  }, [verifyTokenWithBackend, clearError]);

  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);

    // Clear mock storage if present
    if (typeof window !== "undefined") {
      delete window.__CROVIQ_MOCK_USER__;
      sessionStorage.removeItem("__CROVIQ_MOCK_USER__");
    }

    try {
      await signOut(auth);
    } catch {
      // ignore
    }

    // Fire-and-forget server logout event recording
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: {
          "x-request-id": `web-logout-${Date.now()}`,
        },
      });
    } catch {
      // non-blocking
    }

    setUser(null);
    setFirebaseUser(null);
    setIdToken(null);
    clearError();
    setIsLoading(false);
  }, [clearError]);

  return (
    <AuthContext.Provider
      value={{
        user,
        firebaseUser,
        idToken,
        isLoading,
        error,
        authErrorCode,
        loginWithGoogle,
        logout,
        clearError,
        setMockUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
