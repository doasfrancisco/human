"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { CodeEditor } from "@/components/CodeEditor";
import { DiffPreview } from "@/components/DiffPreview";
import {
  checkout,
  compileAll,
  contextToPython,
  deleteSnapshot,
  getBundle,
  getFiles,
  humanToContext,
  saveFiles,
  type Files,
  type TreeHuman,
} from "@/lib/api";

const initialFiles: Files = {
  human: "insertion sort",
  context: "",
  python: "",
  active: { humanHash: null, contextHash: null, pythonHash: null },
  status: { hasContext: false, hasPython: false },
  contextProvenance: [],
  tree: [],
};

type CursorSelection = {
  anchor: number;
  head: number;
};

type Busy =
  | "load"
  | "save"
  | "checkout"
  | "delete"
  | "human-to-context"
  | "context-to-python"
  | "compile-all"
  | null;

type FileKind = "human" | "context" | "python";

type PendingDelete = {
  kind: FileKind;
  hash: string;
  title: string;
  description: string;
} | null;

const fileLabels: Record<FileKind, { title: string; subtitle: string; mode: "text" | "python" }> = {
  human: {
    title: "program.human",
    subtitle: "freeform intent; exact text is the cache key",
    mode: "text",
  },
  context: {
    title: "program.context",
    subtitle: "LLM-expanded free-text context; generated per .human snapshot",
    mode: "text",
  },
  python: {
    title: "program.py",
    subtitle: "generated per .context snapshot",
    mode: "python",
  },
};

export default function Home() {
  const [files, setFiles] = useState<Files>(initialFiles);
  const [drafts, setDrafts] = useState<Pick<Files, "human" | "context" | "python">>(initialFiles);
  const [selected, setSelected] = useState<FileKind>("human");
  const [selections, setSelections] = useState<Record<FileKind, CursorSelection>>({
    human: { anchor: initialFiles.human.length, head: initialFiles.human.length },
    context: { anchor: 0, head: 0 },
    python: { anchor: 0, head: 0 },
  });
  const [mounted, setMounted] = useState(false);
  const [expandedFlows, setExpandedFlows] = useState<Record<string, boolean>>({});
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [highlightedContextLines, setHighlightedContextLines] = useState<number[]>([]);
  const [modKeyDown, setModKeyDown] = useState(false);
  const [busy, setBusy] = useState<Busy>("load");
  const [message, setMessage] = useState("Loading workspace...");
  const [error, setError] = useState<string | null>(null);

  function adoptWorkspace(nextFiles: Files) {
    setFiles(nextFiles);
    setDrafts({
      human: nextFiles.human,
      context: nextFiles.context,
      python: nextFiles.python,
    });
  }

  async function run(label: Busy, action: () => Promise<Files>, success: string, after?: (files: Files) => void) {
    setBusy(label);
    setError(null);
    setMessage("Working...");
    try {
      const nextFiles = await action();
      adoptWorkspace(nextFiles);
      after?.(nextFiles);
      setMessage(success);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Failed");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setMounted(true);
      void run("load", getFiles, "Workspace loaded");
    });
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey) setModKeyDown(true);
    }

    function onKeyUp(event: KeyboardEvent) {
      if (!event.ctrlKey && !event.metaKey) setModKeyDown(false);
    }

    function onBlur() {
      setModKeyDown(false);
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
    };
  }, []);

  const disabled = busy !== null;
  const selectedDirty = drafts[selected] !== files[selected];
  const humanDirty = drafts.human !== files.human;
  const contextDirty = drafts.context !== files.context;

  function setDraft(kind: FileKind, value: string) {
    setDrafts((current) => ({ ...current, [kind]: value }));
  }

  function setEditorSelection(kind: FileKind, selection: CursorSelection) {
    setSelections((current) => ({ ...current, [kind]: selection }));
  }

  if (!mounted) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-100">
        <div className="text-center">
          <p className="text-xs uppercase tracking-[0.28em] text-zinc-500">fran++ v0.0.5</p>
          <h1 className="mt-2 text-2xl font-semibold">Loading editor…</h1>
        </div>
      </main>
    );
  }

  function saveSelected() {
    const payload =
      selected === "human"
        ? { human: drafts.human }
        : selected === "context"
          ? { context: drafts.context }
          : { python: drafts.python };
    run("save", () => saveFiles(payload), `Saved / looked up ${fileLabels[selected].title}`);
  }

  async function copySelected() {
    try {
      await navigator.clipboard.writeText(drafts[selected]);
      setError(null);
      setMessage(`Copied ${fileLabels[selected].title}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Copy failed");
    }
  }

  function programBundleText(bundle: Pick<Files, "human" | "context" | "python">) {
    return [
      "--- program.human ---",
      bundle.human,
      "--- program.context ---",
      bundle.context,
      "--- program.py ---",
      bundle.python,
    ].join("\n\n");
  }

  async function copyWorkspace() {
    try {
      await navigator.clipboard.writeText(programBundleText(drafts));
      setError(null);
      setMessage("Copied current program");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Copy failed");
    }
  }

  async function copyFlow(humanHash: string) {
    try {
      const bundle = await getBundle(humanHash);
      await navigator.clipboard.writeText(programBundleText(bundle));
      setError(null);
      setMessage("Copied history flow");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Copy failed");
    }
  }

  function toggleFlow(hash: string) {
    setExpandedFlows((current) => ({ ...current, [hash]: !(current[hash] ?? true) }));
  }

  function deleteDescription(kind: FileKind) {
    if (kind === "human") return "This deletes the .human flow and all of its .context and .py descendants.";
    if (kind === "context") return "This deletes this .context snapshot and its generated .py descendants.";
    return "This deletes only this .py snapshot.";
  }

  function requestDelete(kind: FileKind, hash: string | null, title = fileLabels[kind].title) {
    if (!hash) return;
    setPendingDelete({ kind, hash, title, description: deleteDescription(kind) });
  }

  function requestDeleteSelected() {
    const hash =
      selected === "human"
        ? files.active.humanHash
        : selected === "context"
          ? files.active.contextHash
          : files.active.pythonHash;
    requestDelete(selected, hash);
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    run("delete", () => deleteSnapshot(target.kind, target.hash), `Deleted ${target.title}`, (nextFiles) => {
      setHighlightedContextLines([]);
      if (target.kind === "human") setSelected("human");
      else if (target.kind === "context" && !nextFiles.status.hasContext) setSelected("human");
      else if (target.kind === "python" && !nextFiles.status.hasPython) setSelected("context");
    });
  }

  function humanPhrasesFromSource(source: string) {
    return [...source.matchAll(/human phrase "([^"]+)"/g)].map((match) => match[1]).filter(Boolean);
  }

  function phraseRanges(text: string, phrase: string) {
    const ranges: Array<{ start: number; end: number }> = [];
    if (!phrase) return ranges;
    const lowerText = text.toLowerCase();
    const lowerPhrase = phrase.toLowerCase();
    let index = lowerText.indexOf(lowerPhrase);
    while (index !== -1) {
      ranges.push({ start: index, end: index + phrase.length });
      index = lowerText.indexOf(lowerPhrase, index + 1);
    }
    return ranges;
  }

  function phraseContainsPosition(text: string, phrase: string, pos: number) {
    return phraseRanges(text, phrase).some((range) => pos >= range.start && pos <= range.end);
  }

  function humanOriginRanges() {
    if (!modKeyDown || selected !== "human") return [];
    const seen = new Set<string>();
    const ranges: Array<{ from: number; to: number }> = [];
    for (const entry of files.contextProvenance) {
      for (const phrase of humanPhrasesFromSource(entry.source)) {
        for (const range of phraseRanges(drafts.human, phrase)) {
          const key = `${range.start}:${range.end}`;
          if (seen.has(key)) continue;
          seen.add(key);
          ranges.push({ from: range.start, to: range.end });
        }
      }
    }
    return ranges;
  }

  function handleHumanModClick(pos: number) {
    const matches = files.contextProvenance.flatMap((entry) =>
      humanPhrasesFromSource(entry.source).map((phrase) => ({ phrase, line: Number(entry.line) }))
    );
    const clicked = matches
      .filter((match) => Number.isFinite(match.line) && phraseContainsPosition(drafts.human, match.phrase, pos))
      .sort((a, b) => b.phrase.length - a.phrase.length);

    if (!clicked.length) {
      setHighlightedContextLines([]);
      setMessage("No context provenance found for that human span");
      return;
    }

    const phrase = clicked[0].phrase;
    const lines = Array.from(
      new Set(
        matches
          .filter((match) => match.phrase.toLowerCase() === phrase.toLowerCase() && Number.isFinite(match.line))
          .map((match) => match.line)
      )
    ).sort((a, b) => a - b);

    setHighlightedContextLines(lines);
    setSelected("context");
    setMessage(`Highlighted ${lines.length} .context line${lines.length === 1 ? "" : "s"} from "${phrase}"`);
  }

  return (
    <main className="flex min-h-screen bg-zinc-950 text-zinc-100">
      <aside className="flex w-[330px] shrink-0 flex-col border-r border-zinc-800 bg-zinc-950">
        <div className="border-b border-zinc-800 px-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-zinc-500">fran++ v0.0.5</p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">Compile tree</h1>
            </div>
            <div className="icon-action-row">
              <ActionIconButton icon="/icons/copy.svg" label="Copy current program" disabled={disabled} onClick={copyWorkspace} />
            </div>
          </div>
          <p className="mt-2 text-xs leading-5 text-zinc-500">
            Exact text snapshots are cached. If you return to a previous .human, its old .context and .py come back.
          </p>
        </div>

        <div className="border-b border-zinc-800 p-3">
          <SidebarFile
            selected={selected === "human"}
            title="program.human"
            hash={files.active.humanHash}
            dirty={humanDirty}
            status="source"
            onClick={() => setSelected("human")}
          />
          <SidebarFile
            selected={selected === "context"}
            title="program.context"
            hash={files.active.contextHash}
            dirty={contextDirty}
            status={humanDirty ? "waiting for .human" : files.status.hasContext ? "generated" : "missing"}
            onClick={() => setSelected("context")}
          />
          <SidebarFile
            selected={selected === "python"}
            title="program.py"
            hash={files.active.pythonHash}
            dirty={drafts.python !== files.python}
            status={humanDirty || contextDirty ? "waiting for parent" : files.status.hasPython ? "generated" : "missing"}
            onClick={() => setSelected("python")}
          />
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-3">
          <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">History</h2>
          {files.tree.length === 0 ? (
            <p className="px-1 text-sm text-zinc-500">No snapshots yet.</p>
          ) : (
            <TreeView
              tree={files.tree}
              disabled={disabled}
              expanded={expandedFlows}
              onToggle={toggleFlow}
              onCopyFlow={copyFlow}
              onCheckout={(kind, hash) => run("checkout", () => checkout(kind, hash), `Checked out ${kind}`)}
            />
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-zinc-800 px-5 py-4">
          <div>
            <h2 className="font-mono text-lg font-semibold text-zinc-100">{fileLabels[selected].title}</h2>
            <p className="mt-1 text-sm text-zinc-500">{fileLabels[selected].subtitle}</p>
            <p className="mt-2 font-mono text-xs text-zinc-600">
              active: {hashShort(files.active.humanHash)} → {hashShort(files.active.contextHash)} → {hashShort(files.active.pythonHash)}
            </p>
          </div>

          <div className="mt-3 min-h-6 text-sm">
            {error ? <span className="text-red-400">{error}</span> : <span className="text-zinc-400">{message}</span>}
          </div>
        </header>

        <div className="min-h-0 flex-1 p-3">{renderBody()}</div>
      </section>

      {pendingDelete ? (
        <ConfirmDeleteModal target={pendingDelete} disabled={disabled} onCancel={() => setPendingDelete(null)} onConfirm={confirmDelete} />
      ) : null}
    </main>
  );

  function fileActions() {
    if (selected === "human") {
      return (
        <div className="icon-action-row">
          <ActionIconButton icon="/icons/copy.svg" label="Copy .human" disabled={disabled} onClick={copySelected} />
          <ActionIconButton icon="/icons/trash.svg" label="Delete .human flow" danger disabled={disabled || selectedDirty || !files.active.humanHash} onClick={requestDeleteSelected} />
          <ActionIconButton icon="/icons/save.svg" label="Save .human" disabled={disabled || !selectedDirty} onClick={saveSelected} />
          <ActionIconButton
            icon="/icons/sparkles.svg"
            label="Generate .context"
            primary
            disabled={disabled || !drafts.human.trim()}
            onClick={() => run("human-to-context", () => humanToContext(drafts.human), "Resolved .context for .human", () => setSelected("context"))}
          />
          <ActionIconButton
            icon="/icons/compile-all.svg"
            label="Compile all"
            disabled={disabled || !drafts.human.trim()}
            onClick={() => run("compile-all", () => compileAll(drafts.human), "Resolved full tree", () => setSelected("python"))}
          />
        </div>
      );
    }

    if (selected === "context") {
      return (
        <div className="icon-action-row">
          <ActionIconButton icon="/icons/copy.svg" label="Copy .context" disabled={disabled} onClick={copySelected} />
          <ActionIconButton icon="/icons/trash.svg" label="Delete .context and .py" danger disabled={disabled || selectedDirty || !files.active.contextHash} onClick={requestDeleteSelected} />
          <ActionIconButton icon="/icons/save.svg" label="Save .context" disabled={disabled || !selectedDirty} onClick={saveSelected} />
          <ActionIconButton
            icon="/icons/sparkles.svg"
            label="Generate .py"
            primary
            disabled={disabled || humanDirty || !drafts.context.trim()}
            onClick={() => run("context-to-python", () => contextToPython(drafts.context), "Resolved .py for .context", () => setSelected("python"))}
          />
        </div>
      );
    }

    return (
      <div className="icon-action-row">
        <ActionIconButton icon="/icons/copy.svg" label="Copy .py" disabled={disabled} onClick={copySelected} />
        <ActionIconButton icon="/icons/trash.svg" label="Delete .py" danger disabled={disabled || selectedDirty || !files.active.pythonHash} onClick={requestDeleteSelected} />
        <ActionIconButton icon="/icons/save.svg" label="Save .py" disabled={disabled || !selectedDirty} onClick={saveSelected} />
      </div>
    );
  }

  function renderBody() {
    if (selected === "context" && humanDirty) {
      return (
        <PendingPane
          title=".human has a draft change"
          body="Save / lookup the .human snapshot or compile it before viewing the context for that exact text."
          action="Save / lookup .human"
          disabled={disabled}
          onClick={() => run("save", () => saveFiles({ human: drafts.human }), "Saved / looked up .human")}
        />
      );
    }

    if (selected === "python" && (humanDirty || contextDirty)) {
      return (
        <PendingPane
          title="Parent file has a draft change"
          body="Save / lookup the changed parent, then generate the downstream file."
          action={humanDirty ? "Save / lookup .human" : "Save / lookup .context"}
          disabled={disabled}
          onClick={() =>
            humanDirty
              ? run("save", () => saveFiles({ human: drafts.human }), "Saved / looked up .human")
              : run("save", () => saveFiles({ context: drafts.context }), "Saved / looked up .context")
          }
        />
      );
    }

    if (selected === "context" && !files.status.hasContext && !selectedDirty) {
      return (
        <PendingPane
          title="No .context exists for this exact .human snapshot"
          body="Generate it once. If you come back to this same .human later, the cached context will be reused."
          action="Generate Human → Context"
          disabled={disabled}
          onClick={() => run("human-to-context", () => humanToContext(drafts.human), "Generated .context", () => setSelected("context"))}
        />
      );
    }

    if (selected === "python" && !files.status.hasPython && !selectedDirty) {
      return (
        <PendingPane
          title="No .py exists for this exact .context snapshot"
          body="Generate it once. If you return to this same context later, the cached Python will be reused."
          action="Generate Context → Python"
          disabled={disabled || !files.status.hasContext}
          onClick={() => run("context-to-python", () => contextToPython(drafts.context), "Generated .py", () => setSelected("python"))}
        />
      );
    }

    if (selectedDirty) {
      return (
        <DirtyEditor
          kind={selected}
          saved={files[selected]}
          draft={drafts[selected]}
          selection={selections[selected]}
          actions={fileActions()}
          highlightedLines={selected === "context" ? highlightedContextLines : []}
          highlightedRanges={selected === "human" ? humanOriginRanges() : []}
          onChange={(value) => setDraft(selected, value)}
          onSelectionChange={(selection) => setEditorSelection(selected, selection)}
          onModClick={selected === "human" ? ({ pos }) => handleHumanModClick(pos) : undefined}
        />
      );
    }

    return (
      <EditorShell title="current snapshot" subtitle="editable; first change opens a diff preview on the right" actions={fileActions()}>
        <CodeEditor
          value={drafts[selected]}
          mode={fileLabels[selected].mode}
          autoFocus
          selection={selections[selected]}
          highlightedLines={selected === "context" ? highlightedContextLines : []}
          highlightedRanges={selected === "human" ? humanOriginRanges() : []}
          onChange={(value) => setDraft(selected, value)}
          onSelectionChange={(selection) => setEditorSelection(selected, selection)}
          onModClick={selected === "human" ? ({ pos }) => handleHumanModClick(pos) : undefined}
        />
      </EditorShell>
    );
  }
}

function SidebarFile({
  selected,
  title,
  hash,
  dirty,
  status,
  onClick,
}: {
  selected: boolean;
  title: string;
  hash: string | null;
  dirty: boolean;
  status: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`mb-2 w-full rounded-lg border px-3 py-2 text-left transition ${
        selected ? "border-indigo-500 bg-indigo-500/10" : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-sm font-semibold text-zinc-100">{title}</span>
        {dirty ? <span className="rounded-full bg-yellow-500/15 px-2 py-0.5 text-[10px] font-bold uppercase text-yellow-300">draft</span> : null}
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs text-zinc-500">
        <span>{status}</span>
        <span className="font-mono">{hashShort(hash)}</span>
      </div>
    </button>
  );
}

function TreeView({
  tree,
  disabled,
  expanded,
  onToggle,
  onCopyFlow,
  onCheckout,
}: {
  tree: TreeHuman[];
  disabled: boolean;
  expanded: Record<string, boolean>;
  onToggle: (hash: string) => void;
  onCopyFlow: (humanHash: string) => void;
  onCheckout: (kind: FileKind, hash: string) => void;
}) {
  return (
    <div className="space-y-2">
      {tree.map((human) => {
        const contexts = human.contexts.length ? human.contexts : human.context ? [human.context] : [];
        const isExpanded = expanded[human.hash] ?? true;

        return (
          <div
            key={human.hash}
            className={`rounded-lg border bg-zinc-900/70 p-2 ${human.active ? "border-indigo-500/60" : "border-zinc-800"}`}
          >
            <div className="flex items-start gap-1">
              <button
                type="button"
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
                aria-label={isExpanded ? "Collapse flow" : "Expand flow"}
                title={isExpanded ? "Collapse flow" : "Expand flow"}
                onClick={() => onToggle(human.hash)}
              >
                <span
                  className="icon-mask"
                  style={{ "--icon-url": `url(${isExpanded ? "/icons/chevron-down.svg" : "/icons/chevron-right.svg"})` } as CSSProperties}
                />
              </button>
              <TreeButton
                active={human.active}
                label=".human"
                preview={human.preview}
                hash={human.hash}
                disabled={disabled}
                onClick={() => onCheckout("human", human.hash)}
              />
              <div className="icon-action-row shrink-0">
                <ActionIconButton icon="/icons/copy.svg" label="Copy this flow" disabled={disabled} onClick={() => onCopyFlow(human.hash)} />
              </div>
            </div>

            {isExpanded ? (
              contexts.length ? (
                <div className="ml-10 mt-2 space-y-2 border-l border-zinc-800 pl-3">
                  {contexts.map((context) => {
                    const pythons = context.pythons.length ? context.pythons : context.python ? [context.python] : [];

                    return (
                      <div key={context.hash}>
                        <TreeButton
                          active={context.active}
                          label=".context"
                          preview={context.preview}
                          hash={context.hash}
                          disabled={disabled}
                          onClick={() => onCheckout("context", context.hash)}
                        />
                        {pythons.length ? (
                          <div className="ml-4 mt-2 space-y-2 border-l border-zinc-800 pl-3">
                            {pythons.map((python) => (
                              <TreeButton
                                key={python.hash}
                                active={python.active}
                                label=".py"
                                preview={python.preview}
                                hash={python.hash}
                                disabled={disabled}
                                onClick={() => onCheckout("python", python.hash)}
                              />
                            ))}
                          </div>
                        ) : (
                          <MissingNode label=".py missing" />
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <MissingNode label=".context missing" />
              )
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function TreeButton({
  active,
  label,
  preview,
  hash,
  disabled,
  onClick,
}: {
  active: boolean;
  label: string;
  preview: string;
  hash: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`w-full rounded-md px-2 py-1.5 text-left ${active ? "bg-indigo-500/15" : "hover:bg-zinc-800"}`}
    >
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-mono font-semibold text-zinc-300">{label}</span>
        <span className="font-mono text-zinc-600">{hashShort(hash)}</span>
      </div>
      <p className="mt-1 truncate text-xs text-zinc-500">{preview}</p>
    </button>
  );
}

function MissingNode({ label }: { label: string }) {
  return <div className="ml-4 mt-2 border-l border-zinc-800 py-1 pl-3 text-xs text-zinc-600">{label}</div>;
}

function ConfirmDeleteModal({
  target,
  disabled,
  onCancel,
  onConfirm,
}: {
  target: NonNullable<PendingDelete>;
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
            <h3 className="text-lg font-semibold text-zinc-100">Delete {target.title}?</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">{target.description}</p>
            <p className="mt-3 font-mono text-xs text-zinc-600">{hashShort(target.hash)}</p>
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

function ActionIconButton({
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

function DirtyEditor({
  kind,
  saved,
  draft,
  selection,
  actions,
  highlightedLines,
  highlightedRanges,
  onChange,
  onSelectionChange,
  onModClick,
}: {
  kind: FileKind;
  saved: string;
  draft: string;
  selection: CursorSelection;
  actions: ReactNode;
  highlightedLines: number[];
  highlightedRanges: Array<{ from: number; to: number }>;
  onChange: (value: string) => void;
  onSelectionChange: (selection: CursorSelection) => void;
  onModClick?: (event: { pos: number; line: number; lineText: string }) => void;
}) {
  return (
    <div className="grid h-full grid-cols-1 gap-3 xl:grid-cols-2">
      <EditorShell title="draft" subtitle="editable new text; this is where you keep typing" actions={actions}>
        <CodeEditor
          value={draft}
          mode={fileLabels[kind].mode}
          autoFocus
          selection={selection}
          highlightedLines={highlightedLines}
          highlightedRanges={highlightedRanges}
          onChange={onChange}
          onSelectionChange={onSelectionChange}
          onModClick={onModClick}
        />
      </EditorShell>
      <EditorShell title="changes" subtitle="read-only diff against the saved snapshot">
        <DiffPreview
          filename={filenameFor(kind)}
          before={saved}
          after={draft}
          language={kind === "python" ? "python" : undefined}
        />
      </EditorShell>
    </div>
  );
}

function EditorShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-[520px] flex-col overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl xl:min-h-0">
      <div className="flex flex-col gap-3 border-b border-zinc-800 px-4 py-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 className="font-mono text-sm font-semibold text-zinc-100">{title}</h3>
          <p className="mt-1 text-xs text-zinc-500">{subtitle}</p>
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function PendingPane({
  title,
  body,
  action,
  disabled,
  onClick,
}: {
  title: string;
  body: string;
  action: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <div className="flex h-full min-h-[520px] items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-900/50 p-8">
      <div className="max-w-lg text-center">
        <h3 className="text-xl font-semibold text-zinc-100">{title}</h3>
        <p className="mt-3 leading-7 text-zinc-500">{body}</p>
        <button className="btn-primary mt-6" disabled={disabled} onClick={onClick}>
          {action}
        </button>
      </div>
    </div>
  );
}

function hashShort(hash: string | null) {
  return hash ? hash.slice(0, 8) : "—";
}

function filenameFor(kind: FileKind) {
  if (kind === "python") return "program.py";
  if (kind === "context") return "program.context";
  return "program.human";
}

