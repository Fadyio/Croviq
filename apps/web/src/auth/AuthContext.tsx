import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  onIdTokenChanged,
  signInWithEmailAndPassword,
  signOut,
  type User as FirebaseUser,
} from "firebase/auth";
import { auth } from "../lib/firebase";
import type { components } from "../api/generated";

export type User = components["schemas"]["User"];
export type ClientAuthEvent =
  | components["schemas"]["AuthLoginAttemptEvent"]
  | components["schemas"]["AuthLoginFailedEvent"]
  | components["schemas"]["AuthSessionRestoredEvent"]
  | components["schemas"]["AuthTokenRefreshedEvent"]
  | components["schemas"]["AuthTokenRefreshFailedEvent"]
  | components["schemas"]["AuthSessionLostEvent"]
  | components["schemas"]["AuthExplicitLogoutEvent"];

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
const SESSION_EXPIRED_MESSAGE = "Your session has expired. Please sign in again.";

const createOptimisticUser = (fbUser: FirebaseUser): User => ({
  user_id: fbUser.uid,
  email: fbUser.email ?? "",
  display_name: fbUser.displayName ?? fbUser.email ?? "Croviq User",
  avatar_url: fbUser.photoURL ?? null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

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

  const verifyTokenWithBackend = useCallback(
    async (token: string, currentFirebaseUser: FirebaseUser): Promise<User | null> => {
      try {
        let response = await fetch("/api/auth/me", {
          headers: {
            Authorization: `Bearer ${token}`,
            "x-request-id": `web-auth-${Date.now()}`,
          },
        });

        // If 401, attempt a force token refresh before giving up, but never destroy session
        if (response.status === 401) {
          try {
            const refreshedToken = await currentFirebaseUser.getIdToken(true);
            void recordClientAuthEvent({
              event_type: "auth.token.refreshed",
              firebase_uid: currentFirebaseUser.uid,
            });
            response = await fetch("/api/auth/me", {
              headers: {
                Authorization: `Bearer ${refreshedToken}`,
                "x-request-id": `web-auth-${Date.now()}`,
              },
            });
          } catch {
            void recordClientAuthEvent({
              event_type: "auth.token_refresh_failed",
              firebase_uid: currentFirebaseUser.uid,
            });
            setError(SESSION_EXPIRED_MESSAGE);
            return null;
          }

          if (response.status === 401) {
            setError(SESSION_EXPIRED_MESSAGE);
            return null;
          }
        }

        if (response.ok) {
          return (await response.json()) as User;
        }

        if (response.status === 403) {
          setError(ACCESS_RESTRICTED_MESSAGE);
          void recordClientAuthEvent({
            event_type: "auth.login_failed",
            error_code: "demo_access_restricted",
            firebase_uid: currentFirebaseUser.uid,
          });
          // A backend authorization refusal blocks Croviq access, but retains the Firebase session.
          // Never trigger sign out automatically.
          return null;
        }

        // On 500, 502, 503, or temporary backend errors, do NOT call signOut.
        // Fallback to domain user representation from verified Firebase User to prevent logout.
        return createOptimisticUser(currentFirebaseUser);
      } catch {
        // Network error contacting Croviq API. Keep authenticated session alive with optimistic user.
        return createOptimisticUser(currentFirebaseUser);
      }
    },
    [],
  );

  useEffect(() => {
    let isMounted = true;
    const unsubscribe = onIdTokenChanged(auth, async (nextFirebaseUser) => {
      if (!isMounted) return;

      setFirebaseUser(nextFirebaseUser);
      if (!nextFirebaseUser) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      void recordClientAuthEvent({
        event_type: "auth.session.restored",
        firebase_uid: nextFirebaseUser.uid,
      });

      try {
        const token = await nextFirebaseUser.getIdToken();
        void recordClientAuthEvent({
          event_type: "auth.token.refreshed",
          firebase_uid: nextFirebaseUser.uid,
        });

        const domainUser = await verifyTokenWithBackend(token, nextFirebaseUser);
        if (!isMounted) return;

        setUser(domainUser);
        if (domainUser) clearError();
      } catch {
        if (isMounted) {
          void recordClientAuthEvent({
            event_type: "auth.session_lost",
            firebase_uid: nextFirebaseUser.uid,
          });
          setUser(createOptimisticUser(nextFirebaseUser));
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
    const currentUid = firebaseUser?.uid;
    if (currentUid) {
      void recordClientAuthEvent({
        event_type: "auth.explicit_logout",
        firebase_uid: currentUid,
      });
    }

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
  }, [clearError, firebaseUser?.uid]);

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
