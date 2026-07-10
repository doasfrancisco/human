"use client";

import { Suspense, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ChevronLeftIcon,
  CollapseAllIcon,
  NewFileIcon,
  NewFolderIcon,
} from "@/components/icons";
import { FileTree, type TreeCreate } from "@/components/FileTree";
import { fsCreate, getFileTree, type FileNode } from "@/lib/api";

type ExplorerSidebarProps = {
  refreshKey?: number;
  projectName?: string | null;
  activeFile?: string;
  onOpenFile?: (node: FileNode) => void;
  onOpenCreatedFile?: (node: FileNode) => void;
  onRequestDelete?: (node: FileNode) => void;
  children?: ReactNode;
};

type TreeSelection = {
  node: FileNode;
  parentPath: string;
};

type TreeMenu = {
  node: FileNode;
  x: number;
  y: number;
};

function SidebarShell({ children }: { children?: ReactNode }) {
  return (
    <aside className="sticky top-0 flex h-screen max-h-screen w-[260px] shrink-0 flex-col border-r border-[#1F2328] bg-[#15181C]">
      {children}
    </aside>
  );
}

function ExplorerSidebarContent({
  refreshKey,
  projectName,
  activeFile,
  onOpenFile,
  onOpenCreatedFile,
  onRequestDelete,
  children,
}: ExplorerSidebarProps) {
  const searchParams = useSearchParams();
  const initialPath = searchParams.get("path");
  const [tree, setTree] = useState<FileNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [localRefresh, setLocalRefresh] = useState(0);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<TreeSelection | null>(null);
  const [creating, setCreating] = useState<TreeCreate | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [menu, setMenu] = useState<TreeMenu | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFileTree(initialPath ?? undefined, 1)
      .then((node) => {
        if (cancelled) return;
        setTree(node);
        setLoading(false);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialPath, refreshKey, localRefresh]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenu(null);
        return;
      }
      if (event.key !== "Delete") return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable='true']")) return;
      if (selected) onRequestDelete?.(selected.node);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selected, onRequestDelete]);

  function startCreate(kind: "file" | "dir") {
    if (!tree) return;
    const parent = selected
      ? selected.node.type === "dir"
        ? selected.node.path
        : selected.parentPath
      : tree.path;
    if (parent !== tree.path) setExpanded((current) => ({ ...current, [parent]: true }));
    setCreateError(null);
    setCreating({ parent, kind });
  }

  function submitCreate(name: string) {
    if (!creating) return;
    fsCreate(creating.parent, name, creating.kind)
      .then((made) => {
        setCreating(null);
        setCreateError(null);
        setLocalRefresh((key) => key + 1);
        if (made.type === "file") {
          const node: FileNode = { name: made.name, path: made.path, type: "file", children: [] };
          if (onOpenCreatedFile) onOpenCreatedFile(node);
          else onOpenFile?.(node);
        } else {
          setExpanded((current) => ({ ...current, [made.path]: true }));
        }
      })
      .catch((err) => {
        setCreateError(err instanceof Error ? err.message : String(err));
      });
  }

  return (
    <SidebarShell>
      <div className="flex h-[52px] shrink-0 items-center gap-2.5 border-b border-[#1F2328] px-4">
        <Link
          href="/projects"
          title="Back to projects"
          className="group flex min-w-0 flex-1 items-center gap-[3px]"
        >
          <ChevronLeftIcon width={14} height={14} className="shrink-0 text-[#9A9DA4] transition-colors group-hover:text-[#EEEFF1]" />
          <span className="truncate text-sm font-semibold leading-4 tracking-[-0.01em] text-[#EEEFF1]">
            {projectName ?? "Projects"}
          </span>
        </Link>
        <button
          type="button"
          aria-label="Collapse folders"
          title="Collapse folders"
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-[#9A9DA4] transition-colors hover:bg-[#FFFFFF0A] hover:text-[#E7EAF0]"
          onClick={() => setExpanded({})}
        >
          <CollapseAllIcon width={16} height={16} />
        </button>
      </div>
      <div className="flex h-[30px] shrink-0 items-center justify-between border-b border-[#1F2328] pl-4 pr-3">
        <span className="text-[10px] font-semibold leading-3 tracking-[0.08em] text-[#5D626B]">EXPLORER</span>
        <div className="flex shrink-0 items-center gap-0.5">
          <button
            type="button"
            aria-label="New file"
            title="New file"
            className="flex h-5 w-5 items-center justify-center rounded text-[#8B8FF5] transition-colors hover:bg-[#FFFFFF0A]"
            onClick={() => startCreate("file")}
          >
            <NewFileIcon width={16} height={16} />
          </button>
          <button
            type="button"
            aria-label="New folder"
            title="New folder"
            className="flex h-5 w-5 items-center justify-center rounded text-[#9A9DA4] transition-colors hover:bg-[#FFFFFF0A]"
            onClick={() => startCreate("dir")}
          >
            <NewFolderIcon width={16} height={16} />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-2 py-1">
        {loading ? (
          <p className="px-2 py-1 text-xs text-[#5D626B]">Loading...</p>
        ) : error ? (
          <p className="px-2 py-1 text-xs text-red-400">{error}</p>
        ) : tree ? (
          <FileTree
            root={tree}
            activeFile={activeFile}
            selectedPath={selected?.node.path ?? null}
            expanded={expanded}
            refreshKey={(refreshKey ?? 0) + localRefresh}
            creating={creating}
            createError={createError}
            onToggle={(path, open) => setExpanded((current) => ({ ...current, [path]: open }))}
            onSelect={(node, parentPath) => setSelected({ node, parentPath })}
            onOpen={(node) => onOpenFile?.(node)}
            onContextMenu={(node, parentPath, x, y) => {
              setSelected({ node, parentPath });
              setMenu({ node, x, y });
            }}
            onCreateSubmit={submitCreate}
            onCreateCancel={() => {
              setCreating(null);
              setCreateError(null);
            }}
          />
        ) : null}
      </div>
      {children}
      {menu ? (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setMenu(null)}
          onContextMenu={(event) => {
            event.preventDefault();
            setMenu(null);
          }}
        >
          <div
            className="absolute min-w-[140px] rounded-md border-[0.8px] border-[#232830] bg-[#1A1F24] py-1 shadow-2xl"
            style={{ left: menu.x, top: menu.y }}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="flex w-full items-center px-3 py-1.5 text-left text-xs text-red-300 transition-colors hover:bg-[#FFFFFF0A]"
              onClick={() => {
                const node = menu.node;
                setMenu(null);
                onRequestDelete?.(node);
              }}
            >
              Delete
            </button>
          </div>
        </div>
      ) : null}
    </SidebarShell>
  );
}

export function ExplorerSidebar({
  refreshKey,
  projectName,
  activeFile,
  onOpenFile,
  onOpenCreatedFile,
  onRequestDelete,
  children,
}: ExplorerSidebarProps) {
  return (
    <Suspense fallback={<SidebarShell />}>
      <ExplorerSidebarContent
        refreshKey={refreshKey}
        projectName={projectName}
        activeFile={activeFile}
        onOpenFile={onOpenFile}
        onOpenCreatedFile={onOpenCreatedFile}
        onRequestDelete={onRequestDelete}
      >
        {children}
      </ExplorerSidebarContent>
    </Suspense>
  );
}
