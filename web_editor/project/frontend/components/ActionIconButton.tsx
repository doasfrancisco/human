"use client";

import type { ReactNode } from "react";

export function ActionIconButton({
  icon,
  text,
  label,
  primary = false,
  danger = false,
  disabled,
  onClick,
}: {
  icon?: ReactNode;
  text?: string;
  label: string;
  primary?: boolean;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  const tone = primary
    ? "border-[#6366F180] bg-[#4F46E52E] text-[#C7D2FE] enabled:hover:bg-[#4F46E54D] enabled:hover:text-white"
    : danger
      ? "border-transparent text-[#F87171] enabled:hover:bg-[#F871711A] enabled:hover:text-[#FCA5A5]"
      : "border-transparent text-[#8A919E] enabled:hover:bg-[#FFFFFF0A] enabled:hover:text-[#E7EAF0]";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={`flex h-5 shrink-0 items-center justify-center rounded-md border-[0.8px] transition-colors ${icon && !text ? "w-5" : "px-1.5"} ${tone}`}
    >
      {icon}
      {text ? <span className="font-mono text-[10px] font-medium tracking-[0.02em]">{text}</span> : null}
    </button>
  );
}
