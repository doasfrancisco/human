import * as React from "react";

export type IconProps = React.SVGProps<SVGSVGElement>;

export function FileHumanIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M9 2.33H4.67a1 1 0 0 0-1 1v9.34a1 1 0 0 0 1 1h6.66a1 1 0 0 0 1-1V5.67z" />
      <path d="M9 2.33v3.34h3.33" />
      <path d="M6 7.5h4M6 9.5h4M6 11.5h2.33" strokeWidth={1.25} />
    </svg>
  );
}

export function FilePythonIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M9 2.33H4.67a1 1 0 0 0-1 1v9.34a1 1 0 0 0 1 1h6.66a1 1 0 0 0 1-1V5.67z" />
      <path d="M9 2.33v3.34h3.33" />
      <rect x="5.4" y="9.2" width="5.2" height="2.6" rx="0.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function FileJsonIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      strokeLinecap="round"
      {...props}
    >
      <path d="M6 4c-1 0-1.33.53-1.33 1.33v1.67c0 .67-.4 1-1.07 1 .67 0 1.07.33 1.07 1v1.67c0 .8.33 1.33 1.33 1.33" />
      <path d="M10 4c1 0 1.33.53 1.33 1.33v1.67c0 .67.4 1 1.07 1-.67 0-1.07.33-1.07 1v1.67c0 .8-.33 1.33-1.33 1.33" />
    </svg>
  );
}

export function FileMarkdownIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinejoin="round"
      {...props}
    >
      <path d="M9 2.33H4.67a1 1 0 0 0-1 1v9.34a1 1 0 0 0 1 1h6.66a1 1 0 0 0 1-1V5.67z" />
      <path d="M9 2.33v3.34h3.33" />
      <path d="M6 10.67V8l1.33 1.33L8.67 8v2.67" strokeWidth={1.25} strokeLinecap="round" />
    </svg>
  );
}

export function FolderIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M2 4.33a1 1 0 0 1 1-1h2.67L7 5h6a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z" />
    </svg>
  );
}

export function FolderOpenIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M4 9.33l.97-1.93a1.33 1.33 0 0 1 1.19-.73h7.17a1.33 1.33 0 0 1 1.3 1.66l-1.04 4a1.33 1.33 0 0 1-1.29 1H2.67a1.33 1.33 0 0 1-1.34-1.33V3.33A1.33 1.33 0 0 1 2.67 2h2.6a1.33 1.33 0 0 1 1.12.6l.54.8a1.33 1.33 0 0 0 1.11.6H12a1.33 1.33 0 0 1 1.33 1.33v1.34" />
    </svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M6 4l4 4-4 4" />
    </svg>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M10 12L6 8l4-4" />
    </svg>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      strokeLinejoin="round"
      {...props}
    >
      <path d="M1.67 8s2.33-4.33 6.33-4.33S14.33 8 14.33 8s-2.33 4.33-6.33 4.33S1.67 8 1.67 8z" />
      <circle cx="8" cy="8" r="1.73" />
    </svg>
  );
}

export function NewFileIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M9 2.33H4.67a1 1 0 0 0-1 1v9.34a1 1 0 0 0 1 1h3" />
      <path d="M9 2.33v3.34h3.33" />
      <path d="M11.67 9.33v4M9.67 11.33h4" />
    </svg>
  );
}

export function NewFolderIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M7.67 13H3a1 1 0 0 1-1-1V4.33a1 1 0 0 1 1-1h2.67L7 5h5.33a1 1 0 0 1 1 1v2" />
      <path d="M11.67 9.33v4M9.67 11.33h4" />
    </svg>
  );
}

export function CollapseAllIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M8.67 4.67L5.33 8l3.34 3.33M12.67 4.67L9.33 8l3.34 3.33" />
    </svg>
  );
}

export function SparklesIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M6.62 10.33a1.33 1.33 0 0 0-.95-.95L1.58 8.32a.33.33 0 0 1 0-.64l4.09-1.05a1.33 1.33 0 0 0 .95-.95l1.06-4.09a.33.33 0 0 1 .64 0l1.05 4.09a1.33 1.33 0 0 0 .96.95l4.09 1.05a.33.33 0 0 1 0 .64l-4.09 1.06a1.33 1.33 0 0 0-.96.95l-1.05 4.09a.33.33 0 0 1-.64 0z" />
      <path d="M13.33 2v2.67" />
      <path d="M14.67 3.33H12" />
      <path d="M2.67 11.33v1.33" />
      <path d="M3.33 12H2" />
    </svg>
  );
}

export const ICON_BY_EXTENSION: Record<string, (props: IconProps) => React.ReactElement> = {
  ".human": FileHumanIcon,
  ".context": FileJsonIcon,
  ".py": FilePythonIcon,
  ".md": FileMarkdownIcon,
};
