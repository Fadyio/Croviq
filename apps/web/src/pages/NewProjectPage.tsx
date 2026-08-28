import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  HardDrive,
  LogOut,
  Upload,
  Video,
  X,
  Loader2,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import type { components } from "../api/generated";

type CreateUploadResponse = components["schemas"]["CreateUploadResponse"];

const SAMPLE_CHANNEL_ID = "croviq_syn_ai_eng_01";
const MAX_UPLOAD_BYTES = 1 * 1024 * 1024 * 1024; // 1 GB

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

interface NewProjectPageProps {
  onNavigateHome: () => void;
  onNavigateToEditor?: (productionId: string) => void;
}

export const NewProjectPage: React.FC<NewProjectPageProps> = ({
  onNavigateHome,
  onNavigateToEditor,
}) => {
  const { user, firebaseUser, logout } = useAuth();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "initiating" | "uploading" | "verifying" | "uploaded" | "failed"
  >("idle");
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeXhrRef = useRef<XMLHttpRequest | null>(null);

  // Navigate to editor helper
  const handleOpenEditor = (productionId: string) => {
    if (onNavigateToEditor) {
      onNavigateToEditor(productionId);
    } else {
      window.location.href = `/productions/${productionId}/editor`;
    }
  };

  // Local file validation
  const handleFileChange = (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      setErrorMessage(null);
      return;
    }

    const validExtensions = [".mp4", ".mov", ".webm", ".mkv", ".m4v"];
    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!validExtensions.includes(ext)) {
      setErrorMessage("Please select a valid video file (.mp4, .mov, .webm, or .mkv)");
      setSelectedFile(null);
      return;
    }

    if (file.size <= 0) {
      setErrorMessage("Selected file is empty (0 bytes)");
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setErrorMessage("File exceeds 1 GB maximum upload limit");
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    setUploadStatus("idle");
    setUploadProgress(0);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  // Start GCS upload and auto-navigate upon completion
  const handleStartUpload = async () => {
    if (!selectedFile || !firebaseUser) return;

    setUploadStatus("initiating");
    setErrorMessage(null);

    try {
      const token = await firebaseUser.getIdToken();

      // 1. Request pre-signed upload URL from backend
      const initResponse = await fetch("/api/productions/upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: selectedFile.name,
          content_type: selectedFile.type || "video/mp4",
          size_bytes: selectedFile.size,
          channel_id: SAMPLE_CHANNEL_ID,
        }),
      });

      if (!initResponse.ok) {
        const errorData = await initResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to initialize video upload session");
      }

      const uploadData: CreateUploadResponse = await initResponse.json();
      const { upload_url, production_id } = uploadData;

      // 2. Direct binary PUT upload to Google Cloud Storage
      setUploadStatus("uploading");

      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        activeXhrRef.current = xhr;

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            setUploadProgress(percent);
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Storage upload failed with HTTP ${xhr.status}`));
          }
        };

        xhr.onerror = () => {
          reject(new Error("Network connection error during file upload"));
        };

        xhr.onabort = () => {
          reject(new Error("Upload aborted"));
        };

        xhr.open("PUT", upload_url, true);
        xhr.setRequestHeader("Content-Type", selectedFile.type || "video/mp4");
        xhr.send(selectedFile);
      });

      // 3. Verify upload with backend
      setUploadStatus("verifying");

      const verifyResponse = await fetch(`/api/productions/${production_id}/verify-upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!verifyResponse.ok) {
        const errorData = await verifyResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload verification failed");
      }

      // 4. Ready -> auto-navigate to editor
      setUploadStatus("uploaded");
      setUploadProgress(100);

      // Brief 500ms delay so the user sees verified state before smooth transition
      setTimeout(() => {
        handleOpenEditor(production_id);
      }, 500);
    } catch (err: unknown) {
      setUploadStatus("failed");
      setErrorMessage(
        err instanceof Error ? err.message : "An unexpected error occurred during upload",
      );
    } finally {
      activeXhrRef.current = null;
    }
  };

  const handleResetUpload = () => {
    if (activeXhrRef.current) {
      activeXhrRef.current.abort();
      activeXhrRef.current = null;
    }
    setSelectedFile(null);
    setUploadStatus("idle");
    setUploadProgress(0);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col font-sans select-none">
      {/* 1. App Shell Top Navigation: Consistent with Home/AppPage */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onNavigateHome}
            className="hover:opacity-80 transition-opacity flex items-center gap-2 shrink-0"
            title="Back to Home"
            aria-label="Back to Home"
          >
            <CroviqLogo height={24} className="h-6 w-auto shrink-0" />
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <span className="text-xs font-semibold text-text-primary tracking-tight">
            New Project
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2/60 px-2.5 py-1 text-xs text-text-secondary">
            <span className="flex h-3.5 w-3.5 items-center justify-center rounded text-[8px] font-bold bg-primary/20 text-primary">
              C
            </span>
            <span className="font-medium text-[11px]">Croviq Sample Channel</span>
          </div>

          <div className="flex items-center gap-2 border-l border-border-subtle pl-3">
            <span className="text-xs text-text-muted hidden sm:inline">{user?.email}</span>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-transparent hover:border-border-subtle"
              title="Sign out"
            >
              <LogOut className="size-3.5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. Main Content: Centered, purposeful upload card */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 md:p-10">
        <div className="w-full max-w-xl flex flex-col gap-6">
          <div className="text-center space-y-1.5">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary">
              Upload raw footage
            </h1>
            <p className="text-xs sm:text-sm text-text-secondary max-w-md mx-auto">
              Drop a video to start a new production. Croviq will analyze, edit, review, and render
              it automatically.
            </p>
          </div>

          <div className="bg-surface-1 border border-border-subtle rounded-xl p-6 shadow-xl flex flex-col gap-5">
            {!selectedFile ? (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className={`flex flex-col items-center justify-center p-8 sm:p-10 border-2 border-dashed rounded-lg cursor-pointer transition-all ${
                  isDragOver
                    ? "border-primary bg-primary/5 scale-[1.01]"
                    : "border-border-strong hover:border-primary/60 hover:bg-surface-2/50"
                }`}
                role="button"
                tabIndex={0}
                aria-label="Upload video area"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                  accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mkv,.mp4,.mov,.webm"
                  className="hidden"
                />

                <div className="w-12 h-12 rounded-full bg-surface-2 border border-border-subtle flex items-center justify-center text-text-secondary mb-4 shadow-sm">
                  <Upload className="w-5 h-5 text-primary" />
                </div>

                <div className="text-center space-y-1">
                  <p className="text-xs sm:text-sm font-semibold text-text-primary">
                    Click to browse or drag and drop video
                  </p>
                  <p className="text-[11px] text-text-muted">MP4 · MOV · WebM · MKV (up to 1 GB)</p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4 p-4 rounded-lg bg-surface-2 border border-border-subtle">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-surface-3 border border-border-subtle flex items-center justify-center text-primary shrink-0">
                      <Video className="w-5 h-5" />
                    </div>
                    <div className="min-w-0 flex flex-col">
                      <span className="text-xs font-semibold text-text-primary truncate">
                        {selectedFile.name}
                      </span>
                      <span className="text-[11px] text-text-muted tabular-nums font-mono">
                        {formatBytes(selectedFile.size)}
                      </span>
                    </div>
                  </div>

                  {uploadStatus === "idle" && (
                    <button
                      type="button"
                      onClick={handleResetUpload}
                      className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded-md transition-colors"
                      title="Remove file"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Progress bar and status indication */}
                {uploadStatus !== "idle" && (
                  <div className="flex flex-col gap-2 pt-2 border-t border-border-subtle">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-secondary flex items-center gap-1.5">
                        {uploadStatus === "initiating" && (
                          <>
                            <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                            <span>Initiating upload session…</span>
                          </>
                        )}
                        {uploadStatus === "uploading" && (
                          <>
                            <HardDrive className="w-3.5 h-3.5 text-primary animate-pulse" />
                            <span>Uploading directly to storage…</span>
                          </>
                        )}
                        {uploadStatus === "verifying" && (
                          <>
                            <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                            <span>Inspecting media…</span>
                          </>
                        )}
                        {uploadStatus === "uploaded" && (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-emerald-400 font-medium">
                              Ready — opening editor…
                            </span>
                          </>
                        )}
                        {uploadStatus === "failed" && (
                          <>
                            <AlertCircle className="w-3.5 h-3.5 text-danger" />
                            <span className="text-danger font-medium">Upload failed</span>
                          </>
                        )}
                      </span>
                      <span className="font-mono text-text-primary font-medium tabular-nums">
                        {uploadProgress}%
                      </span>
                    </div>

                    <div className="w-full h-1.5 bg-surface-3 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-150 ${
                          uploadStatus === "uploaded"
                            ? "bg-emerald-400"
                            : uploadStatus === "failed"
                              ? "bg-danger"
                              : "bg-primary"
                        }`}
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  </div>
                )}

                {errorMessage && (
                  <div className="p-3 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{errorMessage}</span>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2.5 pt-1">
                  {uploadStatus === "idle" && (
                    <button
                      type="button"
                      onClick={handleStartUpload}
                      className="px-4 py-2 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5 shadow-sm"
                    >
                      <Upload className="w-3.5 h-3.5" />
                      <span>Start production</span>
                    </button>
                  )}

                  {uploadStatus === "failed" && (
                    <>
                      <button
                        type="button"
                        onClick={handleResetUpload}
                        className="px-3 py-1.5 bg-surface-3 text-text-primary hover:bg-elevated text-xs font-medium rounded-md transition-colors border border-border-subtle"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleStartUpload}
                        className="px-3.5 py-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded-md transition-colors"
                      >
                        Retry
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}

            {!selectedFile && errorMessage && (
              <div className="p-3 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};
