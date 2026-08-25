import React from "react";
import { motion, useReducedMotion } from "motion/react";
import { AlertCircle, Loader2 } from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { PipelineBraid } from "../components/PipelineBraid";
import { useAuth } from "../auth/AuthContext";

export const LoginPage: React.FC = () => {
  const { loginWithGoogle, isLoading, error } = useAuth();
  const prefersReducedMotion = useReducedMotion();

  const handleSignIn = async () => {
    if (isLoading) return;
    await loginWithGoogle();
  };

  const cardMotionProps = prefersReducedMotion
    ? {}
    : {
        initial: { opacity: 0, y: 8 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.25, ease: "easeOut" as const },
      };

  return (
    <div className="min-h-screen w-full bg-background text-text-primary flex flex-col md:flex-row selection:bg-primary/30">
      {/* Left Pane — Brand & Pipeline Visualization */}
      <section className="flex-1 flex flex-col justify-between p-8 md:p-14 lg:p-18 border-b md:border-b-0 md:border-r border-border-subtle bg-surface-1/40">
        <div>
          {/* Real Croviq SVG Logo */}
          <div className="flex items-center gap-3">
            <CroviqLogo height={32} className="h-8 w-auto" />
          </div>

          <div className="mt-12 md:mt-20 max-w-md">
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-text-primary">
              CI/CD for video creators.
            </h1>
            <p className="mt-3 text-sm md:text-base text-text-secondary leading-relaxed">
              Automated assembly, narrative intelligence, and deterministic truth-verification for
              YouTube production.
            </p>
          </div>
        </div>

        {/* Subtle Animated Workflow SVG Braid */}
        <div className="my-10 md:my-14 flex items-center justify-center md:justify-start">
          <PipelineBraid />
        </div>

        {/* System Tag */}
        <div className="flex items-center gap-2 text-xs font-mono text-text-muted">
          <span className="inline-block w-2 h-2 rounded-full bg-success/80" />
          <span>Croviq Studio • Milestone 2A</span>
        </div>
      </section>

      {/* Right Pane — Compact Google Sign-In Card */}
      <main className="flex-1 flex items-center justify-center p-6 md:p-12 lg:p-16">
        <motion.div
          {...cardMotionProps}
          className="w-full max-w-sm bg-surface-1 border border-border-subtle rounded-lg p-7 md:p-8 shadow-sm flex flex-col"
        >
          {/* Card Header */}
          <div className="mb-6 text-center">
            <h2 className="text-lg font-semibold text-text-primary">Sign in to Croviq</h2>
            <p className="mt-1.5 text-xs text-text-secondary">
              Authenticate with your approved Google identity to access your production workspace.
            </p>
          </div>

          {/* Error Callout */}
          {error && (
            <div
              role="alert"
              className="mb-5 p-3 rounded-md bg-danger/10 border border-danger/30 text-danger text-xs flex items-start gap-2.5 leading-relaxed animate-in fade-in duration-150"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Google Sign-In Button */}
          <button
            type="button"
            onClick={handleSignIn}
            disabled={isLoading}
            className="w-full h-11 px-4 rounded-md bg-surface-2 hover:bg-surface-3 active:bg-elevated border border-border-strong hover:border-border-strong text-text-primary text-sm font-medium flex items-center justify-center gap-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Continue with Google"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
                <span>Verifying session...</span>
              </>
            ) : (
              <>
                {/* Official Google G Logo SVG */}
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="#4285F4"
                    d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.34 24 12 24z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.98 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.34 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                  />
                </svg>
                <span>Continue with Google</span>
              </>
            )}
          </button>

          {/* Hackathon Access Notice */}
          <p className="mt-6 text-center text-xs text-text-muted leading-relaxed">
            Private hackathon demo — authorized account only.
          </p>
        </motion.div>
      </main>
    </div>
  );
};
