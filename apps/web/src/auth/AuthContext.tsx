import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  browserLocalPersistence,
  onAuthStateChanged,
  setPersistence,
  signInWithEmailAndPassword,
  signOut,
  type User as FirebaseUser,
} from "firebase/auth";
import { auth } from "../lib/firebase";
import type { components } from "../api/generated";

export type User = components["schemas"]["User"];
export type ClientAuthEvent =
  components["schemas"]["AuthLoginAttemptEvent"] | components["schemas"]["AuthLoginFailedEvent"];

export interface AuthContextValue {
  user: User | null;
  firebaseUser: FirebaseUser | null;
  isLoading: boolean;
  error: string | null;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const INVALID_CREDENTIALS_MESSAGE = "Email or password is incorrect.";
const ACCESS_RESTRICTED_MESSAGE = "This account is not authorized to access Croviq.";

const recordClientAuthEvent = async (event: ClientAuthEvent): Promise<void> => {
  try {
    await fetch("/api/client-events", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-request-id": `web-auth-${Date.now()}`,
      },
      body: JSON.stringify(event),
    });
  } catch {
    // Client telemetry must not prevent authentication.
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const verifyTokenWithBackend = useCallback(async (token: string): Promise<User | null> => {
    try {
      const response = await fetch("/api/auth/me", {
        headers: {
          Authorization: `Bearer ${token}`,
          "x-request-id": `web-auth-${Date.now()}`,
        },
      });

      if (response.ok) {
        return (await response.json()) as User;
      }

      if (response.status === 403) {
        setError(ACCESS_RESTRICTED_MESSAGE);
        void recordClientAuthEvent({
          event_type: "auth.login_failed",
          error_code: "demo_access_restricted",
        });
        try {
          await signOut(auth);
        } catch {
          // Authorization denial remains the user-facing result if Firebase sign-out fails.
        }
        return null;
      }

      if (response.status === 401) {
        setError("Sign-in expired or invalid. Please sign in again.");
        await signOut(auth);
        return null;
      }

      setError("Unable to complete sign-in. Please try again.");
      return null;
    } catch {
      setError("Network error contacting Croviq API. Please check your connection.");
      return null;
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    // Request browser-local persistence asynchronously without blocking listener attachment
    void setPersistence(auth, browserLocalPersistence).catch(() => {
      // If persistence cannot be set (e.g. strict private mode), in-memory session still functions.
    });

    const unsubscribe = onAuthStateChanged(auth, async (nextFirebaseUser) => {
      if (!isMounted) return;

      setFirebaseUser(nextFirebaseUser);
      if (!nextFirebaseUser) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      try {
        const token = await nextFirebaseUser.getIdToken();
        const domainUser = await verifyTokenWithBackend(token);
        if (!isMounted) return;

        setUser(domainUser);
        if (domainUser) clearError();
      } catch {
        if (isMounted) {
          setUser(null);
          setError("Unable to complete sign-in. Please try again.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, [clearError, verifyTokenWithBackend]);

  const loginWithPassword = useCallback(
    async (email: string, password: string): Promise<void> => {
      setIsLoading(true);
      clearError();
      void recordClientAuthEvent({ event_type: "auth.login_attempt" });

      try {
        await signInWithEmailAndPassword(auth, email, password);
      } catch {
        setError(INVALID_CREDENTIALS_MESSAGE);
        void recordClientAuthEvent({
          event_type: "auth.login_failed",
          error_code: "invalid_credentials",
        });
        setIsLoading(false);
      }
    },
    [clearError],
  );

  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      await signOut(auth);
    } catch {
      // Local application state still must clear if Firebase sign-out fails.
    }

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: {
          "x-request-id": `web-logout-${Date.now()}`,
        },
      });
    } catch {
      // Logout observation must not block client logout.
    }

    setUser(null);
    setFirebaseUser(null);
    clearError();
    setIsLoading(false);
  }, [clearError]);

  return (
    <AuthContext.Provider
      value={{
        user,
        firebaseUser,
        isLoading,
        error,
        loginWithPassword,
        logout,
        clearError,
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
