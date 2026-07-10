"use client";

import { useMemo } from "react";
import type { FileContents } from "@pierre/diffs";
import { MultiFileDiff } from "@pierre/diffs/react";

type DiffPreviewProps = {
  filename: string;
  before: string;
  after: string;
  language?: string;
};

function smallHash(text: string) {
  let hash = 5381;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 33) ^ text.charCodeAt(index);
  }
  return (hash >>> 0).toString(16);
}

export function DiffPreview({ filename, before, after, language }: DiffPreviewProps) {
  const oldFile = useMemo<FileContents>(
    () => ({
      name: filename,
      contents: before,
      cacheKey: `${filename}:saved:${smallHash(before)}`,
      ...(language ? { lang: language } : {}),
    }),
    [before, filename, language]
  );

  const newFile = useMemo<FileContents>(
    () => ({
      name: filename,
      contents: after,
      cacheKey: `${filename}:draft:${smallHash(after)}`,
      ...(language ? { lang: language } : {}),
    }),
    [after, filename, language]
  );

  return (
    <div className="h-full overflow-hidden bg-[#101317]">
      <MultiFileDiff
        oldFile={oldFile}
        newFile={newFile}
        options={{
          theme: { dark: "pierre-dark", light: "pierre-light" },
          diffStyle: "unified",
          diffIndicators: "bars",
          lineDiffType: "word-alt",
          overflow: "scroll",
          tokenizeMaxLineLength: 1000,
          maxLineDiffLength: 1000,
        }}
      />
    </div>
  );
}
