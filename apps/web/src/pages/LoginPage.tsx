import React, { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { AlertCircle, Loader2 } from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";

export const LoginPage: React.FC = () => {
  const { clearError, error, isLoading, loginWithPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const prefersReducedMotion = useReducedMotion();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isLoading) return;

    clearError();
    await loginWithPassword(email, password);
  };

  const cardMotionProps = prefersReducedMotion
    ? {}
    : {
        initial: { opacity: 0, y: 10 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.22, ease: "easeOut" as const },
      };

  return (
    <main className="min-h-screen bg-background px-5 py-10 text-text-primary sm:px-8">
      <motion.section
        {...cardMotionProps}
        className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-md flex-col justify-center"
      >
        <div className="rounded-lg border border-border-subtle bg-surface-1 p-7 shadow-sm sm:p-8">
          <div className="mb-8">
            <CroviqLogo height={28} className="h-7 w-auto" />
            <h1 className="mt-8 text-2xl font-semibold tracking-tight text-text-primary">
              Sign in to Croviq
            </h1>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-text-secondary" htmlFor="email">
                Email
              </label>
              <input
                autoComplete="email"
                className="h-11 w-full rounded-md border border-border-strong bg-surface-2 px-3 text-sm text-text-primary outline-none placeholder:text-text-muted focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isLoading}
                id="email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </div>

            <div>
              <label
                className="mb-2 block text-sm font-medium text-text-secondary"
                htmlFor="password"
              >
                Password
              </label>
              <input
                autoComplete="current-password"
                className="h-11 w-full rounded-md border border-border-strong bg-surface-2 px-3 text-sm text-text-primary outline-none placeholder:text-text-muted focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isLoading}
                id="password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </div>

            <AnimatePresence initial={false}>
              {error && (
                <motion.div
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-start gap-2.5 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm leading-relaxed text-danger"
                  exit={{ opacity: 0, y: -4 }}
                  initial={{ opacity: 0, y: -4 }}
                  role="alert"
                  transition={{ duration: 0.16, ease: "easeOut" }}
                >
                  <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </motion.div>
              )}
            </AnimatePresence>

            <motion.button
              className="flex h-11 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-white outline-none transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading}
              type="submit"
              whileTap={prefersReducedMotion ? undefined : { scale: 0.98 }}
            >
              {isLoading ? (
                <>
                  <Loader2 aria-hidden="true" className="mr-2 h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </motion.button>
          </form>
        </div>
      </motion.section>
    </main>
  );
};
