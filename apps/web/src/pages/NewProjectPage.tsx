import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  LogOut,
  Upload,
  Video,
  X,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import type { components } from "../api/generated";
import { RecentProjectsList } from "../components/projects/RecentProjectsList";

type CreateUploadResponse = components["schemas"]["CreateUploadResponse"];
type Production = components["schemas"]["Production"];

const SAMPLE_CHANNEL_ID = "croviq_syn_ai_eng_01";
const MAX_UPLOAD_BYTES = 1 * 1024 * 1024 * 1024; // 1 GB

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / k ** i).toFixed(1))} ${sizes[i]}`;
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
  const [productions, setProductions] = useState<Production[]>([]);
  const [isLoadingProductions, setIsLoadingProductions] = useState<boolean>(true);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeXhrRef = useRef<XMLHttpRequest | null>(null);

  const loadProductions = useCallback(async () => {
    if (!firebaseUser) return;
    setIsLoadingProductions(true);
    try {
      const token = await firebaseUser.getIdToken();
      const response = await fetch("/api/productions", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setProductions(data.productions || []);
      }
    } catch {
      // Non-blocking productions list
    } finally {
      setIsLoadingProductions(false);
    }
  }, [firebaseUser]);

  useEffect(() => {
    void loadProductions();
  }, [loadProductions]);

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
    if (e.dataTransfer.files?.[0]) {
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
      const initResponse = await fetch("/api/uploads", {
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
      const { upload_id, upload_url, production_id } = uploadData;

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

      const verifyResponse = await fetch(`/api/uploads/${upload_id}/complete`, {
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

      // Brief delay so the user sees verified state before smooth transition
      setTimeout(() => {
        handleOpenEditor(production_id);
      }, 400);
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
            title="Back to Channel Intelligence"
            aria-label="Back to Channel Intelligence"
          >
            <CroviqLogo height={24} className="h-6 w-auto shrink-0" />
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <span className="text-xs font-semibold text-text-primary tracking-tight">
            New Project
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onNavigateHome}
            className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-2/60 px-3 py-1.5 text-xs text-text-secondary hover:border-border-strong hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Channel Intelligence</span>
          </button>

          <div className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2/60 px-2.5 py-1 text-xs text-text-secondary">
            <span className="flex h-3.5 w-3.5 items-center justify-center rounded text-[8px] font-bold bg-primary/20 text-primary">
              C
            </span>
            <span className="font-medium text-[11px]">Croviq Sample Channel</span>
          </div>

          <div className="hidden md:flex items-center gap-2 border-l border-border-subtle pl-3">
            <span className="text-xs text-text-muted">{user?.email}</span>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-transparent hover:border-border-subtle"
              title="Sign out"
            >
              <LogOut className="size-3.5" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. Main Content Layout: Structured 65% / 35% grid matching Croviq shell */}
      <main className="flex-1 py-8 px-4 sm:px-6 lg:px-8 max-w-[1400px] mx-auto w-full space-y-8">
        {/* Header & Obvious Back Action */}
        <div className="flex items-center justify-between border-b border-border-subtle pb-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary">
              New Project
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-text-secondary">
              Start with raw footage — Croviq will analyze, edit, review and render it
              automatically.
            </p>
          </div>

          <button
            type="button"
            onClick={onNavigateHome}
            className="text-xs font-semibold text-primary hover:underline flex items-center gap-1.5"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Channel Intelligence</span>
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,65%)_minmax(0,35%)] gap-8 items-start">
          {/* Left Column: Upload Dropzone Card (65%) */}
          <div className="space-y-4">
            <div className="bg-surface-1 border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary flex items-center gap-2">
                  <Upload className="h-4 w-4 text-primary" />
                  Start with raw footage
                </span>
                <span className="text-[11px] text-text-muted">Max 1 GB</span>
              </div>

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
                    accept=".mp4,.mov,.webm,.mkv,.m4v"
                    className="hidden"
                  />

                  <div className="h-12 w-12 rounded-full bg-surface-2 flex items-center justify-center text-text-secondary mb-3 shadow-inner">
                    <Upload className="size-6 text-primary" />
                  </div>

                  <p className="text-sm font-semibold text-text-primary text-center">
                    Click to browse or drag and drop video
                  </p>
                  <p className="text-xs text-text-muted mt-1 text-center">
                    MP4, MOV, WEBM, or MKV (up to 1 GB)
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between p-3.5 bg-surface-2/80 rounded-lg border border-border-subtle">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 rounded bg-surface-3 text-text-primary shrink-0">
                        <Video className="size-5 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-text-primary truncate">
                          {selectedFile.name}
                        </p>
                        <p className="text-[11px] text-text-muted">
                          {formatBytes(selectedFile.size)}
                        </p>
                      </div>
                    </div>

                    {uploadStatus === "idle" && (
                      <button
                        onClick={handleResetUpload}
                        className="p-1 text-text-muted hover:text-text-primary rounded hover:bg-surface-3 transition-colors"
                        title="Remove file"
                        aria-label="Remove selected file"
                      >
                        <X className="size-4" />
                      </button>
                    )}
                  </div>

                  {/* Dynamic Upload Progress & State */}
                  {uploadStatus !== "idle" && (
                    <div className="space-y-2.5 bg-surface-2/40 p-3.5 rounded-lg border border-border-subtle">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-text-secondary flex items-center gap-2">
                          {uploadStatus === "initiating" && (
                            <>
                              <Loader2 className="size-3.5 animate-spin text-primary" />
                              Initializing session...
                            </>
                          )}
                          {uploadStatus === "uploading" && (
                            <>
                              <Loader2 className="size-3.5 animate-spin text-primary" />
                              Uploading {uploadProgress}%
                            </>
                          )}
                          {uploadStatus === "verifying" && (
                            <>
                              <Loader2 className="size-3.5 animate-spin text-primary" />
                              Inspecting media...
                            </>
                          )}
                          {uploadStatus === "uploaded" && (
                            <>
                              <CheckCircle2 className="size-3.5 text-success" />
                              Opening Editor...
                            </>
                          )}
                        </span>
                        <span className="font-mono text-text-primary">{uploadProgress}%</span>
                      </div>

                      <div className="w-full bg-surface-3 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-primary h-full transition-all duration-200"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Error Notification */}

                  {/* Action Buttons */}
                  <div className="flex items-center justify-end gap-3 pt-2">
                    {uploadStatus === "idle" && (
                      <button
                        onClick={handleResetUpload}
                        className="px-3.5 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors"
                      >
                        Cancel
                      </button>
                    )}

                    <button
                      onClick={handleStartUpload}
                      disabled={uploadStatus !== "idle" && uploadStatus !== "failed"}
                      className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-semibold transition-all shadow-sm disabled:opacity-50"
                    >
                      {uploadStatus === "idle" && (
                        <>
                          <Upload className="size-3.5" />
                          <span>Start Production</span>
                        </>
                      )}
                      {uploadStatus === "failed" && <span>Retry Upload</span>}
                      {(uploadStatus === "initiating" ||
                        uploadStatus === "uploading" ||
                        uploadStatus === "verifying") && (
                        <>
                          <Loader2 className="size-3.5 animate-spin" />
                          <span>Processing...</span>
                        </>
                      )}
                      {uploadStatus === "uploaded" && <span>Success</span>}
                    </button>
                  </div>
                </div>
              )}

              {/* Error Notification */}
              {errorMessage && (
                <div
                  role="alert"
                  className="p-3 bg-danger/10 border border-danger/20 rounded-lg flex items-start gap-2 text-danger text-xs"
                >
                  <AlertCircle className="size-4 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-semibold">Upload failed</p>
                    <p className="text-[11px] opacity-90">{errorMessage}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Compact Recent Projects */}
          <div>
            <RecentProjectsList
              productions={productions}
              isLoading={isLoadingProductions}
              onOpenProject={handleOpenEditor}
            />
          </div>
        </div>
      </main>
    </div>
  );
};
