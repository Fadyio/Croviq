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
    <main className="relative min-h-screen bg-background text-text-primary flex flex-col justify-center items-center px-4 py-8 selection:bg-primary/25">
      {/* Subtle architectural studio background accents */}
      <div className="absolute inset-0 bg-[radial-gradient(#22272F_1px,transparent_1px)] [background-size:24px_24px] opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-5xl h-64 bg-gradient-to-b from-primary/5 via-transparent to-transparent pointer-events-none" />

      <motion.section {...cardMotionProps} className="relative z-10 w-full max-w-[400px]">
        <div className="rounded-xl border border-border-subtle bg-surface-1/95 p-6 sm:p-8 shadow-xl shadow-black/40 backdrop-blur-sm">
          <div className="flex flex-col items-center text-center mb-7">
            <div className="mb-5 flex items-center justify-center">
              <CroviqLogo height={30} className="h-[30px] w-auto" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">
              Sign in to Croviq
            </h1>
            <p className="mt-1 text-xs text-text-muted">
              Autonomous Production Studio for YouTube Creators
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label
                className="mb-1.5 block text-xs font-medium text-text-secondary"
                htmlFor="email"
              >
                Email
              </label>
              <input
                autoComplete="email"
                className="h-10 w-full rounded-md border border-border-subtle bg-surface-2 px-3 text-xs text-text-primary outline-none transition-all placeholder:text-text-muted hover:border-border-strong focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isLoading}
                id="email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="creator@channel.com"
                required
                type="email"
                value={email}
              />
            </div>

            <div>
              <label
                className="mb-1.5 block text-xs font-medium text-text-secondary"
                htmlFor="password"
              >
                Password
              </label>
              <input
                autoComplete="current-password"
                className="h-10 w-full rounded-md border border-border-subtle bg-surface-2 px-3 text-xs text-text-primary outline-none transition-all placeholder:text-text-muted hover:border-border-strong focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
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
                  className="flex items-start gap-2.5 rounded-md border border-danger/30 bg-danger/10 p-2.5 text-xs leading-relaxed text-danger"
                  exit={{ opacity: 0, y: -4 }}
                  initial={{ opacity: 0, y: -4 }}
                  role="alert"
                  transition={{ duration: 0.16, ease: "easeOut" }}
                >
                  <AlertCircle aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{error}</span>
                </motion.div>
              )}
            </AnimatePresence>

            <motion.button
              className="mt-2 flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 text-xs font-semibold text-white shadow-sm transition-all hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading}
              type="submit"
              whileTap={prefersReducedMotion ? undefined : { scale: 0.99 }}
            >
              {isLoading ? (
                <>
                  <Loader2 aria-hidden="true" className="mr-2 h-3.5 w-3.5 animate-spin" />
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
