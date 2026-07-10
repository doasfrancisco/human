"use client";

import { useEffect, useState, type CSSProperties, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { ChevronRightIcon } from "@/components/icons";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal";
import { createProject, deleteProject, getProjects, pickFolder, selectProject, type Project } from "@/lib/api";

function timeAgo(iso: string) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Project | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProjects()
      .then((list) => {
        if (cancelled) return;
        setProjects(list.projects);
        setLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function openProject(project: Project) {
    setBusy(true);
    setError(null);
    selectProject(project.id)
      .then(() => {
        router.push("/");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setBusy(false);
      });
  }

  function submitNewProject() {
    const name = newName.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    createProject(name)
      .then(() => {
        router.push("/");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setBusy(false);
      });
  }

  function openFolderDialog() {
    setBusy(true);
    setError(null);
    pickFolder()
      .then(({ path }) => {
        if (path) {
          router.push(`/?path=${encodeURIComponent(path)}`);
        } else {
          setBusy(false);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setBusy(false);
      });
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    setBusy(true);
    setError(null);
    deleteProject(target.id)
      .then((list) => {
        setProjects(list.projects);
        setBusy(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setBusy(false);
      });
  }

  const disabled = busy || !loaded;

  function rowKeyDown(event: KeyboardEvent<HTMLDivElement>, project: Project) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    if (!disabled) openProject(project);
  }

  return (
    <main className="flex min-h-screen flex-col items-center bg-[var(--fp-ground)] px-4 pb-16 pt-24 font-sans text-[var(--fp-text)]">
      <div className="w-full max-w-[840px]">
        <div className="flex items-end justify-between">
          <h1 className="text-[42px] font-bold leading-[46px] tracking-[-0.025em] text-[var(--fp-text)]">Projects</h1>
          <button
            type="button"
            className="pb-1 text-[13px] font-medium leading-4 text-[var(--fp-text-muted)] transition-colors hover:text-[var(--fp-text)]"
            disabled={disabled}
            onClick={openFolderDialog}
          >
            Open folder
          </button>
        </div>

        <div className="my-2 min-h-6 text-[13px] leading-4">
          {error ? (
            <span className="text-red-400">{error}</span>
          ) : busy ? (
            <span className="text-[var(--fp-text-muted)]">Working...</span>
          ) : null}
        </div>

        <div className="flex items-center border-b border-[var(--fp-hairline)] px-3 pb-[10px]">
          <span className="flex-1 font-mono text-[10px] uppercase leading-3 tracking-[0.14em] text-[var(--fp-text-dim)]">
            project
          </span>
          <span className="w-[130px] shrink-0 font-mono text-[10px] uppercase leading-3 tracking-[0.14em] text-[var(--fp-text-dim)]">
            last compiled
          </span>
          <span className="w-[52px] shrink-0" />
        </div>

        {!loaded ? (
          <div className="flex h-[58px] items-center border-b border-[var(--fp-hairline)] px-3 text-[13px] leading-4 text-[var(--fp-text-dim)]">
            Loading projects...
          </div>
        ) : projects.length === 0 ? (
          <div className="flex h-[58px] items-center border-b border-[var(--fp-hairline)] px-3 text-[13px] leading-4 text-[var(--fp-text-dim)]">
            No projects yet — create your first project to start compiling.
          </div>
        ) : (
          projects.map((project) => (
            <div
              key={project.id}
              role="button"
              tabIndex={0}
              aria-label={`Open project ${project.name}`}
              className="group flex h-[58px] cursor-pointer items-center border-b border-[var(--fp-hairline)] px-3 transition-colors hover:bg-[var(--fp-surface)] focus-visible:bg-[var(--fp-surface)] focus-visible:outline-none"
              onClick={() => {
                if (!disabled) openProject(project);
              }}
              onKeyDown={(event) => rowKeyDown(event, project)}
            >
              <div className="flex min-w-0 flex-1 items-center gap-[10px]">
                <span
                  className={`h-5 w-[3px] shrink-0 rounded-[2px] ${project.active ? "bg-[var(--fp-accent)]" : "bg-transparent"}`}
                />
                <span className="truncate text-[15px] font-semibold leading-[18px] text-[var(--fp-text)]">
                  {project.name}
                </span>
              </div>
              <span className="w-[130px] shrink-0 font-mono text-[13px] leading-4 text-[var(--fp-text-muted)]">
                {timeAgo(project.updated_at)}
              </span>
              <div className="flex w-[52px] shrink-0 items-center justify-end gap-2">
                <button
                  type="button"
                  aria-label={`Delete project ${project.name}`}
                  title={`Delete project ${project.name}`}
                  disabled={disabled}
                  className="text-[var(--fp-text-dim)] transition-colors hover:text-red-400"
                  onClick={(event) => {
                    event.stopPropagation();
                    setPendingDelete(project);
                  }}
                >
                  <span
                    className="icon-mask"
                    style={{ "--icon-url": "url(/icons/trash.svg)", height: 14, width: 14 } as CSSProperties}
                  />
                </button>
                <ChevronRightIcon width={14} height={14} className="shrink-0 text-[var(--fp-accent-soft)]" />
              </div>
            </div>
          ))
        )}

        <div className="h-4" />

        {creating ? (
          <form
            className="flex h-[52px] w-full items-center gap-[10px] rounded-[10px] border border-[var(--fp-hairline)] bg-[var(--fp-surface)] px-3"
            onSubmit={(event) => {
              event.preventDefault();
              submitNewProject();
            }}
          >
            <span className="w-[14px] shrink-0 text-[14px] leading-[14px] text-[var(--fp-text-muted)]">+</span>
            <input
              autoFocus
              value={newName}
              placeholder="project name"
              className="min-w-0 flex-1 bg-transparent text-[13px] leading-4 text-[var(--fp-text)] outline-none placeholder:text-[var(--fp-text-dim)]"
              onChange={(event) => setNewName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setCreating(false);
              }}
            />
            <button
              type="submit"
              className="shrink-0 text-[13px] font-medium leading-4 text-[var(--fp-accent-soft)] transition-colors hover:text-[var(--fp-text)]"
              disabled={disabled || !newName.trim()}
            >
              Create
            </button>
            <button
              type="button"
              className="shrink-0 text-[13px] leading-4 text-[var(--fp-text-dim)] transition-colors hover:text-[var(--fp-text-muted)]"
              disabled={disabled}
              onClick={() => setCreating(false)}
            >
              Cancel
            </button>
          </form>
        ) : (
          <button
            type="button"
            className="flex h-[52px] w-full items-center gap-[10px] rounded-[10px] border border-dashed border-[#2A2F36] px-3 text-left transition-colors hover:border-[var(--fp-text-dim)]"
            disabled={disabled}
            onClick={() => {
              setNewName("");
              setCreating(true);
            }}
          >
            <span className="w-[14px] shrink-0 text-[14px] leading-[14px] text-[var(--fp-text-muted)]">+</span>
            <span className="text-[13px] font-medium leading-4 text-[#B6BDC7]">New project</span>
            <span className="text-[13px] leading-4 text-[var(--fp-text-dim)]">— start from a blank .human</span>
          </button>
        )}
      </div>

      {pendingDelete ? (
        <ConfirmDeleteModal
          title={`project "${pendingDelete.name}"`}
          description="This deletes the project and all of its .human, .context, and .py snapshots."
          detail={pendingDelete.id.slice(0, 8)}
          disabled={busy}
          onCancel={() => setPendingDelete(null)}
          onConfirm={confirmDelete}
        />
      ) : null}
    </main>
  );
}
