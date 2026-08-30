import {
  Check,
  Clock,
  Film,
  Image as ImageIcon,
  Info,
  Loader2,
  Lock,
  UploadCloud,
  X,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";

export const YouTubeIcon: React.FC<{ className?: string }> = ({ className = "size-4" }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
  </svg>
);

export interface VerifiedThumbnailFrame {
  concept_index?: number;
  concept_id?: string;
  headline?: string;
  frame_timestamp_ms?: number;
  formatted_time?: string;
  visual_description?: string;
}

import type { components } from "../../api/generated";

type PublishPreparationResponse = components["schemas"]["PublishPreparationResponse"];

interface PublishConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  prepData: PublishPreparationResponse | null;
  isLoadingPrep: boolean;
  onConfirmPublish: (params: {
    requested_privacy: "private" | "unlisted" | "public";
    made_for_kids: boolean;
    contains_synthetic_media: boolean;
    selected_title: string;
    selected_description: string;
    selected_tags: string[];
    category_id: string;
    thumbnail_frame_ms?: number;
  }) => Promise<void>;
  isPublishing: boolean;
  onGrantUploadAccess: () => void;
  onConnectYouTube: () => void;
}

export const PublishConfirmationModal: React.FC<PublishConfirmationModalProps> = ({
  isOpen,
  onClose,
  prepData,
  isLoadingPrep,
  onConfirmPublish,
  isPublishing,
  onGrantUploadAccess,
  onConnectYouTube,
}) => {
  // Form State
  const [privacy, setPrivacy] = useState<"private" | "unlisted" | "public">("private");
  const [madeForKids, setMadeForKids] = useState<boolean>(false);
  const [containsSyntheticMedia, setContainsSyntheticMedia] = useState<boolean>(false);
  const [titleInput, setTitleInput] = useState<string>("");
  const [descInput, setDescInput] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("28");
  const [selectedFrameIndex, setSelectedFrameIndex] = useState<number>(0);

  // Initialize values when prepData loads
  useEffect(() => {
    if (prepData) {
      setTitleInput(prepData.suggested_title || prepData.master_title || "");
      setDescInput(prepData.suggested_description || "");
      setCategoryId(prepData.suggested_category_id || "28");
      setContainsSyntheticMedia(Boolean(prepData.suggested_synthetic_media));
      setPrivacy("private"); // Privacy ALWAYS defaults to private as required
      setSelectedFrameIndex(0);
    }
  }, [prepData]);

  // Validation
  const titleCharCount = titleInput.length;
  const isTitleValid = titleCharCount > 0 && titleCharCount <= 100;

  const descByteCount = useMemo(() => {
    return new TextEncoder().encode(descInput).length;
  }, [descInput]);
  const isDescValid = descByteCount <= 5000;

  const canSubmit =
    Boolean(prepData?.can_publish) &&
    Boolean(prepData?.has_upload_access) &&
    !prepData?.is_sample_channel &&
    isTitleValid &&
    isDescValid &&
    !isPublishing;

  const selectedThumbnail = (
    prepData?.verified_thumbnail_frames as VerifiedThumbnailFrame[] | undefined
  )?.[selectedFrameIndex];

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-fade-in select-none"
      data-testid="publish-confirmation-modal"
    >
      <div className="bg-surface-1 border border-border-subtle rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between bg-surface-2/60 shrink-0">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-500">
              <YouTubeIcon className="size-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                Publish to YouTube
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  Creator Confirmation
                </span>
              </h2>
              <p className="text-xs text-text-secondary">
                Review verified metadata, privacy, and declarations before external upload.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPublishing}
            className="p-1.5 text-text-muted hover:text-text-primary rounded-lg hover:bg-surface-3 transition-colors disabled:opacity-50"
            data-testid="btn-close-publish-modal"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoadingPrep ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-text-secondary">
              <Loader2 className="size-8 text-primary animate-spin" />
              <span className="text-xs font-medium">
                Loading channel and release package details…
              </span>
            </div>
          ) : (
            <>
              {/* 1. Channel Connection Status Banner */}
              <div
                className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                  prepData?.is_sample_channel
                    ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                    : !prepData?.has_upload_access
                      ? "bg-blue-500/10 border-blue-500/30 text-blue-300"
                      : "bg-surface-2/70 border-border-subtle text-text-primary"
                }`}
                data-testid="section-channel-status"
              >
                <div className="flex items-center gap-3">
                  {prepData?.channel_avatar_url ? (
                    <img
                      src={prepData.channel_avatar_url}
                      alt={prepData.channel_title}
                      className="size-10 rounded-full object-cover border border-border-subtle"
                    />
                  ) : (
                    <div className="size-10 rounded-full bg-surface-3 flex items-center justify-center text-text-muted">
                      <YouTubeIcon className="size-5" />
                    </div>
                  )}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-text-primary">
                        {prepData?.channel_title || "YouTube Channel"}
                      </span>
                      {prepData?.is_sample_channel && (
                        <span className="text-[10px] font-bold px-2 py-0.5 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full">
                          Synthetic Sample Channel
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-text-secondary">
                      {prepData?.is_sample_channel
                        ? "Sample Channel is read-only for testing and cannot upload to YouTube."
                        : prepData?.has_upload_access
                          ? "Publishing permission (youtube.upload) granted."
                          : "Upload permission missing. Incremental authorization required."}
                    </p>
                  </div>
                </div>

                {prepData?.is_sample_channel ? (
                  <button
                    type="button"
                    onClick={onConnectYouTube}
                    className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-black text-xs font-bold rounded-lg transition-colors shadow-xs shrink-0"
                    data-testid="btn-connect-youtube"
                  >
                    Connect YouTube to Publish
                  </button>
                ) : (
                  !prepData?.has_upload_access && (
                    <button
                      type="button"
                      onClick={onGrantUploadAccess}
                      className="px-3.5 py-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-bold rounded-lg transition-colors shadow-xs shrink-0 flex items-center gap-1.5"
                      data-testid="btn-grant-upload-access"
                    >
                      <Lock className="size-3.5" />
                      <span>Grant Upload Access</span>
                    </button>
                  )
                )}
              </div>

              {/* 2. Video & Metadata Review */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1.5">
                    <Film className="size-3.5 text-primary" />
                    <span>Video & Packaging Metadata</span>
                  </h3>
                  {prepData?.master_duration_ms && (
                    <span className="text-xs font-mono text-text-muted flex items-center gap-1">
                      <Clock className="size-3" />
                      {Math.floor(prepData.master_duration_ms / 60000)}m{" "}
                      {Math.floor((prepData.master_duration_ms % 60000) / 1000)}s
                    </span>
                  )}
                </div>

                {/* Title Input */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <label className="font-semibold text-text-primary">YouTube Title</label>
                    <span
                      className={`text-[11px] font-mono ${
                        titleCharCount > 100 ? "text-rose-400 font-bold" : "text-text-muted"
                      }`}
                    >
                      {titleCharCount}/100 chars
                    </span>
                  </div>
                  <input
                    type="text"
                    value={titleInput}
                    onChange={(e) => setTitleInput(e.target.value)}
                    maxLength={110}
                    placeholder="Enter YouTube title…"
                    className={`w-full px-3.5 py-2.5 bg-surface-2 rounded-lg text-xs text-text-primary border transition-colors focus:outline-none ${
                      !isTitleValid
                        ? "border-rose-500/50 focus:border-rose-500"
                        : "border-border-subtle focus:border-primary"
                    }`}
                    data-testid="input-publish-title"
                  />
                </div>

                {/* Description Textarea */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <label className="font-semibold text-text-primary">
                      Description (Includes Chapters)
                    </label>
                    <span
                      className={`text-[11px] font-mono ${
                        descByteCount > 5000 ? "text-rose-400 font-bold" : "text-text-muted"
                      }`}
                    >
                      {descByteCount}/5000 bytes
                    </span>
                  </div>
                  <textarea
                    rows={5}
                    value={descInput}
                    onChange={(e) => setDescInput(e.target.value)}
                    placeholder="YouTube video description with timecodes…"
                    className={`w-full p-3 bg-surface-2 rounded-lg text-xs font-mono text-text-secondary border transition-colors focus:outline-none ${
                      !isDescValid
                        ? "border-rose-500/50 focus:border-rose-500"
                        : "border-border-subtle focus:border-primary"
                    }`}
                    data-testid="textarea-publish-description"
                  />
                </div>

                {/* Category & Tags Preview */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="space-y-1 text-xs">
                    <label className="font-semibold text-text-primary">Category</label>
                    <select
                      value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value)}
                      className="w-full px-3 py-2 bg-surface-2 border border-border-subtle rounded-lg text-xs text-text-primary focus:outline-none focus:border-primary"
                      data-testid="select-publish-category"
                    >
                      <option value="28">Science & Technology (28)</option>
                      <option value="27">Education (27)</option>
                      <option value="22">People & Blogs (22)</option>
                      <option value="24">Entertainment (24)</option>
                      <option value="26">Howto & Style (26)</option>
                    </select>
                  </div>

                  <div className="space-y-1 text-xs">
                    <label className="font-semibold text-text-primary">
                      Tags ({prepData?.suggested_tags?.length || 0})
                    </label>
                    <div className="p-2 bg-surface-2 border border-border-subtle rounded-lg text-[11px] text-text-muted flex items-center gap-1.5 overflow-x-auto">
                      {prepData?.suggested_tags?.length ? (
                        prepData.suggested_tags.map((t, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 bg-surface-3 text-text-secondary rounded text-[10px] font-mono shrink-0"
                          >
                            #{t}
                          </span>
                        ))
                      ) : (
                        <span>No tags</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* 3. Verified Thumbnail Frame Selection */}
              {Boolean(prepData?.verified_thumbnail_frames?.length) && (
                <div
                  className="space-y-3 pt-4 border-t border-border-subtle"
                  data-testid="section-thumbnail-selection"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1.5">
                      <ImageIcon className="size-3.5 text-primary" />
                      <span>Select Thumbnail Frame (Extracted from Master)</span>
                    </h3>
                    <span className="text-[10px] text-text-muted">High-res JPEG ≤ 2MB</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {(
                      prepData?.verified_thumbnail_frames as VerifiedThumbnailFrame[] | undefined
                    )?.map((frame, idx) => {
                      const isSelected = selectedFrameIndex === idx;
                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedFrameIndex(idx)}
                          className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between gap-2 ${
                            isSelected
                              ? "bg-primary/10 border-primary shadow-xs"
                              : "bg-surface-2/60 border-border-subtle hover:border-border-strong"
                          }`}
                          data-testid={`thumbnail-frame-option-${idx}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="space-y-0.5 min-w-0">
                              <span className="text-xs font-bold text-text-primary line-clamp-1">
                                "{frame.headline}"
                              </span>
                              <p className="text-[11px] text-text-muted line-clamp-2">
                                {frame.visual_description}
                              </p>
                            </div>
                            <div
                              className={`size-4 rounded-full border flex items-center justify-center shrink-0 mt-0.5 ${
                                isSelected
                                  ? "bg-primary border-primary text-white"
                                  : "border-border-strong bg-surface-3"
                              }`}
                            >
                              {isSelected && <Check className="size-2.5" />}
                            </div>
                          </div>
                          <span className="text-[10px] font-mono text-primary font-semibold flex items-center gap-1">
                            <Clock className="size-3" />
                            Frame @ {frame.formatted_time}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 4. Visibility / Privacy Selection */}
              <div
                className="space-y-3 pt-4 border-t border-border-subtle"
                data-testid="section-privacy-selection"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1.5">
                    <Lock className="size-3.5 text-primary" />
                    <span>Visibility (Defaults to Private)</span>
                  </h3>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <label
                    className={`p-3 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all ${
                      privacy === "private"
                        ? "bg-primary/10 border-primary"
                        : "bg-surface-2 border-border-subtle hover:border-border-strong"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-text-primary">Private (Default)</span>
                      <input
                        type="radio"
                        name="privacy"
                        value="private"
                        checked={privacy === "private"}
                        onChange={() => setPrivacy("private")}
                        className="text-primary focus:ring-0"
                        data-testid="radio-privacy-private"
                      />
                    </div>
                    <span className="text-[11px] text-text-muted">
                      Only you and invited users can watch.
                    </span>
                  </label>

                  <label
                    className={`p-3 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all ${
                      privacy === "unlisted"
                        ? "bg-primary/10 border-primary"
                        : "bg-surface-2 border-border-subtle hover:border-border-strong"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-text-primary">Unlisted</span>
                      <input
                        type="radio"
                        name="privacy"
                        value="unlisted"
                        checked={privacy === "unlisted"}
                        onChange={() => setPrivacy("unlisted")}
                        className="text-primary focus:ring-0"
                        data-testid="radio-privacy-unlisted"
                      />
                    </div>
                    <span className="text-[11px] text-text-muted">
                      Anyone with the direct link can watch.
                    </span>
                  </label>

                  <label
                    className={`p-3 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all ${
                      privacy === "public"
                        ? "bg-primary/10 border-primary"
                        : "bg-surface-2 border-border-subtle hover:border-border-strong"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-text-primary">Public</span>
                      <input
                        type="radio"
                        name="privacy"
                        value="public"
                        checked={privacy === "public"}
                        onChange={() => setPrivacy("public")}
                        className="text-primary focus:ring-0"
                        data-testid="radio-privacy-public"
                      />
                    </div>
                    <span className="text-[11px] text-text-muted">
                      Publicly searchable and visible on channel.
                    </span>
                  </label>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-2/60 border border-border-subtle text-[11px] text-text-muted flex items-start gap-2">
                  <Info className="size-4 text-blue-400 shrink-0 mt-0.5" />
                  <span>
                    Google restricts API projects created after July 28, 2020 to private uploads
                    until YouTube compliance audit verification is complete. Croviq reports the
                    truthful status returned by YouTube.
                  </span>
                </div>
              </div>

              {/* 5. Declarations: Made for Kids & Synthetic Media */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-border-subtle">
                {/* Made for Kids Declaration */}
                <div
                  className="p-4 rounded-xl bg-surface-2/70 border border-border-subtle space-y-2.5"
                  data-testid="section-made-for-kids"
                >
                  <span className="text-xs font-bold text-text-primary">
                    Audience: Made for Kids? (COPPA)
                  </span>
                  <p className="text-[11px] text-text-muted">
                    Creators are required to declare whether content is directed at children under
                    13.
                  </p>
                  <div className="space-y-2 pt-1 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer text-text-secondary hover:text-text-primary">
                      <input
                        type="radio"
                        name="made_for_kids"
                        checked={!madeForKids}
                        onChange={() => setMadeForKids(false)}
                        className="text-primary focus:ring-0"
                        data-testid="radio-made-for-kids-no"
                      />
                      <span>No, not made for kids (Default)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer text-text-secondary hover:text-text-primary">
                      <input
                        type="radio"
                        name="made_for_kids"
                        checked={madeForKids}
                        onChange={() => setMadeForKids(true)}
                        className="text-primary focus:ring-0"
                        data-testid="radio-made-for-kids-yes"
                      />
                      <span>Yes, made for kids</span>
                    </label>
                  </div>
                </div>

                {/* Synthetic Media Disclosure */}
                <div
                  className="p-4 rounded-xl bg-surface-2/70 border border-border-subtle space-y-2.5"
                  data-testid="section-synthetic-media"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-text-primary">
                      Synthetic Media Disclosure
                    </span>
                    {prepData?.suggested_synthetic_media && (
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-primary/20 text-primary border border-primary/30 rounded-full">
                        AI Detected
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-text-muted">
                    {prepData?.suggested_synthetic_media
                      ? "Suggested: Yes (Studio Voice narration or Omni generated B-roll detected in production)."
                      : "Declare if video contains realistic altered or generated AI media."}
                  </p>
                  <div className="space-y-2 pt-1 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer text-text-secondary hover:text-text-primary">
                      <input
                        type="radio"
                        name="synthetic_media"
                        checked={containsSyntheticMedia}
                        onChange={() => setContainsSyntheticMedia(true)}
                        className="text-primary focus:ring-0"
                        data-testid="radio-synthetic-media-yes"
                      />
                      <span>Yes, contains realistic synthetic media</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer text-text-secondary hover:text-text-primary">
                      <input
                        type="radio"
                        name="synthetic_media"
                        checked={!containsSyntheticMedia}
                        onChange={() => setContainsSyntheticMedia(false)}
                        className="text-primary focus:ring-0"
                        data-testid="radio-synthetic-media-no"
                      />
                      <span>No, unaltered original footage only</span>
                    </label>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-border-subtle bg-surface-2/60 flex items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={isPublishing}
            className="px-4 py-2 text-xs font-semibold bg-surface-2 hover:bg-surface-3 text-text-primary rounded-lg border border-border-subtle transition-colors disabled:opacity-50"
            data-testid="btn-cancel-publish"
          >
            Cancel
          </button>

          <button
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              onConfirmPublish({
                requested_privacy: privacy,
                made_for_kids: madeForKids,
                contains_synthetic_media: containsSyntheticMedia,
                selected_title: titleInput.trim(),
                selected_description: descInput.trim(),
                selected_tags: prepData?.suggested_tags || [],
                category_id: categoryId,
                thumbnail_frame_ms: selectedThumbnail?.frame_timestamp_ms,
              })
            }
            className={`px-5 py-2 text-xs font-bold rounded-lg flex items-center gap-2 transition-all shadow-md ${
              canSubmit
                ? "bg-red-600 hover:bg-red-700 text-white cursor-pointer"
                : "bg-surface-3 text-text-muted cursor-not-allowed opacity-60"
            }`}
            data-testid="btn-confirm-upload-to-youtube"
          >
            {isPublishing ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                <span>Initiating Upload…</span>
              </>
            ) : (
              <>
                <UploadCloud className="size-4" />
                <span>Upload to YouTube</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
