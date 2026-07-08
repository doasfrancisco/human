"use client";

import type { CSSProperties } from "react";

export function ConfirmDeleteModal({
  title,
  description,
  detail,
  disabled,
  onCancel,
  onConfirm,
}: {
  title: string;
  description: string;
  detail: string;
  disabled: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-950 p-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/40 bg-red-500/10 text-red-300">
            <span className="icon-mask" style={{ "--icon-url": "url(/icons/trash.svg)" } as CSSProperties} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-zinc-100">Delete {title}?</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">{description}</p>
            <p className="mt-3 font-mono text-xs text-zinc-600">{detail}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-secondary" disabled={disabled} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn-danger" disabled={disabled} onClick={onConfirm}>
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
