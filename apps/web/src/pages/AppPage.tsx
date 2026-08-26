import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileVideo,
  HardDrive,
  LogOut,
  Upload,
  Video,
  X,
  ArrowRight,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import type { components } from "../api/generated";

type Production = components["schemas"]["Production"];
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

interface AppPageProps {
  onNavigateToEditor?: (productionId: string) => void;
}

export const AppPage: React.FC<AppPageProps> = ({ onNavigateToEditor }) => {
  const { user, firebaseUser, logout } = useAuth();

  // Channel Selection State - Defaulted to canonical channel automatically
  const [selectedChannelId] = useState<string>(SAMPLE_CHANNEL_ID);

  // Upload Flow State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "initiating" | "uploading" | "verifying" | "uploaded" | "failed"
  >("idle");
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [activeUploadId, setActiveUploadId] = useState<string | null>(null);
  const [activeProductionId, setActiveProductionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeXhrRef = useRef<XMLHttpRequest | null>(null);

  // Recent Productions List
  const [productions, setProductions] = useState<Production[]>([]);
  const [isLoadingProductions, setIsLoadingProductions] = useState<boolean>(false);

  const fetchProductions = useCallback(async () => {
    if (!firebaseUser) return;
    setIsLoadingProductions(true);
    try {
      const token = await firebaseUser.getIdToken();

      // Ensure workspace is initialized in background
      fetch("/api/workspace", {
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});

      // Load productions
      try {
        const res = await fetch("/api/productions", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setProductions(data.productions || []);
        }
      } catch {
        // Non-blocking
      }
    } catch {
      // Non-blocking
    } finally {
      setIsLoadingProductions(false);
    }
  }, [firebaseUser]);

  useEffect(() => {
    fetchProductions();
  }, [fetchProductions]);

  // Handle file selection and local validation
  const handleFileChange = (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      setErrorMessage(null);
      return;
    }

    const validExtensions = [".mp4", ".mov", ".webm", ".mkv", ".m4v"];
    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!validExtensions.includes(ext)) {
      setErrorMessage("Please select a valid video file (.mp4, .mov, or .webm)");
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

  // Execute direct GCS upload
  const handleStartUpload = async () => {
    if (!selectedFile || !firebaseUser || !selectedChannelId) return;

    setUploadStatus("initiating");
    setErrorMessage(null);
    setUploadProgress(0);

    try {
      const token = await firebaseUser.getIdToken();

      let contentType = selectedFile.type;
      if (!contentType) {
        if (selectedFile.name.endsWith(".mp4")) contentType = "video/mp4";
        else if (selectedFile.name.endsWith(".mov")) contentType = "video/quicktime";
        else if (selectedFile.name.endsWith(".webm")) contentType = "video/webm";
        else if (selectedFile.name.endsWith(".mkv")) contentType = "video/x-matroska";
        else if (selectedFile.name.endsWith(".m4v")) contentType = "video/mp4";
        else contentType = "video/mp4";
      }

      // Step 1: Initiate upload with backend
      const initRes = await fetch("/api/uploads", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          filename: selectedFile.name,
          content_type: contentType,
          size_bytes: selectedFile.size,
          channel_id: selectedChannelId,
        }),
      });

      if (!initRes.ok) {
        const errorData = await initRes.json().catch(() => ({}));
        throw new Error(errorData.detail || `Upload registration failed (${initRes.status})`);
      }

      const uploadTarget: CreateUploadResponse = await initRes.json();
      setActiveUploadId(uploadTarget.upload_id);
      setActiveProductionId(uploadTarget.production_id);

      // Step 2: Upload directly to storage via signed PUT URL
      setUploadStatus("uploading");

      const xhr = new XMLHttpRequest();
      activeXhrRef.current = xhr;

      xhr.open(uploadTarget.method || "PUT", uploadTarget.upload_url, true);

      if (uploadTarget.required_headers) {
        for (const [headerKey, headerVal] of Object.entries(uploadTarget.required_headers)) {
          xhr.setRequestHeader(headerKey, String(headerVal));
        }
      }
      xhr.upload.onprogress = (progressEvent) => {
        if (progressEvent.lengthComputable) {
          const percentComplete = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          setUploadProgress(percentComplete);
        }
      };

      xhr.onload = async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          // Step 3: Verify and complete upload on backend
          setUploadStatus("verifying");
          try {
            const currentToken = await firebaseUser.getIdToken();
            const compRes = await fetch(`/api/uploads/${uploadTarget.upload_id}/complete`, {
              method: "POST",
              headers: {
                Authorization: `Bearer ${currentToken}`,
              },
            });

            if (!compRes.ok) {
              const compErr = await compRes.json().catch(() => ({}));
              throw new Error(compErr.detail || "Storage verification failed");
            }

            const finalProduction: Production = await compRes.json();
            setUploadStatus("uploaded");
            setUploadProgress(100);
            setActiveProductionId(finalProduction.production_id);
            fetchProductions();
          } catch (err: unknown) {
            setUploadStatus("failed");
            setErrorMessage(err instanceof Error ? err.message : "Verification failed");
          }
        } else {
          setUploadStatus("failed");
          setErrorMessage(`Storage upload failed with HTTP status ${xhr.status}`);
        }
      };

      xhr.onerror = () => {
        setUploadStatus("failed");
        setErrorMessage("Network error during direct storage upload");
      };

      xhr.send(selectedFile);
    } catch (err: unknown) {
      setUploadStatus("failed");
      setErrorMessage(err instanceof Error ? err.message : "Upload initialization failed");
    }
  };

  const handleResetUpload = () => {
    if (activeXhrRef.current && uploadStatus === "uploading") {
      activeXhrRef.current.abort();
    }
    setSelectedFile(null);
    setUploadStatus("idle");
    setUploadProgress(0);
    setActiveUploadId(null);
    setActiveProductionId(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleOpenProduction = (productionId: string) => {
    if (onNavigateToEditor) {
      onNavigateToEditor(productionId);
    } else {
      window.history.pushState(null, "", `/productions/${productionId}/editor`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col font-sans selection:bg-primary/25">
      {/* App Header Bar */}
      <header className="h-14 bg-surface-1 border-b border-border-subtle px-4 sm:px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <CroviqLogo height={24} className="h-6 w-auto" />
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">
            {user?.email || "demo@croviq.app"}
          </span>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-transparent hover:border-border-subtle"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Logout</span>
          </button>
        </div>
      </header>

      {/* Main Viewport */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-8 flex flex-col gap-8">
        {/* Intro */}
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-bold tracking-tight text-text-primary">
            Croviq
          </h1>
          <p className="text-xs text-text-secondary">
            Your autonomous video production team.
          </p>
        </div>

        {/* Upload Station */}
        <section className="p-6 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-4 shadow-sm">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-text-primary">
              Drop your raw video
            </h2>
            <p className="text-xs text-text-muted mt-0.5">
              MP4 &middot; MOV &middot; WebM &middot; MKV &middot; up to 1 GB
            </p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".mp4,.mov,.webm,.mkv,.m4v,video/mp4,video/quicktime,video/webm,video/x-matroska"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileChange(e.target.files[0]);
              }
            }}
          />

          {!selectedFile ? (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border border-dashed rounded-lg p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-150 ${
                isDragOver
                  ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                  : "border-border-strong hover:border-text-secondary bg-surface-2/40 hover:bg-surface-2/70"
              }`}
            >
              <div className="w-10 h-10 rounded-full bg-surface-3 flex items-center justify-center mb-3 text-text-secondary border border-border-subtle">
                <Upload className="w-4 h-4 text-primary" />
              </div>
              <p className="text-xs font-medium text-text-primary">
                Drop your raw video here, or{" "}
                <span className="text-primary underline font-semibold">browse</span>
              </p>
              <p className="text-[11px] text-text-muted mt-1 font-mono">
                MP4 &middot; MOV &middot; WebM &middot; MKV &middot; up to 1 GB
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3.5 p-4 rounded-lg bg-surface-2 border border-border-subtle">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-md bg-surface-3 border border-border-subtle flex items-center justify-center shrink-0">
                    <FileVideo className="w-4 h-4 text-primary" />
                  </div>
                  <div className="min-w-0 flex flex-col">
                    <span className="text-xs font-medium text-text-primary truncate">
                      {selectedFile.name}
                    </span>
                    <span className="text-[11px] text-text-muted tabular-nums">
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
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {uploadStatus !== "idle" && (
                <div className="flex flex-col gap-2 pt-2 border-t border-border-subtle">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary flex items-center gap-1.5">
                      {uploadStatus === "initiating" && "Initiating upload session..."}
                      {uploadStatus === "uploading" && (
                        <>
                          <HardDrive className="w-3.5 h-3.5 text-primary animate-pulse" />
                          <span>Uploading...</span>
                        </>
                      )}
                      {uploadStatus === "verifying" && "Verifying upload..."}
                      {uploadStatus === "uploaded" && (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                          <span className="text-success font-medium">Uploaded</span>
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
                          ? "bg-success"
                          : uploadStatus === "failed"
                            ? "bg-danger"
                            : "bg-primary"
                      }`}
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {uploadStatus === "uploaded" && activeProductionId && (
                <div className="p-3 bg-success/10 border border-success/20 rounded-md text-xs text-text-primary flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-success font-medium">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>Upload complete</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleOpenProduction(activeProductionId)}
                    className="px-3 py-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5 shadow-sm shrink-0"
                  >
                    <span>Open Editor</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {errorMessage && (
                <div className="p-2.5 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger flex items-center gap-2">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-1">
                {uploadStatus === "idle" && (
                  <button
                    type="button"
                    onClick={handleStartUpload}
                    className="px-3.5 py-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5 shadow-sm"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>Upload video</span>
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
                      Retry Upload
                    </button>
                  </>
                )}

                {uploadStatus === "uploaded" && (
                  <button
                    type="button"
                    onClick={handleResetUpload}
                    className="px-3 py-1.5 bg-surface-3 text-text-primary hover:bg-elevated text-xs font-medium rounded-md transition-colors border border-border-subtle"
                  >
                    Upload another video
                  </button>
                )}
              </div>
            </div>
          )}

          {!selectedFile && errorMessage && (
            <div className="p-2.5 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </section>

        {/* Recent Productions */}
        <section className="p-6 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold tracking-tight text-text-primary">
              Recent productions
            </h2>
          </div>

          {isLoadingProductions ? (
            <div className="p-8 rounded-lg bg-surface-2/40 border border-border-subtle text-center text-xs text-text-muted">
              Loading recent productions...
            </div>
          ) : productions.length === 0 ? (
            <div className="py-10 px-4 rounded-lg bg-surface-2/30 border border-border-subtle text-center flex flex-col items-center justify-center gap-2">
              <div className="w-8 h-8 rounded-full bg-surface-3 flex items-center justify-center text-text-muted">
                <Video className="w-4 h-4" />
              </div>
              <p className="text-xs text-text-secondary font-medium">
                No productions yet.
              </p>
              <p className="text-xs text-text-muted">
                Drop a video above to begin.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2.5" data-testid="productions-list">
              {productions.map((prod) => (
                <div
                  key={prod.production_id}
                  onClick={() => handleOpenProduction(prod.production_id)}
                  className="p-3.5 rounded-lg bg-surface-2/70 hover:bg-surface-2 border border-border-subtle hover:border-primary/40 transition-all flex items-center justify-between gap-3 cursor-pointer group"
                  data-testid={`production-row-${prod.production_id}`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-surface-3 border border-border-subtle flex items-center justify-center shrink-0 group-hover:border-primary/40 transition-colors">
                      <FileVideo className="w-5 h-5 text-primary" />
                    </div>
                    <div className="min-w-0 flex flex-col">
                      <span className="text-xs font-semibold text-text-primary truncate group-hover:text-primary transition-colors">
                        {prod.source_media?.original_filename || "Untitled Production"}
                      </span>
                      <div className="flex items-center gap-2 text-[11px] text-text-muted mt-0.5">
                        {prod.source_media?.size_bytes ? (
                          <>
                            <span className="tabular-nums">
                              {formatBytes(prod.source_media.size_bytes)}
                            </span>
                            <span>&middot;</span>
                          </>
                        ) : null}
                        <span>
                          {new Date(prod.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${
                        prod.status === "uploaded"
                          ? "bg-success/10 text-success border-success/20"
                          : prod.status === "failed"
                            ? "bg-danger/10 text-danger border-danger/20"
                            : "bg-primary/10 text-primary border-primary/20"
                      }`}
                    >
                      {prod.status}
                    </span>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenProduction(prod.production_id);
                      }}
                      className="px-3 py-1.5 bg-surface-3 hover:bg-primary hover:text-white text-text-secondary text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 border border-border-subtle hover:border-transparent"
                    >
                      <span>Open Editor</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
};
