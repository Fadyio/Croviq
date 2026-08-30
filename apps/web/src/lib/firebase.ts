import { type FirebaseApp, getApp, getApps, initializeApp } from "firebase/app";
import {
  type Auth,
  browserLocalPersistence,
  getAuth,
  indexedDBLocalPersistence,
  initializeAuth,
} from "firebase/auth";

/**
 * Firebase / Identity Platform client configuration.
 * Strictly configured via Vite environment variables (import.meta.env).
 * No hardcoded fallback keys, project constants, or dummy substitutions.
 */
const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN;
const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;

if (!apiKey || !authDomain || !projectId) {
  const missing: string[] = [];
  if (!apiKey) missing.push("VITE_FIREBASE_API_KEY");
  if (!authDomain) missing.push("VITE_FIREBASE_AUTH_DOMAIN");
  if (!projectId) missing.push("VITE_FIREBASE_PROJECT_ID");
  throw new Error(
    `Missing required Firebase frontend configuration: ${missing.join(", ")}. Ensure these environment variables are provided.`,
  );
}

const firebaseConfig = {
  apiKey,
  authDomain,
  projectId,
};
export const app: FirebaseApp = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);

const getOrInitAuth = (firebaseApp: FirebaseApp): Auth => {
  try {
    return initializeAuth(firebaseApp, {
      persistence: [indexedDBLocalPersistence, browserLocalPersistence],
    });
  } catch {
    return getAuth(firebaseApp);
  }
};

export const auth: Auth = getOrInitAuth(app);
