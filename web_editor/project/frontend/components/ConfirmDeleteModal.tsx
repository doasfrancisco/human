"use client";

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
      <div className="w-full max-w-md rounded-xl border-[0.8px] border-[#232830] bg-[#15181C] p-5 shadow-2xl">
        <h3 className="text-sm font-semibold text-[#E7EAF0]">Delete {title}?</h3>
        <p className="mt-2 text-xs leading-5 text-[#8A919E]">{description}</p>
        <p className="mt-3 font-mono text-[11px] text-[#5C6470]">{detail}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-md px-3 py-1.5 text-xs font-medium text-[#8A919E] transition-colors enabled:hover:bg-[#FFFFFF0A] enabled:hover:text-[#E7EAF0]"
            disabled={disabled}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-md border-[0.8px] border-red-500/50 bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-300 transition-colors enabled:hover:bg-red-500/25"
            disabled={disabled}
            onClick={onConfirm}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
