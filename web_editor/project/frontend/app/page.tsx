"use client";

import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ActionIconButton } from "@/components/ActionIconButton";
import { CodeEditor } from "@/components/CodeEditor";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal";
import { DiffPreview } from "@/components/DiffPreview";
import { ExplorerSidebar } from "@/components/ExplorerSidebar";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileHumanIcon,
  FileJsonIcon,
  FilePythonIcon,
  ICON_BY_EXTENSION,
  SparklesIcon,
  type IconProps,
} from "@/components/icons";
import {
  checkout,
  compile,
  contextToPython,
  fsDelete,
  fsRead,
  fsWrite,
  getBundle,
  getFiles,
  getProjects,
  humanToContext,
  reword,
  saveFiles,
  DEFAULT_PROGRAM,
  type CompiledUnit,
  type ContextRole,
  type FileNode,
  type Files,
  type Project,
  type TreeHuman,
} from "@/lib/api";

const initialFiles: Files = {
  name: DEFAULT_PROGRAM,
  human: "",
  context: "",
  python: "",
  units: [],
  active: { humanHash: null, contextHash: null, pythonHash: null },
  status: { hasContext: false, hasPython: false },
  contextRole: null,
  contextProvenance: [],
  pythonProvenance: [],
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
  | "compile"
  | "reword"
  | null;

type FileKind = "human" | "context" | "python";

type PlainTab = {
  path: string;
  name: string;
  saved: string;
  draft: string;
};

type RewordDraft = {
  start: number;
  end: number;
  original: string;
  text: string;
} | null;

const fileMeta: Record<FileKind, { extension: string; subtitle: string; mode: "text" | "python" }> = {
  human: {
    extension: "human",
    subtitle: "",
    mode: "text",
  },
  context: {
    extension: "context",
    subtitle: "LLM-expanded free-text context; generated per .human snapshot",
    mode: "text",
  },
  python: {
    extension: "py",
    subtitle: "generated per .context snapshot",
    mode: "python",
  },
};

function fileTitle(kind: FileKind, name: string) {
  return `${name}.${fileMeta[kind].extension}`;
}

function programNameFromFile(fileName: string) {
  const match = fileName.match(/^(.+)\.(human|context|py)$/);
  return match ? match[1] : null;
}

function kindFromFileName(fileName: string): FileKind | null {
  if (fileName.endsWith(".human")) return "human";
  if (fileName.endsWith(".context")) return "context";
  if (fileName.endsWith(".py")) return "python";
  return null;
}

function plainTabIcon(fileName: string) {
  const dot = fileName.lastIndexOf(".");
  const ext = dot > 0 ? fileName.slice(dot) : "";
  return ICON_BY_EXTENSION[ext] ?? FileHumanIcon;
}

function tabWithinPath(tabPath: string, targetPath: string) {
  return tabPath === targetPath || tabPath.startsWith(`${targetPath}/`) || tabPath.startsWith(`${targetPath}\\`);
}

const KINDS: FileKind[] = ["human", "context", "python"];

const fileGlyphs: Record<FileKind, (props: IconProps) => ReactElement> = {
  human: FileHumanIcon,
  context: FileJsonIcon,
  python: FilePythonIcon,
};

export default function Home() {
  const router = useRouter();
  const [files, setFiles] = useState<Files>(initialFiles);
  const [programName, setProgramName] = useState(DEFAULT_PROGRAM);
  const [programLoaded, setProgramLoaded] = useState(false);
  const [drafts, setDrafts] = useState<Pick<Files, "human" | "context" | "python">>(initialFiles);
  const [selected, setSelected] = useState<FileKind>("human");
  const [selections, setSelections] = useState<Record<FileKind, CursorSelection>>({
    human: { anchor: initialFiles.human.length, head: initialFiles.human.length },
    context: { anchor: 0, head: 0 },
    python: { anchor: 0, head: 0 },
  });
  const [mounted, setMounted] = useState(false);
  const [expandedFlows, setExpandedFlows] = useState<Record<string, boolean>>({});
  const [plainTabs, setPlainTabs] = useState<PlainTab[]>([]);
  const [activePlain, setActivePlain] = useState<string | null>(null);
  const [activeUnit, setActiveUnit] = useState<string | null>(null);
  const [closedUnits, setClosedUnits] = useState<Record<string, boolean>>({});
  const [unitHighlight, setUnitHighlight] = useState<{ target: string; lines: number[] } | null>(null);
  const [closedKinds, setClosedKinds] = useState<Record<FileKind, boolean>>({
    human: false,
    context: false,
    python: false,
  });
  const [fsDeleteTarget, setFsDeleteTarget] = useState<FileNode | null>(null);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [highlighted, setHighlighted] = useState<{ kind: FileKind; lines: number[] }>({
    kind: "context",
    lines: [],
  });
  const [rewordDraft, setRewordDraft] = useState<RewordDraft>(null);
  const [modKeyDown, setModKeyDown] = useState(false);
  const [treeVersion, setTreeVersion] = useState(0);
  const [busy, setBusy] = useState<Busy>(null);
  const [message, setMessage] = useState("Open or create a file to get started");
  const [error, setError] = useState<string | null>(null);
  const saveShortcutRef = useRef<() => void>(() => {});

  function rebasedDraft(current: string, previous: string, next: string) {
    return current !== previous && current !== next ? current : next;
  }

  function adoptWorkspace(nextFiles: Files, mode: "merge" | "replace" = "merge") {
    const nextName = nextFiles.name || DEFAULT_PROGRAM;
    const sameProgram = nextName === programName && programLoaded;
    setFiles(nextFiles);
    setProgramName(nextName);
    setProgramLoaded(true);
    if (mode === "merge" && sameProgram) {
      setDrafts((current) => ({
        human: rebasedDraft(current.human, files.human, nextFiles.human),
        context: rebasedDraft(current.context, files.context, nextFiles.context),
        python: rebasedDraft(current.python, files.python, nextFiles.python),
      }));
    } else {
      setDrafts({
        human: nextFiles.human,
        context: nextFiles.context,
        python: nextFiles.python,
      });
    }
    if (!nextFiles.units.length) {
      setActiveUnit(null);
      setClosedUnits({});
      setUnitHighlight(null);
    }
  }

  function focusUnits(nextFiles: Files, preferredTarget?: string | null) {
    if (!nextFiles.units.length) return false;
    const match = preferredTarget
      ? nextFiles.units.find((unit) => unit.target === preferredTarget)
      : undefined;
    setClosedUnits({});
    setUnitHighlight(null);
    setActivePlain(null);
    setActiveUnit((match ?? nextFiles.units[0]).target);
    return true;
  }

  async function run(label: Busy, action: () => Promise<Files>, success: string, after?: (files: Files) => void) {
    setBusy(label);
    setError(null);
    setMessage("Working...");
    try {
      const nextFiles = await action();
      adoptWorkspace(nextFiles, label === "checkout" ? "replace" : "merge");
      setTreeVersion((version) => version + 1);
      after?.(nextFiles);
      setMessage(success);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Failed");
    } finally {
      setBusy(null);
    }
  }

  async function loadActiveProject() {
    try {
      const list = await getProjects();
      const active = list.projects.find((project) => project.active) ?? null;
      setActiveProject(active);
      if (!active) router.replace("/projects");
    } catch {
      setActiveProject(null);
    }
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setMounted(true);
      void loadActiveProject();
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

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveShortcutRef.current();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const disabled = busy !== null;
  const plainTab = activePlain !== null ? (plainTabs.find((tab) => tab.path === activePlain) ?? null) : null;
  const unitList = files.units;
  const visibleUnits = unitList.filter((unit) => !closedUnits[unit.target]);
  const activeUnitTab =
    activeUnit !== null ? (visibleUnits.find((unit) => unit.target === activeUnit) ?? null) : null;
  const provenanceKind: "context" | "python" = files.contextRole === "direct" ? "python" : "context";
  const activeProvenance = files.contextRole === "direct" ? files.pythonProvenance : files.contextProvenance;
  const provenanceLabel = provenanceKind === "python" ? ".py" : ".context";
  const selectedDirty = drafts[selected] !== files[selected];
  const humanDirty = drafts.human !== files.human;
  const contextDirty = drafts.context !== files.context;
  const pythonDirty = drafts.python !== files.python;
  const showContextCard = files.status.hasContext && files.contextRole !== "direct";
  const activeHash = plainTab
    ? null
    : activeUnitTab
      ? activeUnitTab.hash
      : selected === "human"
        ? files.active.humanHash
        : selected === "context"
          ? files.active.contextHash
          : files.active.pythonHash;

  function isKindVisible(kind: FileKind) {
    if (!programLoaded) return false;
    if (closedKinds[kind]) return false;
    if (kind === "context") return showContextCard;
    if (kind === "python") return !unitList.length;
    return true;
  }

  const visibleKinds = KINDS.filter((kind) => isKindVisible(kind));

  if (activeUnit !== null && !activeUnitTab) {
    setActiveUnit(null);
  }

  if (!plainTab && !activeUnitTab && !isKindVisible(selected) && visibleKinds.length) {
    setSelected(
      selected === "context" && (files.contextRole === "direct" || files.status.hasPython) && isKindVisible("python")
        ? "python"
        : visibleKinds[0]
    );
  }

  function saveSelected() {
    const payload =
      selected === "human"
        ? { human: drafts.human }
        : selected === "context"
          ? { context: drafts.context }
          : { python: drafts.python };
    run("save", () => saveFiles(payload, programName), `Saved / looked up ${fileTitle(selected, programName)}`);
  }

  async function savePlainTab(tab: PlainTab) {
    setBusy("save");
    setError(null);
    setMessage("Working...");
    try {
      await fsWrite(tab.path, tab.draft);
      setPlainTabs((current) =>
        current.map((entry) => (entry.path === tab.path ? { ...entry, saved: tab.draft } : entry))
      );
      setMessage(`Saved ${tab.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Failed");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    saveShortcutRef.current = () => {
      if (busy !== null) return;
      if (plainTab) {
        if (plainTab.draft === plainTab.saved) return;
        void savePlainTab(plainTab);
        return;
      }
      if (activeUnitTab) return;
      if (!isKindVisible(selected) || !selectedDirty) return;
      saveSelected();
    };
  });

  function setDraft(kind: FileKind, value: string) {
    setDrafts((current) => ({ ...current, [kind]: value }));
  }

  function setEditorSelection(kind: FileKind, selection: CursorSelection) {
    setSelections((current) => ({ ...current, [kind]: selection }));
  }

  if (!mounted) {
    return (
      <main className="flex h-screen items-center justify-center bg-[#101317] text-[#E7EAF0]">
        <div className="text-center">
          <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#5C6470]">fran++ v0.0.5</p>
          <h1 className="mt-2 text-lg font-semibold">Loading editor…</h1>
        </div>
      </main>
    );
  }

  function openProgramFile(node: FileNode) {
    const nextName = programNameFromFile(node.name);
    const kind = kindFromFileName(node.name);
    if (!nextName || !kind) return;
    setClosedKinds((current) => ({ ...current, [kind]: false }));
    setActivePlain(null);
    if (nextName === programName && programLoaded) {
      if (kind === "python" && focusUnits(files)) return;
      setActiveUnit(null);
      setSelected(kind);
      return;
    }
    if (disabled) return;
    run("load", () => getFiles(nextName), `Loaded program ${nextName}`, (nextFiles) => {
      setHighlighted({ kind: "context", lines: [] });
      if (kind === "python" && focusUnits(nextFiles)) return;
      if (nextFiles.units.length) setClosedUnits({});
      setActiveUnit(null);
      setSelected(kind);
    });
  }

  async function openPlainFile(node: FileNode) {
    setActiveUnit(null);
    const existing = plainTabs.find((tab) => tab.path === node.path);
    if (existing) {
      setActivePlain(existing.path);
      return;
    }
    try {
      const file = await fsRead(node.path);
      setPlainTabs((current) =>
        current.some((tab) => tab.path === file.path)
          ? current
          : [...current, { path: file.path, name: file.name, saved: file.content, draft: file.content }]
      );
      setActivePlain(file.path);
      setError(null);
      setMessage(`Opened ${file.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Open failed");
    }
  }

  async function openCreatedFile(node: FileNode) {
    const nextName = programNameFromFile(node.name);
    const kind = kindFromFileName(node.name);
    if (!nextName || !kind) {
      await openPlainFile(node);
      return;
    }
    let content = "";
    try {
      content = (await fsRead(node.path)).content;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Open failed");
      return;
    }
    setClosedKinds((current) => ({ ...current, [kind]: false }));
    setActivePlain(null);
    if (nextName === programName && programLoaded) {
      setFiles((current) => ({ ...current, [kind]: content }));
      setDrafts((current) => ({ ...current, [kind]: content }));
      setActiveUnit(null);
      setSelected(kind);
      return;
    }
    if (disabled) return;
    void run("load", () => getFiles(nextName), `Loaded program ${nextName}`, () => {
      setHighlighted({ kind: "context", lines: [] });
      setFiles((current) => ({ ...current, [kind]: content }));
      setDrafts((current) => ({ ...current, [kind]: content }));
      setClosedUnits({});
      setActiveUnit(null);
      setSelected(kind);
    });
  }

  function openFile(node: FileNode) {
    if (node.type !== "file") return;
    const unit = unitList.find((candidate) => candidate.target === node.name);
    if (unit) {
      setClosedUnits((current) => ({ ...current, [unit.target]: false }));
      setActivePlain(null);
      setActiveUnit(unit.target);
      return;
    }
    if (kindFromFileName(node.name) && programNameFromFile(node.name)) openProgramFile(node);
    else void openPlainFile(node);
  }

  function closePipelineTab(kind: FileKind) {
    const remaining = visibleKinds.filter((visible) => visible !== kind);
    setClosedKinds((current) => ({ ...current, [kind]: true }));
    if (!plainTab && !activeUnitTab && selected === kind && !remaining.length) {
      if (visibleUnits.length) setActiveUnit(visibleUnits[0].target);
      else if (plainTabs.length) setActivePlain(plainTabs[plainTabs.length - 1].path);
    }
  }

  function closeUnitTab(target: string) {
    const remaining = visibleUnits.filter((unit) => unit.target !== target);
    setClosedUnits((current) => ({ ...current, [target]: true }));
    if (activeUnit === target) {
      if (remaining.length) {
        setActiveUnit(remaining[remaining.length - 1].target);
      } else {
        setActiveUnit(null);
        if (!plainTab && !visibleKinds.length && plainTabs.length) {
          setActivePlain(plainTabs[plainTabs.length - 1].path);
        }
      }
    }
  }

  function closePlainTab(path: string) {
    const remaining = plainTabs.filter((tab) => tab.path !== path);
    setPlainTabs(remaining);
    if (activePlain === path) {
      setActivePlain(remaining.length ? remaining[remaining.length - 1].path : null);
    }
  }

  async function confirmFsDelete() {
    if (!fsDeleteTarget) return;
    const target = fsDeleteTarget;
    setFsDeleteTarget(null);
    setBusy("delete");
    setError(null);
    setMessage("Working...");
    try {
      await fsDelete(target.path);
      const remaining = plainTabs.filter((tab) => !tabWithinPath(tab.path, target.path));
      setPlainTabs(remaining);
      if (activePlain !== null && tabWithinPath(activePlain, target.path)) {
        setActivePlain(remaining.length ? remaining[remaining.length - 1].path : null);
      }
      const kind = kindFromFileName(target.name);
      if (target.type === "file" && kind && programNameFromFile(target.name) === programName) {
        setClosedKinds((current) => ({ ...current, [kind]: true }));
      }
      setTreeVersion((version) => version + 1);
      setMessage(`Deleted ${target.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Failed");
    } finally {
      setBusy(null);
    }
  }

  async function copySelected() {
    try {
      await navigator.clipboard.writeText(
        plainTab ? plainTab.draft : activeUnitTab ? activeUnitTab.python : drafts[selected]
      );
      setError(null);
      setMessage(`Copied ${plainTab ? plainTab.name : activeUnitTab ? activeUnitTab.target : fileTitle(selected, programName)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Copy failed");
    }
  }

  function programBundleText(bundle: Pick<Files, "human" | "context" | "python">) {
    return [
      `--- ${fileTitle("human", programName)} ---`,
      bundle.human,
      `--- ${fileTitle("context", programName)} ---`,
      bundle.context,
      `--- ${fileTitle("python", programName)} ---`,
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
      const bundle = await getBundle(humanHash, programName);
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

  function phraseRangeAtPosition(text: string, phrase: string, pos: number) {
    return phraseRanges(text, phrase).find((range) => pos >= range.start && pos <= range.end);
  }

  function humanOriginRanges() {
    if (!modKeyDown || selected !== "human") return [];
    const seen = new Set<string>();
    const ranges: Array<{ from: number; to: number }> = [];
    for (const entry of activeProvenance) {
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

  function provenancePhraseMatches() {
    return activeProvenance.flatMap((entry) =>
      humanPhrasesFromSource(entry.source).map((phrase) => ({ phrase, line: Number(entry.line) }))
    );
  }

  function narrowestPhraseMatchesAt(pos: number) {
    return provenancePhraseMatches()
      .flatMap((match) => {
        if (!Number.isFinite(match.line)) return [];
        const range = phraseRangeAtPosition(drafts.human, match.phrase, pos);
        return range ? [{ ...match, range }] : [];
      })
      .sort(
        (a, b) =>
          a.range.end - a.range.start - (b.range.end - b.range.start) ||
          a.phrase.length - b.phrase.length ||
          a.range.start - b.range.start
      );
  }

  function lineSpan(text: string, lineNumber: number) {
    const lines = text.split("\n");
    let start = 0;
    for (let i = 0; i < lineNumber - 1 && i < lines.length; i += 1) start += lines[i].length + 1;
    return { start, end: start + (lines[lineNumber - 1]?.length ?? 0) };
  }

  function navigateToKind(kind: FileKind, lines: number[]) {
    setClosedKinds((current) => ({ ...current, [kind]: false }));
    setActivePlain(null);
    setActiveUnit(null);
    setSelected(kind);
    setHighlighted({ kind, lines });
    const span = lineSpan(drafts[kind], lines[0]);
    setEditorSelection(kind, { anchor: span.start, head: span.end });
  }

  function entryLines(entries: typeof files.pythonProvenance) {
    return Array.from(
      new Set(entries.map((entry) => Number(entry.line)).filter((line) => Number.isFinite(line)))
    ).sort((a, b) => a - b);
  }

  function entriesForPhrase(phrase: string) {
    const lower = phrase.toLowerCase();
    const cited = activeProvenance.filter((entry) =>
      humanPhrasesFromSource(entry.source).some((candidate) => candidate.toLowerCase() === lower)
    );
    const exact = cited.filter((entry) =>
      humanPhrasesFromSource(entry.source).every((candidate) => candidate.toLowerCase() === lower)
    );
    return exact.length ? exact : cited;
  }

  function linesForPhraseOccurrence(phrase: string, range: { start: number; end: number }) {
    const entries = entriesForPhrase(phrase);
    const lines = entryLines(entries);
    const occurrences = phraseRanges(drafts.human, phrase);
    if (lines.length < 2 || occurrences.length < 2) return lines;
    const occurrenceIndex = occurrences.findIndex(
      (candidate) => candidate.start === range.start && candidate.end === range.end
    );
    if (occurrenceIndex === -1) return lines;
    const lower = phrase.toLowerCase();
    const otherLines = new Set(
      activeProvenance
        .filter((entry) => {
          const phrases = humanPhrasesFromSource(entry.source);
          return phrases.length > 0 && !phrases.some((candidate) => candidate.toLowerCase() === lower);
        })
        .map((entry) => Number(entry.line))
        .filter((line) => Number.isFinite(line))
    );
    const runs: number[][] = [];
    let current: number[] = [];
    for (const line of lines) {
      const previous = current.length ? current[current.length - 1] : null;
      let separated = false;
      if (previous !== null) {
        for (let between = previous + 1; between < line; between += 1) {
          if (otherLines.has(between)) {
            separated = true;
            break;
          }
        }
      }
      if (separated) {
        runs.push(current);
        current = [line];
      } else {
        current.push(line);
      }
    }
    if (current.length) runs.push(current);
    if (runs.length !== occurrences.length) return lines;
    return runs[occurrenceIndex];
  }

  function handleHumanModClick(pos: number) {
    const clicked = narrowestPhraseMatchesAt(pos);
    if (!clicked.length) return;

    const phrase = clicked[0].phrase;
    const lines = linesForPhraseOccurrence(phrase, clicked[0].range);
    if (!lines.length) return;

    navigateToKind(provenanceKind, lines);
    setMessage(`Traced "${phrase}" to ${lines.length} ${provenanceLabel} line${lines.length === 1 ? "" : "s"}`);
  }

  function pythonEntriesForContextLine(line: number) {
    const phrases = new Set(
      files.contextProvenance
        .filter((entry) => Number(entry.line) === line)
        .flatMap((entry) => humanPhrasesFromSource(entry.source))
        .map((phrase) => phrase.toLowerCase())
    );
    if (!phrases.size) return [];
    return files.pythonProvenance.filter((entry) =>
      humanPhrasesFromSource(entry.source).some((phrase) => phrases.has(phrase.toLowerCase()))
    );
  }

  function pythonLinesForContextLine(line: number) {
    const entries = pythonEntriesForContextLine(line);
    const preferred = entries.filter((entry) => !entry.target || entry.target === `${programName}.py`);
    return entryLines(preferred.length ? preferred : entries);
  }

  function unitForContextLine(line: number) {
    const entries = pythonEntriesForContextLine(line);
    const unit = unitList.find((candidate) => entries.some((entry) => entry.target === candidate.target));
    if (!unit) return null;
    const lines = entryLines(entries.filter((entry) => entry.target === unit.target));
    return lines.length ? { unit, lines } : null;
  }

  function navigateToUnit(unit: CompiledUnit, lines: number[]) {
    setClosedUnits((current) => ({ ...current, [unit.target]: false }));
    setActivePlain(null);
    setActiveUnit(unit.target);
    setUnitHighlight({ target: unit.target, lines });
  }

  function handleHumanModContextMenu({ pos, line }: { pos: number; line: number }) {
    const clicked = narrowestPhraseMatchesAt(pos);
    const span = clicked.length
      ? { start: clicked[0].range.start, end: clicked[0].range.end }
      : lineSpan(drafts.human, line);
    const original = drafts.human.slice(span.start, span.end);
    if (!original) return;
    setRewordDraft({ start: span.start, end: span.end, original, text: original });
  }

  function confirmReword() {
    if (!rewordDraft) return;
    const target = rewordDraft;
    if (drafts.human.slice(target.start, target.end) !== target.original) {
      setRewordDraft(null);
      setError("The .human text changed under the reword editor; reopen it");
      return;
    }
    const updated = drafts.human.slice(0, target.start) + target.text + drafts.human.slice(target.end);
    setRewordDraft(null);
    setDraft("human", updated);
    run(
      "reword",
      async () => {
        try {
          return await reword(updated, programName);
        } catch (err) {
          const detail = err instanceof Error ? err.message : String(err);
          throw new Error(
            detail === "Not Found" || detail.startsWith("404")
              ? "Reword is not available yet: the backend /api/reword endpoint is missing"
              : detail
          );
        }
      },
      "Reworded .human; compiled output untouched"
    );
  }

  function linesForTarget(target: string, provenance = files.contextProvenance) {
    return provenance
      .filter((entry) => entry.target === target)
      .map((entry) => Number(entry.line))
      .filter((line) => Number.isFinite(line))
      .sort((a, b) => a - b);
  }

  function handleContextModClick(line: number) {
    if (unitList.length) {
      const linked = unitForContextLine(line);
      if (!linked) return;
      navigateToUnit(linked.unit, linked.lines);
      setMessage(
        `Traced .context line ${line} to ${linked.lines.length} ${linked.unit.target} line${linked.lines.length === 1 ? "" : "s"}`
      );
      return;
    }
    const lines = pythonLinesForContextLine(line);
    if (!lines.length) return;
    navigateToKind("python", lines);
    setMessage(`Traced .context line ${line} to ${lines.length} .py line${lines.length === 1 ? "" : "s"}`);
  }

  function contextOriginRanges() {
    if (!modKeyDown || selected !== "context") return [];
    const ranges: Array<{ from: number; to: number }> = [];
    const lineCount = drafts.context.split("\n").length;
    for (let line = 1; line <= lineCount; line += 1) {
      const linked = unitList.length ? unitForContextLine(line) !== null : pythonLinesForContextLine(line).length > 0;
      if (!linked) continue;
      const span = lineSpan(drafts.context, line);
      if (span.end > span.start) ranges.push({ from: span.start, to: span.end });
    }
    return ranges;
  }

  function contextModClickHandler() {
    if (selected === "human") return ({ pos }: { pos: number }) => handleHumanModClick(pos);
    if (selected === "context") return ({ line }: { pos: number; line: number }) => handleContextModClick(line);
    return undefined;
  }

  return (
    <main className="flex h-screen overflow-hidden bg-[#101317] font-sans text-[#E7EAF0]">
      <ExplorerSidebar
        refreshKey={treeVersion}
        projectName={activeProject?.name ?? null}
        activeFile={
          plainTab
            ? plainTab.name
            : activeUnitTab
              ? activeUnitTab.target
              : programLoaded
                ? fileTitle(selected, programName)
                : undefined
        }
        onOpenFile={openFile}
        onOpenCreatedFile={(node) => void openCreatedFile(node)}
        onRequestDelete={setFsDeleteTarget}
      >
        <div className="flex min-h-0 flex-1 flex-col border-t border-[#1F2328] p-3">
          <div className="mb-2 flex items-center justify-between px-1">
            <h2 className="truncate text-[11px] font-medium uppercase leading-3 tracking-[0.08em] text-[#737780]">
              History · {programName}
            </h2>
            <button
              type="button"
              title="Copy current program"
              disabled={disabled}
              className="font-mono text-[10px] text-[#5D626B] transition-colors enabled:hover:text-[#8A919E]"
              onClick={copyWorkspace}
            >
              copy program
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {files.tree.length === 0 ? (
              <p className="px-1 text-xs text-[#5D626B]">No snapshots yet.</p>
            ) : (
              <TreeView
                tree={files.tree}
                programName={programName}
                disabled={disabled}
                expanded={expandedFlows}
                onToggle={toggleFlow}
                onCopyFlow={copyFlow}
                onCheckout={(kind, hash, target) =>
                  run("checkout", () => checkout(kind, hash, programName), `Checked out ${kind}`, (nextFiles) => {
                    setHighlighted({
                      kind: "context",
                      lines: target ? linesForTarget(target, nextFiles.contextProvenance) : [],
                    });
                    focusUnits(nextFiles, target);
                  })
                }
              />
            )}
          </div>
        </div>
      </ExplorerSidebar>

      <section className="flex min-w-0 flex-1 flex-col p-3">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border-[0.8px] border-[#232830] bg-[#1A1F24] shadow-2xl">
          <div className="flex h-7 shrink-0 items-stretch border-b border-[#1F2328] bg-[#14181C]">
            {isKindVisible("human") ? (
              <EditorTab
                title={fileTitle("human", programName)}
                icon={fileGlyphs.human}
                active={!plainTab && !activeUnitTab && selected === "human"}
                dirty={humanDirty}
                onClick={() => {
                  setActivePlain(null);
                  setActiveUnit(null);
                  setSelected("human");
                }}
                onClose={() => closePipelineTab("human")}
              />
            ) : null}
            {isKindVisible("context") ? (
              <EditorTab
                title={fileTitle("context", programName)}
                icon={fileGlyphs.context}
                active={!plainTab && !activeUnitTab && selected === "context"}
                dirty={contextDirty}
                onClick={() => {
                  setActivePlain(null);
                  setActiveUnit(null);
                  setSelected("context");
                }}
                onClose={() => closePipelineTab("context")}
              />
            ) : null}
            {isKindVisible("python") ? (
              <EditorTab
                title={fileTitle("python", programName)}
                icon={fileGlyphs.python}
                active={!plainTab && !activeUnitTab && selected === "python"}
                dirty={pythonDirty}
                onClick={() => {
                  setActivePlain(null);
                  setActiveUnit(null);
                  setSelected("python");
                }}
                onClose={() => closePipelineTab("python")}
              />
            ) : null}
            {visibleUnits.map((unit) => (
              <EditorTab
                key={unit.target}
                title={unit.target}
                icon={plainTabIcon(unit.target)}
                active={!plainTab && activeUnitTab?.target === unit.target}
                dirty={false}
                onClick={() => {
                  setActivePlain(null);
                  setActiveUnit(unit.target);
                }}
                onClose={() => closeUnitTab(unit.target)}
              />
            ))}
            {plainTabs.map((tab) => (
              <EditorTab
                key={tab.path}
                title={tab.name}
                icon={plainTabIcon(tab.name)}
                active={activePlain === tab.path}
                dirty={tab.draft !== tab.saved}
                onClick={() => {
                  setActiveUnit(null);
                  setActivePlain(tab.path);
                }}
                onClose={() => closePlainTab(tab.path)}
              />
            ))}
            <div className="min-w-0 flex-1" />
            <div className="flex shrink-0 items-center gap-1.5 px-2">{fileActions()}</div>
          </div>

          <div className="relative min-h-0 flex-1 bg-[#101317]">
            {renderBody()}
            {!plainTab && !activeUnitTab && selected === "human" && rewordDraft ? (
              <div className="absolute left-1/2 top-8 z-20 w-[min(560px,90%)] -translate-x-1/2 rounded-xl border-[0.8px] border-[#232830] bg-[#15181C] p-4 shadow-2xl">
                <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#5D626B]">
                  reword phrase
                </p>
                <p className="mt-1 truncate font-mono text-xs text-[#5C6470]">was: {rewordDraft.original}</p>
                <input
                  autoFocus
                  value={rewordDraft.text}
                  onChange={(event) =>
                    setRewordDraft((current) => (current ? { ...current, text: event.target.value } : current))
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      confirmReword();
                    } else if (event.key === "Escape") {
                      event.preventDefault();
                      setRewordDraft(null);
                    }
                  }}
                  className="mt-3 w-full rounded-md border border-[#1F2328] bg-[#101317] px-3 py-2 font-mono text-sm text-[#E7EAF0] outline-none focus:border-[#4F46E5]"
                />
                <p className="mt-2 text-xs text-[#8A919E]">
                  Rebinds the same compiled .context/.py to this wording — nothing recompiles.
                </p>
                <div className="mt-3 flex justify-end gap-2">
                  <button
                    type="button"
                    className="rounded-md px-3 py-1.5 text-xs font-medium text-[#8A919E] transition-colors hover:bg-[#FFFFFF0A] hover:text-[#E7EAF0]"
                    onClick={() => setRewordDraft(null)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="rounded-md border-[0.8px] border-[#6366F180] bg-[#4F46E52E] px-3 py-1.5 text-xs font-semibold text-[#C7D2FE] transition-colors enabled:hover:bg-[#4F46E54D]"
                    disabled={disabled || !rewordDraft.text.trim() || rewordDraft.text === rewordDraft.original}
                    onClick={confirmReword}
                  >
                    Save wording
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="flex h-6 shrink-0 items-center gap-3 border-t border-[#1F2328] bg-[#14181C] px-3 font-mono text-[11px]">
            {error ? (
              <span className="truncate text-[#F87171]">{error}</span>
            ) : (
              <span className="truncate text-[#8A919E]">{message}</span>
            )}
            <span className="ml-auto flex shrink-0 items-center gap-2 text-[#5D626B]">
              {!plainTab && !activeUnitTab && selected === "context" && files.contextRole ? (
                <RoleBadge role={files.contextRole} />
              ) : null}
              <span>{hashShort(activeHash)}</span>
            </span>
          </div>
        </div>
      </section>

      {fsDeleteTarget ? (
        <ConfirmDeleteModal
          title={fsDeleteTarget.name}
          description={
            fsDeleteTarget.type === "dir"
              ? "This deletes the folder and everything inside it."
              : "This deletes the file from the project folder."
          }
          detail={fsDeleteTarget.path}
          disabled={disabled}
          onCancel={() => setFsDeleteTarget(null)}
          onConfirm={confirmFsDelete}
        />
      ) : null}
    </main>
  );

  function fileActions() {
    if (plainTab) {
      return <ActionIconButton text="copy" label="Copy file" disabled={disabled} onClick={copySelected} />;
    }

    if (activeUnitTab) {
      return (
        <ActionIconButton text="copy" label={`Copy ${activeUnitTab.target}`} disabled={disabled} onClick={copySelected} />
      );
    }

    if (!isKindVisible(selected)) return null;

    if (selected === "human") {
      return (
        <>
          <ActionIconButton text="copy" label="Copy .human" disabled={disabled} onClick={copySelected} />
          <ActionIconButton
            icon={<SparklesIcon width={12} height={12} />}
            label="Compile"
            primary
            disabled={disabled || !drafts.human.trim()}
            onClick={() =>
              run("compile", () => compile(drafts.human, false, programName), "Compiled", (nextFiles) => {
                if (focusUnits(nextFiles)) return;
                setSelected(nextFiles.status.hasPython ? "python" : "context");
              })
            }
          />
        </>
      );
    }

    if (selected === "context") {
      return (
        <>
          <ActionIconButton text="copy" label="Copy .context" disabled={disabled} onClick={copySelected} />
          <ActionIconButton
            icon={<SparklesIcon width={12} height={12} />}
            label="Compile"
            primary
            disabled={disabled || humanDirty || !drafts.context.trim()}
            onClick={() =>
              run(
                "context-to-python",
                () => contextToPython(drafts.context, false, programName),
                "Compiled",
                (nextFiles) => {
                  if (focusUnits(nextFiles)) return;
                  setSelected("python");
                }
              )
            }
          />
        </>
      );
    }

    return <ActionIconButton text="copy" label="Copy .py" disabled={disabled} onClick={copySelected} />;
  }

  function renderBody() {
    if (plainTab) {
      const tabPath = plainTab.path;
      return (
        <CodeEditor
          key={tabPath}
          value={plainTab.draft}
          mode="text"
          autoFocus
          onChange={(value) =>
            setPlainTabs((current) =>
              current.map((tab) => (tab.path === tabPath ? { ...tab, draft: value } : tab))
            )
          }
        />
      );
    }

    if (activeUnitTab) {
      const lines = unitHighlight?.target === activeUnitTab.target ? unitHighlight.lines : [];
      const span = lines.length ? lineSpan(activeUnitTab.python, lines[0]) : null;
      return (
        <CodeEditor
          key={activeUnitTab.target}
          value={activeUnitTab.python}
          mode="python"
          readOnly
          selection={span ? { anchor: span.start, head: span.end } : undefined}
          highlightedLines={lines}
        />
      );
    }

    if (!isKindVisible(selected)) {
      return (
        <div className="flex h-full items-center justify-center p-8">
          <p className="text-xs text-[#5D626B]">No editor open. Select a file in the explorer.</p>
        </div>
      );
    }

    if (selected === "context" && humanDirty) {
      return (
        <PendingPane
          title=".human has a draft change"
          body="Save / lookup the .human snapshot or compile it before viewing the context for that exact text."
          action="Save / lookup .human"
          disabled={disabled}
          onClick={() => run("save", () => saveFiles({ human: drafts.human }, programName), "Saved / looked up .human")}
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
              ? run("save", () => saveFiles({ human: drafts.human }, programName), "Saved / looked up .human")
              : run("save", () => saveFiles({ context: drafts.context }, programName), "Saved / looked up .context")
          }
        />
      );
    }

    if (selected === "context" && files.contextRole === "direct" && !selectedDirty) {
      return (
        <PendingPane
          title=".context was skipped for this snapshot"
          body="Compile decided this intent was trivial enough to compile .py directly from .human, so there is no intermediate context."
          action="Open .py"
          disabled={disabled}
          onClick={() => setSelected("python")}
        />
      );
    }

    if (selected === "context" && !files.status.hasContext && !selectedDirty) {
      return (
        <PendingPane
          title="No .context exists for this exact .human snapshot"
          body="Generate it once; leaf vs split is decided automatically. If you come back to this same .human later, the cached context will be reused."
          action="Generate Human → Context"
          disabled={disabled}
          onClick={() =>
            run(
              "human-to-context",
              () => humanToContext(drafts.human, false, programName),
              "Generated .context",
              () => setSelected("context")
            )
          }
        />
      );
    }

    if (selected === "python" && !files.status.hasPython && !selectedDirty) {
      return (
        <PendingPane
          title="No .py exists for this exact .context snapshot"
          body="Generate it once. If you return to this same context later, the cached Python will be reused."
          action={files.contextRole === "direct" ? "Compile .human → .py" : "Generate Context → Python"}
          disabled={disabled || !files.status.hasContext}
          onClick={() =>
            files.contextRole === "direct"
              ? run("compile", () => compile(drafts.human, false, programName), "Compiled .py", () =>
                  setSelected("python")
                )
              : run(
                  "context-to-python",
                  () => contextToPython(drafts.context, false, programName),
                  "Generated .py",
                  () => setSelected("python")
                )
          }
        />
      );
    }

    if (selectedDirty) {
      return (
        <DirtyEditor
          kind={selected}
          programName={programName}
          saved={files[selected]}
          draft={drafts[selected]}
          selection={selections[selected]}
          highlightedLines={selected === highlighted.kind ? highlighted.lines : []}
          highlightedRanges={selected === "human" ? humanOriginRanges() : selected === "context" ? contextOriginRanges() : []}
          onChange={(value) => setDraft(selected, value)}
          onSelectionChange={(selection) => setEditorSelection(selected, selection)}
          onModClick={contextModClickHandler()}
          onModContextMenu={selected === "human" ? handleHumanModContextMenu : undefined}
        />
      );
    }

    return (
      <CodeEditor
        value={drafts[selected]}
        mode={fileMeta[selected].mode}
        autoFocus
        selection={selections[selected]}
        highlightedLines={selected === highlighted.kind ? highlighted.lines : []}
        highlightedRanges={selected === "human" ? humanOriginRanges() : selected === "context" ? contextOriginRanges() : []}
        onChange={(value) => setDraft(selected, value)}
        onSelectionChange={(selection) => setEditorSelection(selected, selection)}
        onModClick={contextModClickHandler()}
        onModContextMenu={selected === "human" ? handleHumanModContextMenu : undefined}
      />
    );
  }
}

function EditorTab({
  title,
  icon: Icon,
  active,
  dirty,
  onClick,
  onClose,
}: {
  title: string;
  icon: (props: IconProps) => ReactElement;
  active: boolean;
  dirty: boolean;
  onClick: () => void;
  onClose: () => void;
}) {
  return (
    <div
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`group flex shrink-0 cursor-pointer items-center gap-1.5 border-r border-t-2 border-r-[#1F2328] border-t-transparent px-2.5 text-xs leading-4 ${
        active ? "bg-[#1A1F24] text-[#E6EDF3]" : "text-[#7D8590] transition-colors hover:text-[#BCC0C7]"
      }`}
    >
      <Icon width={13} height={13} className={`shrink-0 ${active ? "text-[#A5B4FC]" : "text-[#8A919E]"}`} />
      <span>{title}</span>
      <button
        type="button"
        aria-label={`Close ${title}`}
        title={`Close ${title}`}
        onClick={(event) => {
          event.stopPropagation();
          onClose();
        }}
        className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded transition-colors hover:bg-[#FFFFFF14]"
      >
        {dirty ? (
          <>
            <span className={`h-1.5 w-1.5 rounded-full group-hover:hidden ${active ? "bg-[#E6EDF3]" : "bg-[#7D8590]"}`} />
            <span className="hidden text-[9px] leading-3 text-[#E6EDF3] group-hover:block">✕</span>
          </>
        ) : (
          <span className={`text-[9px] leading-3 ${active ? "text-[#E6EDF3]" : "text-[#565E67]"}`}>✕</span>
        )}
      </button>
    </div>
  );
}

function RoleBadge({ role }: { role: ContextRole }) {
  return (
    <span
      className={`shrink-0 font-mono text-[9px] font-semibold uppercase tracking-[0.06em] ${
        role === "split" ? "text-amber-300/90" : role === "direct" ? "text-sky-300/90" : "text-emerald-300/90"
      }`}
    >
      {role}
    </span>
  );
}

function TreeView({
  tree,
  programName,
  disabled,
  expanded,
  onToggle,
  onCopyFlow,
  onCheckout,
}: {
  tree: TreeHuman[];
  programName: string;
  disabled: boolean;
  expanded: Record<string, boolean>;
  onToggle: (hash: string) => void;
  onCopyFlow: (humanHash: string) => void;
  onCheckout: (kind: FileKind, hash: string, target?: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      {tree.map((human) => {
        const contexts = human.contexts.length ? human.contexts : human.context ? [human.context] : [];
        const isExpanded = expanded[human.hash] ?? true;

        return (
          <div key={human.hash} className="flex flex-col gap-0.5">
            <div className="group flex items-start gap-2.5 px-1 py-[3px]">
              <button
                type="button"
                className="flex w-3.5 shrink-0 justify-center pt-0.5 text-[#9A9DA4] transition-colors hover:text-[#E7EAF0]"
                aria-label={isExpanded ? "Collapse flow" : "Expand flow"}
                title={isExpanded ? "Collapse flow" : "Expand flow"}
                onClick={() => onToggle(human.hash)}
              >
                {isExpanded ? <ChevronDownIcon width={12} height={12} /> : <ChevronRightIcon width={12} height={12} />}
              </button>
              <button
                type="button"
                disabled={disabled}
                title={human.preview}
                className="flex min-w-0 flex-1 items-baseline justify-between gap-2 text-left"
                onClick={() => onCheckout("human", human.hash)}
              >
                <span className={`truncate text-xs font-semibold ${human.active ? "text-[#C5CAFB]" : "text-[#EEEFF1]"}`}>
                  {fileTitle("human", programName)}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-[#5D626B]">{hashShort(human.hash)}</span>
              </button>
              <button
                type="button"
                disabled={disabled}
                title="Copy this flow"
                className="w-7 shrink-0 text-left font-mono text-[10px] text-[#5D626B] opacity-0 transition-opacity group-hover:opacity-100 enabled:hover:text-[#8A919E]"
                onClick={() => onCopyFlow(human.hash)}
              >
                copy
              </button>
            </div>

            {isExpanded ? (
              contexts.length ? (
                <div className="flex flex-col gap-0.5">
                  {contexts.map((context) => {
                    const pythons = context.pythons.length ? context.pythons : context.python ? [context.python] : [];

                    if (context.role === "direct") {
                      return (
                        <div key={context.hash} className="flex flex-col gap-0.5">
                          {pythons.length ? (
                            pythons.map((python) => (
                              <HistoryEntry
                                key={python.hash}
                                active={python.active}
                                label={fileTitle("python", programName)}
                                preview={python.preview}
                                hash={python.hash}
                                disabled={disabled}
                                badge={<RoleBadge role="direct" />}
                                onClick={() => onCheckout("python", python.hash)}
                              />
                            ))
                          ) : (
                            <MissingNode label=".py missing" />
                          )}
                        </div>
                      );
                    }

                    return (
                      <div key={context.hash} className="flex flex-col gap-0.5">
                        <HistoryEntry
                          active={context.active}
                          label={fileTitle("context", programName)}
                          preview={context.preview}
                          hash={context.hash}
                          disabled={disabled}
                          badge={<RoleBadge role={context.role} />}
                          onClick={() => onCheckout("context", context.hash)}
                        />
                        {pythons.length ? (
                          pythons.map((python) => (
                            <HistoryEntry
                              key={python.hash}
                              active={python.active}
                              label={
                                python.target
                                  ? `${fileTitle("python", programName)} · ${python.target}`
                                  : fileTitle("python", programName)
                              }
                              preview={python.preview}
                              hash={python.hash}
                              disabled={disabled}
                              onClick={() => onCheckout("python", python.hash, python.target ?? undefined)}
                            />
                          ))
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

function HistoryEntry({
  active,
  label,
  preview,
  hash,
  disabled,
  badge,
  onClick,
}: {
  active: boolean;
  label: string;
  preview: string;
  hash: string;
  disabled: boolean;
  badge?: ReactNode;
  onClick: () => void;
}) {
  return (
    <div className="flex items-center gap-2.5 py-0.5 pl-[18px] pr-1">
      <span className="flex w-3.5 shrink-0 justify-center">
        <span className={`h-1 w-1 rounded-full ${active ? "bg-[#818CF8]" : "bg-[#4A505A]"}`} />
      </span>
      <button
        type="button"
        disabled={disabled}
        title={preview}
        className="flex min-w-0 flex-1 items-baseline justify-between gap-2 text-left"
        onClick={onClick}
      >
        <span className="flex min-w-0 items-baseline gap-1.5">
          <span className={`truncate text-xs font-medium ${active ? "text-[#C5CAFB]" : "text-[#B9BDC4]"}`}>{label}</span>
          {badge}
        </span>
        <span className="shrink-0 font-mono text-[11px] text-[#5D626B]">{hashShort(hash)}</span>
      </button>
      <span className="w-7 shrink-0" />
    </div>
  );
}

function MissingNode({ label }: { label: string }) {
  return <div className="py-0.5 pl-[42px] font-mono text-[11px] text-[#5D626B]">{label}</div>;
}

function DirtyEditor({
  kind,
  programName,
  saved,
  draft,
  selection,
  highlightedLines,
  highlightedRanges,
  onChange,
  onSelectionChange,
  onModClick,
  onModContextMenu,
}: {
  kind: FileKind;
  programName: string;
  saved: string;
  draft: string;
  selection: CursorSelection;
  highlightedLines: number[];
  highlightedRanges: Array<{ from: number; to: number }>;
  onChange: (value: string) => void;
  onSelectionChange: (selection: CursorSelection) => void;
  onModClick?: (event: { pos: number; line: number; lineText: string }) => void;
  onModContextMenu?: (event: { pos: number; line: number; lineText: string }) => void;
}) {
  return (
    <div className="grid h-full grid-cols-1 grid-rows-2 xl:grid-cols-2 xl:grid-rows-1">
      <div className="flex min-h-0 flex-col">
        <PaneHeader label="draft" hint="editable; keep typing here" />
        <div className="min-h-0 flex-1">
          <CodeEditor
            value={draft}
            mode={fileMeta[kind].mode}
            autoFocus
            selection={selection}
            highlightedLines={highlightedLines}
            highlightedRanges={highlightedRanges}
            onChange={onChange}
            onSelectionChange={onSelectionChange}
            onModClick={onModClick}
            onModContextMenu={onModContextMenu}
          />
        </div>
      </div>
      <div className="flex min-h-0 flex-col border-t border-[#1F2328] xl:border-l xl:border-t-0">
        <PaneHeader label="changes" hint="diff against the saved snapshot" />
        <div className="min-h-0 flex-1">
          <DiffPreview
            filename={fileTitle(kind, programName)}
            before={saved}
            after={draft}
            language={kind === "python" ? "python" : undefined}
          />
        </div>
      </div>
    </div>
  );
}

function PaneHeader({ label, hint }: { label: string; hint: string }) {
  return (
    <div className="flex h-7 shrink-0 items-baseline gap-2 border-b border-[#1F2328] bg-[#14181C] px-3 pt-1.5">
      <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#8A919E]">{label}</span>
      <span className="truncate text-[10px] text-[#5D626B]">{hint}</span>
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
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h3 className="text-sm font-semibold text-[#E7EAF0]">{title}</h3>
        <p className="mt-2 text-xs leading-5 text-[#8A919E]">{body}</p>
        <button
          type="button"
          className="mt-5 rounded-md border-[0.8px] border-[#6366F180] bg-[#4F46E52E] px-3 py-1.5 text-xs font-medium text-[#C7D2FE] transition-colors enabled:hover:bg-[#4F46E54D]"
          disabled={disabled}
          onClick={onClick}
        >
          {action}
        </button>
      </div>
    </div>
  );
}

function hashShort(hash: string | null) {
  return hash ? hash.slice(0, 8) : "—";
}
