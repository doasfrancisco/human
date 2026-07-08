"use client";

import { useEffect, useMemo, useRef } from "react";
import { basicSetup } from "codemirror";
import { Compartment, EditorSelection, EditorState, Extension, RangeSetBuilder, StateField } from "@codemirror/state";
import { Decoration, DecorationSet, EditorView } from "@codemirror/view";
import { python } from "@codemirror/lang-python";

const editorTheme = EditorView.theme({
  "&": {
    height: "100%",
    fontSize: "13px",
    backgroundColor: "#09090b",
    color: "#f4f4f5",
  },
  ".cm-scroller": {
    fontFamily:
      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
  },
  ".cm-content": {
    padding: "14px 0",
  },
  ".cm-line": {
    padding: "0 14px",
  },
  ".cm-gutters": {
    backgroundColor: "#09090b",
    color: "#71717a",
    borderRight: "1px solid #27272a",
  },
  ".cm-activeLine": {
    backgroundColor: "#18181b",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "#18181b",
  },
  ".cm-cursor": {
    borderLeftColor: "#fbbf24",
    borderLeftWidth: "2px",
  },
  ".cm-focused .cm-cursor": {
    borderLeftColor: "#fbbf24",
  },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
    backgroundColor: "rgba(99, 102, 241, 0.35)",
  },
  ".cm-matchingBracket, .cm-nonmatchingBracket": {
    backgroundColor: "rgba(251, 191, 36, 0.2)",
    outline: "1px solid rgba(251, 191, 36, 0.45)",
  },
  ".cm-diffLine": {
    backgroundColor: "rgba(234, 179, 8, 0.16)",
  },
  ".cm-originRange": {
    backgroundColor: "rgba(99, 102, 241, 0.28)",
    outline: "1px solid rgba(165, 180, 252, 0.65)",
    borderRadius: "3px",
    cursor: "pointer",
  },
  "&.cm-focused": {
    outline: "none",
  },
});

const readOnlyTheme = EditorView.theme({
  "&": {
    backgroundColor: "#0f0f12",
  },
});

type CursorSelection = {
  anchor: number;
  head: number;
};

type ModClickEvent = {
  pos: number;
  line: number;
  lineText: string;
};

type HighlightedRange = {
  from: number;
  to: number;
};

type CodeEditorProps = {
  value: string;
  mode?: "text" | "python";
  readOnly?: boolean;
  autoFocus?: boolean;
  selection?: CursorSelection;
  onChange?: (value: string) => void;
  onSelectionChange?: (selection: CursorSelection) => void;
  onModClick?: (event: ModClickEvent) => void;
  highlightedLines?: number[];
  highlightedRanges?: HighlightedRange[];
};

function rangeHighlightExtension(ranges: HighlightedRange[]): Extension {
  function build(state: EditorState): DecorationSet {
    const builder = new RangeSetBuilder<Decoration>();
    const length = state.doc.length;
    const sorted = [...ranges]
      .map((range) => ({ from: Math.max(0, Math.min(range.from, length)), to: Math.max(0, Math.min(range.to, length)) }))
      .filter((range) => range.to > range.from)
      .sort((a, b) => a.from - b.from || a.to - b.to);

    let lastTo = -1;
    for (const range of sorted) {
      if (range.from < lastTo) continue;
      builder.add(range.from, range.to, Decoration.mark({ class: "cm-originRange" }));
      lastTo = range.to;
    }
    return builder.finish();
  }

  return StateField.define<DecorationSet>({
    create: build,
    update(value, transaction) {
      if (transaction.docChanged) return build(transaction.state);
      return value;
    },
    provide: (field) => EditorView.decorations.from(field),
  });
}

function lineHighlightExtension(lines: number[]): Extension {
  const lineSet = new Set(lines);

  function build(state: EditorState): DecorationSet {
    const builder = new RangeSetBuilder<Decoration>();
    for (let lineNumber = 1; lineNumber <= state.doc.lines; lineNumber += 1) {
      if (!lineSet.has(lineNumber)) continue;
      const line = state.doc.line(lineNumber);
      builder.add(line.from, line.from, Decoration.line({ class: "cm-diffLine" }));
    }
    return builder.finish();
  }

  return StateField.define<DecorationSet>({
    create: build,
    update(value, transaction) {
      if (transaction.docChanged) return build(transaction.state);
      return value;
    },
    provide: (field) => EditorView.decorations.from(field),
  });
}

function clampSelection(selection: CursorSelection | undefined, length: number) {
  if (!selection) return undefined;
  return {
    anchor: Math.max(0, Math.min(selection.anchor, length)),
    head: Math.max(0, Math.min(selection.head, length)),
  };
}

function toEditorSelection(selection: CursorSelection | undefined, length: number) {
  const clamped = clampSelection(selection, length);
  if (!clamped) return undefined;
  return EditorSelection.create([EditorSelection.range(clamped.anchor, clamped.head)], 0);
}

export function CodeEditor({
  value,
  mode = "text",
  readOnly = false,
  autoFocus = false,
  selection,
  onChange,
  onSelectionChange,
  onModClick,
  highlightedLines = [],
  highlightedRanges = [],
}: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  const onSelectionChangeRef = useRef(onSelectionChange);
  const onModClickRef = useRef(onModClick);
  const suppressChangeRef = useRef(false);
  const compartmentsRef = useRef({ lines: new Compartment(), ranges: new Compartment() });
  const highlightKey = useMemo(() => highlightedLines.join(","), [highlightedLines]);
  const rangeHighlightKey = useMemo(
    () => highlightedRanges.map((range) => `${range.from}:${range.to}`).join(","),
    [highlightedRanges]
  );

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    onSelectionChangeRef.current = onSelectionChange;
  }, [onSelectionChange]);

  useEffect(() => {
    onModClickRef.current = onModClick;
  }, [onModClick]);

  useEffect(() => {
    if (!hostRef.current) return;

    const extensions = [
      basicSetup,
      editorTheme,
      readOnly ? readOnlyTheme : [],
      compartmentsRef.current.lines.of(highlightedLines.length ? lineHighlightExtension(highlightedLines) : []),
      compartmentsRef.current.ranges.of(highlightedRanges.length ? rangeHighlightExtension(highlightedRanges) : []),
      EditorState.readOnly.of(readOnly),
      EditorView.lineWrapping,
      EditorView.domEventHandlers({
        click(event, view) {
          if (!onModClickRef.current || (!event.ctrlKey && !event.metaKey)) return false;
          const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
          if (pos === null) return false;
          const line = view.state.doc.lineAt(pos);
          event.preventDefault();
          onModClickRef.current({ pos, line: line.number, lineText: line.text });
          return true;
        },
      }),
      EditorView.updateListener.of((update) => {
        if ((update.docChanged || update.selectionSet) && !suppressChangeRef.current) {
          const cursor = update.state.selection.main;
          onSelectionChangeRef.current?.({ anchor: cursor.anchor, head: cursor.head });
        }
        if (!update.docChanged || suppressChangeRef.current) return;
        onChangeRef.current?.(update.state.doc.toString());
      }),
    ];

    if (mode === "python") {
      extensions.push(python());
    }

    const view = new EditorView({
      parent: hostRef.current,
      state: EditorState.create({
        doc: value,
        selection: toEditorSelection(selection, value.length),
        extensions,
      }),
    });

    viewRef.current = view;
    if (autoFocus) view.focus();

    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, readOnly]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;

    const current = view.state.doc.toString();
    if (current === value) return;

    const nextSelection = toEditorSelection(
      { anchor: view.state.selection.main.anchor, head: view.state.selection.main.head },
      value.length
    );

    suppressChangeRef.current = true;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: value },
      selection: nextSelection,
    });
    suppressChangeRef.current = false;
  }, [value]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view || !selection || view.hasFocus) return;

    const nextSelection = toEditorSelection(selection, view.state.doc.length);
    if (!nextSelection) return;

    const current = view.state.selection.main;
    const next = nextSelection.main;
    if (current.anchor === next.anchor && current.head === next.head) return;

    view.dispatch({ selection: nextSelection, scrollIntoView: true });
    // Only cursor endpoints matter here; depending on the object causes noisy remount updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.anchor, selection?.head]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;

    view.dispatch({
      effects: compartmentsRef.current.lines.reconfigure(
        highlightedLines.length ? lineHighlightExtension(highlightedLines) : []
      ),
    });

    if (!highlightedLines.length) return;
    const firstLine = Math.min(...highlightedLines);
    if (firstLine >= 1 && firstLine <= view.state.doc.lines) {
      view.dispatch({
        effects: EditorView.scrollIntoView(view.state.doc.line(firstLine).from, { y: "center" }),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightKey]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;

    view.dispatch({
      effects: compartmentsRef.current.ranges.reconfigure(
        highlightedRanges.length ? rangeHighlightExtension(highlightedRanges) : []
      ),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeHighlightKey]);

  return <div ref={hostRef} className="h-full overflow-hidden" />;
}
