import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Cpu,
  FileVideo,
  HardDrive,
  Layers,
  LogOut,
  Radio,
  Sparkles,
  Upload,
  Video,
  X,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import type { components } from "../api/generated";
type Production = components["schemas"]["Production"];
type CreateUploadResponse = components["schemas"]["CreateUploadResponse"];

const SAMPLE_CHANNEL_ID = "croviq_syn_ai_eng_01";
const SAMPLE_CHANNEL_TITLE = "Synthetic AI Engineering (~50k subs)";
const MAX_UPLOAD_BYTES = 1 * 1024 * 1024 * 1024; // 1 GB (1,073,741,824 bytes)

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

export const AppPage: React.FC = () => {
  const { user, firebaseUser, logout } = useAuth();

  // Channel Selection State
  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(SAMPLE_CHANNEL_ID);

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
  // Workspace State
  const [workspaceName, setWorkspaceName] = useState<string>("Croviq Demo Workspace");

  // Recent Productions List
  const [productions, setProductions] = useState<Production[]>([]);
  const [isLoadingProductions, setIsLoadingProductions] = useState<boolean>(false);
  const fetchProductions = useCallback(async () => {
    if (!firebaseUser) return;
    setIsLoadingProductions(true);
    try {
      const token = await firebaseUser.getIdToken();

      // Load workspace in parallel
      fetch("/api/workspace", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((ws) => {
          if (ws && ws.name) setWorkspaceName(ws.name);
        })
        .catch(() => {});

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
        // Non-blocking for page render
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

    const validExtensions = [".mp4", ".mov", ".webm", ".m4v"];
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

      // Normalize MIME content-type
      let contentType = selectedFile.type;
      if (!contentType) {
        if (selectedFile.name.endsWith(".mp4")) contentType = "video/mp4";
        else if (selectedFile.name.endsWith(".mov")) contentType = "video/quicktime";
        else if (selectedFile.name.endsWith(".webm")) contentType = "video/webm";
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

      // Step 2: Upload directly to private GCS via signed PUT URL
      setUploadStatus("uploading");

      const xhr = new XMLHttpRequest();
      activeXhrRef.current = xhr;

      xhr.open(uploadTarget.method || "PUT", uploadTarget.upload_url, true);

      // Apply required headers
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

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col font-sans selection:bg-primary/25">
      {/* Studio Header Bar */}
      <header className="h-12 bg-surface-1 border-b border-border-subtle px-4 sm:px-6 flex items-center justify-between shrink-0 sticky top-0 z-30 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <CroviqLogo height={24} className="h-6 w-auto" />
          <span className="text-border-strong select-none font-light">/</span>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-text-primary tracking-tight">
              {workspaceName}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-2 border border-border-subtle text-[11px] text-text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            <span className="text-text-muted">Engine Online</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-2 border border-border-subtle text-xs text-text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
            <span className="font-mono text-text-muted text-[11px]">
              {user?.email || "creator@croviq.app"}
            </span>
          </div>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-transparent hover:border-border-subtle"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Studio Workbench Viewport */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 flex flex-col gap-5">
        {/* Studio Banner & Identity */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-1 border-b border-border-subtle/50">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold tracking-tight text-text-primary">Croviq</h1>
              <span className="px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase bg-primary/10 text-primary border border-primary/20 rounded">
                Production Studio
              </span>
            </div>
            <p className="text-xs text-text-secondary mt-0.5">
              DevOps for YouTube Creators &middot; Autonomous Production Studio
            </p>
          </div>

          {selectedChannelId && (
            <div className="flex items-center gap-1.5 self-start sm:self-auto text-[11px] text-text-muted bg-surface-1 px-2.5 py-1 rounded-md border border-border-subtle">
              <Sparkles className="w-3 h-3 text-primary shrink-0" />
              <span className="text-text-secondary font-medium">{SAMPLE_CHANNEL_TITLE}</span>
            </div>
          )}
        </div>

        {/* Workbench Split: Intake Station (Left) + Channel Context (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Intake Station & Active Workflow (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            {/* Upload / Ingestion Station */}
            <section className="p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold tracking-tight text-text-primary">
                    What are we making?
                  </h2>
                  <p className="text-xs text-text-muted mt-0.5">
                    Upload raw video footage. The browser uploads directly to private cloud storage.
                  </p>
                </div>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono text-text-muted bg-surface-2 rounded border border-border-subtle">
                  Direct GCS
                </span>
              </div>

              {/* Hidden File Input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp4,.mov,.webm,.m4v,video/mp4,video/quicktime,video/webm"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileChange(e.target.files[0]);
                  }
                }}
              />

              {/* Drop Zone when no file selected */}
              {!selectedFile ? (
                <div
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border border-dashed rounded-lg p-6 sm:p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-150 ${
                    isDragOver
                      ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                      : "border-border-strong hover:border-text-secondary bg-surface-2/40 hover:bg-surface-2/70"
                  }`}
                >
                  <div className="w-10 h-10 rounded-full bg-surface-3 flex items-center justify-center mb-2.5 text-text-secondary border border-border-subtle group-hover:scale-105 transition-transform">
                    <Upload className="w-4 h-4 text-primary" />
                  </div>
                  <p className="text-xs font-medium text-text-primary">
                    Drop your raw video here, or{" "}
                    <span className="text-primary underline font-semibold">browse</span>
                  </p>
                  <p className="text-[11px] text-text-muted mt-1 font-mono">
                    MP4, MOV, or WebM &middot; Up to 1 GB &middot; Direct upload
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-3.5 p-4 rounded-lg bg-surface-2 border border-border-subtle">
                  {/* Selected File Details */}
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

                  {/* Progress Bar & Status Text during upload */}
                  {uploadStatus !== "idle" && (
                    <div className="flex flex-col gap-2 pt-2 border-t border-border-subtle">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-text-secondary flex items-center gap-1.5">
                          {uploadStatus === "initiating" && "Initiating upload session..."}
                          {uploadStatus === "uploading" && (
                            <>
                              <HardDrive className="w-3.5 h-3.5 text-primary animate-pulse" />
                              <span>Uploading directly to storage...</span>
                            </>
                          )}
                          {uploadStatus === "verifying" && "Verifying upload in storage..."}
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

                      {/* Progress Bar Track */}
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

                  {/* Success Result Details */}
                  {uploadStatus === "uploaded" && (
                    <div className="p-3 bg-success/10 border border-success/20 rounded-md text-xs text-text-primary flex flex-col gap-1">
                      <div className="flex items-center gap-1.5 font-medium text-success">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Production recorded and ready for analysis</span>
                      </div>
                      {activeProductionId && (
                        <span className="font-mono text-text-secondary text-[11px]">
                          Production ID: {activeProductionId}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Error Banner */}
                  {errorMessage && (
                    <div className="p-2.5 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger flex items-center gap-2">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      <span>{errorMessage}</span>
                    </div>
                  )}

                  {/* Action Buttons */}
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

              {/* Inline Error for drag/drop rejection */}
              {!selectedFile && errorMessage && (
                <div className="p-2.5 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger flex items-center gap-2">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}
            </section>

            {/* Autonomous Production Pipeline HUD */}
            <div className="p-3.5 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-text-secondary flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-primary" />
                  <span>Autonomous Production Team</span>
                </span>
                <span className="text-[11px] text-text-muted font-mono">5 Agents Active</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                <div className="p-2 rounded bg-surface-2 border border-border-subtle flex flex-col gap-0.5">
                  <span className="text-[10px] font-semibold text-text-primary flex items-center gap-1">
                    <span>🎬</span> Maya
                  </span>
                  <span className="text-[10px] text-text-muted leading-tight">Director</span>
                </div>
                <div className="p-2 rounded bg-surface-2 border border-border-subtle flex flex-col gap-0.5">
                  <span className="text-[10px] font-semibold text-text-primary flex items-center gap-1">
                    <span>✂️</span> Leo
                  </span>
                  <span className="text-[10px] text-text-muted leading-tight">Dialogue Editor</span>
                </div>
                <div className="p-2 rounded bg-surface-2 border border-border-subtle flex flex-col gap-0.5">
                  <span className="text-[10px] font-semibold text-text-primary flex items-center gap-1">
                    <span>📊</span> Alex
                  </span>
                  <span className="text-[10px] text-text-muted leading-tight">Data Scientist</span>
                </div>
                <div className="p-2 rounded bg-surface-2 border border-border-subtle flex flex-col gap-0.5">
                  <span className="text-[10px] font-semibold text-text-primary flex items-center gap-1">
                    <span>🔍</span> Iris
                  </span>
                  <span className="text-[10px] text-text-muted leading-tight">QA Lead</span>
                </div>
                <div className="p-2 rounded bg-surface-2 border border-border-subtle flex flex-col gap-0.5 col-span-2 sm:col-span-1">
                  <span className="text-[10px] font-semibold text-text-primary flex items-center gap-1">
                    <span>📦</span> Nina
                  </span>
                  <span className="text-[10px] text-text-muted leading-tight">Packaging</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Studio Intelligence & Channel Config (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* Channel Selection & Sources */}
            <section className="p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-3.5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold tracking-tight text-text-primary">
                  Studio Channel
                </h2>
                <span className="text-[11px] text-text-muted">Target profile</span>
              </div>

              <div className="flex flex-col gap-3">
                {/* Sample Channel Card */}
                <div
                  className={`p-3.5 rounded-lg border transition-all flex flex-col gap-2.5 ${
                    selectedChannelId === SAMPLE_CHANNEL_ID
                      ? "bg-surface-2 border-primary/50 ring-1 ring-primary/20"
                      : "bg-surface-2/60 border-border-subtle hover:border-border-strong"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
                      <Sparkles className="w-3.5 h-3.5 text-primary shrink-0" />
                      <span>Synthetic AI Engineering</span>
                    </div>
                    <span className="px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-primary/15 text-primary border border-primary/25 rounded">
                      Active
                    </span>
                  </div>
                  <p className="text-[11px] text-text-secondary leading-relaxed">
                    ~50k subscribers &middot; 100 historical videos &middot; Pre-computed retention
                    & Memory Bank baselines for Day 1 testing.
                  </p>
                  <button
                    type="button"
                    onClick={() => setSelectedChannelId(SAMPLE_CHANNEL_ID)}
                    className={`w-full py-1.5 px-3 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                      selectedChannelId === SAMPLE_CHANNEL_ID
                        ? "bg-primary text-white hover:bg-primary-hover shadow-sm"
                        : "bg-surface-3 text-text-primary hover:bg-elevated border border-border-subtle"
                    }`}
                  >
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Use Sample Channel</span>
                  </button>
                </div>

                {/* Connect YouTube Card */}
                <div className="p-3.5 rounded-lg border border-border-subtle bg-surface-2/30 flex flex-col gap-2.5 opacity-70">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-text-secondary">
                      <svg
                        className="w-3.5 h-3.5 text-danger fill-current shrink-0"
                        viewBox="0 0 24 24"
                      >
                        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                      </svg>
                      <span>Connect YouTube Channel</span>
                    </div>
                    <span className="px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-surface-3 text-text-muted border border-border-subtle rounded">
                      Coming soon
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed">
                    Direct YouTube channel connection is coming soon. Use the sample channel to
                    continue.
                  </p>
                  <button
                    type="button"
                    disabled
                    className="w-full py-1.5 px-3 text-xs font-medium rounded-md bg-surface-3/80 text-text-muted border border-border-subtle cursor-not-allowed flex items-center justify-center gap-1.5"
                  >
                    <span>Coming soon</span>
                  </button>
                </div>
              </div>
            </section>

            {/* Channel Intelligence Telemetry */}
            <div className="p-4 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-text-secondary flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-success" />
                  <span>Channel Memory Status</span>
                </span>
                <span className="text-[10px] font-mono text-success bg-success/10 px-1.5 py-0.5 rounded border border-success/20">
                  Synchronized
                </span>
              </div>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex items-center justify-between text-text-muted">
                  <span>Memory Provider</span>
                  <span className="text-text-secondary font-mono">Agent Platform</span>
                </div>
                <div className="flex items-center justify-between text-text-muted">
                  <span>Channel Baseline</span>
                  <span className="text-text-secondary">52.4% avg retention</span>
                </div>
                <div className="flex items-center justify-between text-text-muted">
                  <span>Active Directives</span>
                  <span className="text-text-secondary">12 falsifiable lessons</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Full-Width Section: Recent Productions Ledger */}
        <section className="p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle flex flex-col gap-3.5 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold tracking-tight text-text-primary">
                Recent productions
              </h2>
              <span className="px-2 py-0.5 text-[10px] text-text-muted font-mono bg-surface-2 rounded-full border border-border-subtle">
                {productions.length} total
              </span>
            </div>
          </div>

          {isLoadingProductions ? (
            <div className="p-8 rounded-lg bg-surface-2/40 border border-border-subtle text-center text-xs text-text-muted">
              Loading recent productions...
            </div>
          ) : productions.length === 0 ? (
            <div className="py-8 px-4 rounded-lg bg-surface-2/30 border border-border-subtle text-center flex flex-col items-center justify-center gap-2">
              <div className="w-8 h-8 rounded-full bg-surface-3 flex items-center justify-center text-text-muted">
                <Video className="w-4 h-4" />
              </div>
              <p className="text-xs text-text-muted">
                No productions recorded yet. Drop a video above to start.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {productions.map((prod) => (
                <div
                  key={prod.production_id}
                  className="p-3 rounded-lg bg-surface-2 border border-border-subtle hover:border-border-strong transition-colors flex items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded bg-surface-3 border border-border-subtle flex items-center justify-center shrink-0">
                      <FileVideo className="w-4 h-4 text-primary" />
                    </div>
                    <div className="min-w-0 flex flex-col">
                      <span className="text-xs font-semibold text-text-primary truncate">
                        {prod.source_media?.original_filename || prod.production_id}
                      </span>
                      <div className="flex items-center gap-2 text-[11px] text-text-muted mt-0.5">
                        <span className="font-mono">{prod.production_id}</span>
                        {prod.source_media?.size_bytes && (
                          <>
                            <span>&middot;</span>
                            <span className="tabular-nums">
                              {formatBytes(prod.source_media.size_bytes)}
                            </span>
                          </>
                        )}
                        <span>&middot;</span>
                        <span>{new Date(prod.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
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
