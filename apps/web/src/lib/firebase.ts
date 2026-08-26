import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import {
  browserLocalPersistence,
  getAuth,
  indexedDBLocalPersistence,
  initializeAuth,
  type Auth,
} from "firebase/auth";

/**
 * Firebase / Identity Platform client configuration.
 * Configured via Vite environment variables with production defaults.
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "***REMOVED***",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "croviq-506602.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "croviq-506602",
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
