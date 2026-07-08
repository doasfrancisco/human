"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ActionIconButton } from "@/components/ActionIconButton";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal";
import { createProject, deleteProject, getProjects, selectProject, type Project } from "@/lib/api";

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

  return (
    <main className="flex min-h-screen justify-center bg-zinc-950 px-4 py-16 text-zinc-100">
      <div className="w-full max-w-xl">
        <p className="text-xs uppercase tracking-[0.28em] text-zinc-500">fran++ v0.0.5</p>
        <div className="mt-2 flex items-end justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <button
            type="button"
            className="btn-primary"
            disabled={disabled}
            onClick={() => {
              setNewName("");
              setCreating(true);
            }}
          >
            + New project
          </button>
        </div>
        <p className="mt-2 text-sm text-zinc-500">
          Pick a project to open it in the editor. Each project keeps its own .human, .context, and .py snapshots.
        </p>

        <div className="mt-3 min-h-6 text-sm">
          {error ? <span className="text-red-400">{error}</span> : busy ? <span className="text-zinc-400">Working...</span> : null}
        </div>

        {creating ? (
          <form
            className="mt-2 flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              submitNewProject();
            }}
          >
            <input
              autoFocus
              value={newName}
              placeholder="project name"
              className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
              onChange={(event) => setNewName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setCreating(false);
              }}
            />
            <button type="submit" className="btn-primary" disabled={disabled || !newName.trim()}>
              Create
            </button>
            <button type="button" className="btn-secondary" disabled={disabled} onClick={() => setCreating(false)}>
              Cancel
            </button>
          </form>
        ) : null}

        <div className="mt-4">
          {!loaded ? (
            <p className="text-sm text-zinc-500">Loading projects...</p>
          ) : projects.length === 0 ? (
            creating ? null : (
              <div className="rounded-xl border border-dashed border-zinc-800 p-10 text-center">
                <h2 className="text-lg font-semibold text-zinc-100">No projects yet</h2>
                <p className="mt-2 text-sm text-zinc-500">Create your first project to start compiling.</p>
                <button
                  type="button"
                  className="btn-primary mt-5"
                  disabled={disabled}
                  onClick={() => {
                    setNewName("");
                    setCreating(true);
                  }}
                >
                  New project
                </button>
              </div>
            )
          ) : (
            <div className="space-y-2">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className={`flex items-center gap-2 rounded-xl border px-2 py-2 transition ${
                    project.active ? "border-indigo-500 bg-indigo-500/10" : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
                  }`}
                >
                  <button
                    type="button"
                    disabled={disabled}
                    className="min-w-0 flex-1 rounded-lg px-3 py-1.5 text-left"
                    onClick={() => openProject(project)}
                  >
                    <span className="flex items-center gap-2">
                      <span className={`truncate text-sm font-semibold ${project.active ? "text-zinc-100" : "text-zinc-300"}`}>
                        {project.name}
                      </span>
                      {project.active ? (
                        <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] font-bold uppercase text-indigo-300">
                          active
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block font-mono text-xs text-zinc-600">{project.id.slice(0, 8)}</span>
                  </button>
                  <ActionIconButton
                    icon="/icons/trash.svg"
                    label={`Delete project ${project.name}`}
                    danger
                    disabled={disabled}
                    onClick={() => setPendingDelete(project)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
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
