"use client";

import type { CSSProperties } from "react";

export function ActionIconButton({
  icon,
  label,
  primary = false,
  danger = false,
  disabled,
  onClick,
}: {
  icon: string;
  label: string;
  primary?: boolean;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  const className = primary ? "icon-btn-primary" : danger ? "icon-btn-danger" : "icon-btn";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={className}
    >
      <span className="icon-mask" style={{ "--icon-url": `url(${icon})` } as CSSProperties} />
    </button>
  );
}
