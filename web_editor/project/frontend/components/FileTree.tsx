"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  FileHumanIcon,
  ICON_BY_EXTENSION,
  NewFolderIcon,
} from "@/components/icons";
import { getFileTree, type FileNode } from "@/lib/api";

const ROW_BASE =
  "flex h-[26px] w-full items-center gap-1.5 rounded-[6px] pr-2 text-[13px] leading-4 tracking-[-0.005em]";

export type TreeCreate = {
  parent: string;
  kind: "file" | "dir";
};

type TreeCtx = {
  activeFile?: string;
  selectedPath: string | null;
  expanded: Record<string, boolean>;
  refreshKey: number;
  creating: TreeCreate | null;
  createError: string | null;
  onToggle: (path: string, open: boolean) => void;
  onSelect: (node: FileNode, parentPath: string) => void;
  onOpen: (node: FileNode, paired: boolean) => void;
  onContextMenu: (node: FileNode, parentPath: string, x: number, y: number) => void;
  onCreateSubmit: (name: string) => void;
  onCreateCancel: () => void;
};

function extensionOf(name: string) {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot) : "";
}

function isActiveFile(node: FileNode, activeFile?: string) {
  if (!activeFile) return false;
  const path = node.path.replace(/\\/g, "/");
  const target = activeFile.replace(/\\/g, "/");
  return path === target || path.endsWith(`/${target}`);
}

function isGenerated(ext: string) {
  return ext === ".context" || ext === ".py";
}

function glyphColor(ext: string, active: boolean) {
  if (active || ext === ".human") return "text-[#A5B4FC]";
  if (isGenerated(ext)) return "text-[#8A919E]";
  return "text-[#5C6470]";
}

function nameColor(ext: string, active: boolean) {
  if (active || ext === ".human") return "font-medium text-[#EEEFF1]";
  if (isGenerated(ext)) return "text-[#9A9DA4]";
  return "text-[#BCC0C7]";
}

function rowBackground(active: boolean, selected: boolean) {
  if (selected) return "bg-[#22283180]";
  if (active) return "bg-[#1E2228]";
  return "hover:bg-[#FFFFFF08]";
}

function FileGlyph({ node, active }: { node: FileNode; active: boolean }) {
  const ext = extensionOf(node.name);
  const Icon = ICON_BY_EXTENSION[ext] ?? FileHumanIcon;
  return (
    <span className={`flex w-4 shrink-0 justify-center ${glyphColor(ext, active)}`}>
      <Icon width={16} height={16} />
    </span>
  );
}

function CreateRow({ indent, ctx }: { indent: number; ctx: TreeCtx }) {
  const [name, setName] = useState("");
  const kind = ctx.creating?.kind ?? "file";
  return (
    <div>
      <div className={`${ROW_BASE} bg-[#1E2228]`} style={{ paddingLeft: `${indent}px` }}>
        <span className="flex w-4 shrink-0 justify-center text-[#8A919E]">
          {kind === "dir" ? <NewFolderIcon width={16} height={16} /> : <FileHumanIcon width={16} height={16} />}
        </span>
        <input
          autoFocus
          value={name}
          aria-label={kind === "dir" ? "New folder name" : "New file name"}
          className="min-w-0 flex-1 rounded-[4px] border border-[#4F46E580] bg-[#101317] px-1 py-0.5 text-[13px] text-[#E7EAF0] outline-none"
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              if (name.trim()) ctx.onCreateSubmit(name.trim());
            } else if (event.key === "Escape") {
              event.preventDefault();
              ctx.onCreateCancel();
            }
          }}
          onBlur={ctx.onCreateCancel}
        />
      </div>
      {ctx.createError ? (
        <p className="py-0.5 text-[11px] text-red-400" style={{ paddingLeft: `${indent + 22}px` }}>
          {ctx.createError}
        </p>
      ) : null}
    </div>
  );
}

function FileRow({
  node,
  parentPath,
  paired,
  indent,
  lane,
  ctx,
}: {
  node: FileNode;
  parentPath: string;
  paired: boolean;
  indent: number;
  lane?: ReactNode;
  ctx: TreeCtx;
}) {
  const ext = extensionOf(node.name);
  const active = isActiveFile(node, ctx.activeFile);
  const selected = ctx.selectedPath === node.path;
  return (
    <div
      className={`${ROW_BASE} cursor-pointer ${rowBackground(active, selected)}`}
      style={{ paddingLeft: `${indent}px` }}
      title={node.path}
      onClick={() => {
        ctx.onSelect(node, parentPath);
        ctx.onOpen(node, paired);
      }}
      onContextMenu={(event) => {
        event.preventDefault();
        ctx.onSelect(node, parentPath);
        ctx.onContextMenu(node, parentPath, event.clientX, event.clientY);
      }}
    >
      {lane}
      <FileGlyph node={node} active={active} />
      <span className={`min-w-0 flex-1 truncate ${nameColor(ext, active)}`}>{node.name}</span>
      {isGenerated(ext) ? (
        <span className="flex w-4 shrink-0 justify-center text-[#737780]">
          <EyeIcon width={16} height={16} />
        </span>
      ) : null}
    </div>
  );
}

function HumanPairRow({
  human,
  context,
  parentPath,
  indent,
  ctx,
}: {
  human: FileNode;
  context: FileNode;
  parentPath: string;
  indent: number;
  ctx: TreeCtx;
}) {
  const open = ctx.expanded[human.path] ?? true;
  const active = isActiveFile(human, ctx.activeFile);
  const selected = ctx.selectedPath === human.path;
  return (
    <>
      <div
        className={`${ROW_BASE} cursor-pointer ${rowBackground(active, selected)}`}
        style={{ paddingLeft: `${indent}px` }}
        title={human.path}
        onClick={() => {
          ctx.onSelect(human, parentPath);
          ctx.onOpen(human, true);
        }}
        onContextMenu={(event) => {
          event.preventDefault();
          ctx.onSelect(human, parentPath);
          ctx.onContextMenu(human, parentPath, event.clientX, event.clientY);
        }}
      >
        <button
          type="button"
          className="flex w-4 shrink-0 justify-center text-[#9A9DA4] transition-colors hover:text-[#EEEFF1]"
          aria-label={open ? "Collapse" : "Expand"}
          onClick={(event) => {
            event.stopPropagation();
            ctx.onToggle(human.path, !open);
          }}
        >
          {open ? <ChevronDownIcon width={16} height={16} /> : <ChevronRightIcon width={16} height={16} />}
        </button>
        <FileGlyph node={human} active={active} />
        <span className={`min-w-0 flex-1 truncate ${nameColor(".human", active)}`}>{human.name}</span>
      </div>
      {open ? <FileRow node={context} parentPath={parentPath} paired indent={indent + 22} ctx={ctx} /> : null}
    </>
  );
}

function DirRow({ node, parentPath, depth, ctx }: { node: FileNode; parentPath: string; depth: number; ctx: TreeCtx }) {
  const open = ctx.expanded[node.path] ?? false;
  const selected = ctx.selectedPath === node.path;
  const refreshKey = ctx.refreshKey;
  const [children, setChildren] = useState<FileNode[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const indent = 8 + depth * 16;

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    getFileTree(node.path, 1)
      .then((fresh) => {
        if (cancelled) return;
        setChildren(fresh.children);
        setLoadError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [open, node.path, refreshKey]);

  return (
    <div>
      <div
        className={`${ROW_BASE} cursor-pointer text-left ${selected ? "bg-[#22283180]" : "hover:bg-[#FFFFFF08]"}`}
        style={{ paddingLeft: `${indent}px` }}
        title={node.path}
        onClick={() => {
          ctx.onSelect(node, parentPath);
          ctx.onToggle(node.path, !open);
        }}
        onContextMenu={(event) => {
          event.preventDefault();
          ctx.onSelect(node, parentPath);
          ctx.onContextMenu(node, parentPath, event.clientX, event.clientY);
        }}
      >
        <span className="flex w-4 shrink-0 justify-center text-[#9A9DA4]">
          {open ? <ChevronDownIcon width={16} height={16} /> : <ChevronRightIcon width={16} height={16} />}
        </span>
        <span className="min-w-0 flex-1 truncate font-medium text-[#BCC0C7]">{node.name}</span>
      </div>
      {open ? (
        <>
          {ctx.creating?.parent === node.path ? <CreateRow indent={8 + (depth + 1) * 16 + 22} ctx={ctx} /> : null}
          {children === null ? (
            loadError ? (
              <div className="py-1 text-xs text-red-400" style={{ paddingLeft: `${8 + (depth + 1) * 16 + 22}px` }}>
                {loadError}
              </div>
            ) : (
              <div className="py-1 text-xs text-[#5D626B]" style={{ paddingLeft: `${8 + (depth + 1) * 16 + 22}px` }}>
                Loading...
              </div>
            )
          ) : (
            renderNodes(children, node.path, depth + 1, ctx)
          )}
        </>
      ) : null}
    </div>
  );
}

function renderNodes(nodes: FileNode[], parentPath: string, depth: number, ctx: TreeCtx) {
  const names = new Set(nodes.map((node) => node.name));
  const pairedContexts = new Set(
    nodes
      .filter(
        (node) =>
          node.type === "file" &&
          node.name.endsWith(".context") &&
          names.has(`${node.name.slice(0, -".context".length)}.human`)
      )
      .map((node) => node.name)
  );

  function pairedWithHuman(name: string) {
    if (name.endsWith(".human")) return true;
    if (name.endsWith(".context")) return names.has(`${name.slice(0, -".context".length)}.human`);
    if (name.endsWith(".py")) return names.has(`${name.slice(0, -".py".length)}.human`);
    return false;
  }

  return nodes.map((node) => {
    if (node.type === "dir") {
      return <DirRow key={node.path} node={node} parentPath={parentPath} depth={depth} ctx={ctx} />;
    }
    if (pairedContexts.has(node.name)) return null;
    if (node.name.endsWith(".human")) {
      const contextName = `${node.name.slice(0, -".human".length)}.context`;
      const context = nodes.find((sibling) => sibling.type === "file" && sibling.name === contextName);
      if (context) {
        return (
          <HumanPairRow
            key={node.path}
            human={node}
            context={context}
            parentPath={parentPath}
            indent={8 + depth * 16}
            ctx={ctx}
          />
        );
      }
    }
    return (
      <FileRow
        key={node.path}
        node={node}
        parentPath={parentPath}
        paired={pairedWithHuman(node.name)}
        indent={8 + depth * 16}
        ctx={ctx}
      />
    );
  });
}

export function FileTree({
  root,
  activeFile,
  selectedPath,
  expanded,
  refreshKey,
  creating,
  createError,
  onToggle,
  onSelect,
  onOpen,
  onContextMenu,
  onCreateSubmit,
  onCreateCancel,
}: {
  root: FileNode;
  activeFile?: string;
  selectedPath: string | null;
  expanded: Record<string, boolean>;
  refreshKey: number;
  creating: TreeCreate | null;
  createError: string | null;
  onToggle: (path: string, open: boolean) => void;
  onSelect: (node: FileNode, parentPath: string) => void;
  onOpen: (node: FileNode, paired: boolean) => void;
  onContextMenu: (node: FileNode, parentPath: string, x: number, y: number) => void;
  onCreateSubmit: (name: string) => void;
  onCreateCancel: () => void;
}) {
  const ctx: TreeCtx = {
    activeFile,
    selectedPath,
    expanded,
    refreshKey,
    creating,
    createError,
    onToggle,
    onSelect,
    onOpen,
    onContextMenu,
    onCreateSubmit,
    onCreateCancel,
  };
  return (
    <div className="flex flex-col gap-px py-1">
      {creating?.parent === root.path ? <CreateRow indent={8} ctx={ctx} /> : null}
      {renderNodes(root.children ?? [], root.path, 0, ctx)}
    </div>
  );
}
