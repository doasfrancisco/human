"use client";

import { useEffect, useMemo, useRef } from "react";
import { basicSetup } from "codemirror";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { Compartment, EditorSelection, EditorState, Extension, RangeSetBuilder, StateEffect, StateField } from "@codemirror/state";
import { Decoration, DecorationSet, EditorView } from "@codemirror/view";
import { python } from "@codemirror/lang-python";
import { tags } from "@lezer/highlight";

const editorTheme = EditorView.theme({
  "&": {
    height: "100%",
    fontSize: "13px",
    backgroundColor: "#101317",
    color: "#E7EAF0",
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
    backgroundColor: "#101317",
    color: "#71717A",
    borderRight: "1px solid #1F2328",
  },
  ".cm-activeLine": {
    backgroundColor: "#1A1F24",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "#1A1F24",
  },
  ".cm-cursor": {
    borderLeftColor: "#A5B4FC",
    borderLeftWidth: "2px",
  },
  ".cm-focused .cm-cursor": {
    borderLeftColor: "#A5B4FC",
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
  ".cm-originRangeHover": {
    backgroundColor: "rgba(129, 140, 248, 0.5)",
    outline: "1px solid rgba(199, 210, 254, 0.95)",
    textDecoration: "underline",
    cursor: "pointer",
  },
  "&.cm-focused": {
    outline: "none",
  },
});

const readOnlyTheme = EditorView.theme({
  "&": {
    backgroundColor: "#14181C",
  },
});

const brightHighlightStyle = HighlightStyle.define([
  { tag: tags.keyword, color: "#FABD2F", fontWeight: "500" },
  { tag: [tags.string, tags.special(tags.string), tags.regexp, tags.character], color: "#B8BB26" },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: "#7FD1E8" },
  { tag: [tags.number, tags.integer, tags.float], color: "#C4A7E7" },
  { tag: [tags.bool, tags.null, tags.atom], color: "#D3869B" },
  { tag: tags.comment, color: "#8A9A7B", fontStyle: "italic" },
  { tag: [tags.className, tags.typeName, tags.namespace], color: "#8EC07C" },
  { tag: [tags.definition(tags.variableName), tags.definition(tags.propertyName)], color: "#E7EAF0" },
  { tag: tags.propertyName, color: "#9CC9E8" },
  { tag: [tags.operator, tags.compareOperator, tags.logicOperator, tags.arithmeticOperator], color: "#FE8019" },
  { tag: [tags.punctuation, tags.bracket, tags.separator], color: "#B0A8A0" },
  { tag: tags.self, color: "#E5C07B", fontStyle: "italic" },
  { tag: [tags.meta, tags.annotation, tags.processingInstruction], color: "#B48EAD" },
  { tag: tags.variableName, color: "#E7EAF0" },
  { tag: tags.labelName, color: "#7FD1E8" },
  { tag: tags.escape, color: "#FE8019" },
  { tag: tags.invalid, color: "#FB4934" },
  { tag: tags.heading, color: "#FABD2F", fontWeight: "600" },
  { tag: tags.link, color: "#7FD1E8", textDecoration: "underline" },
]);

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
  onModContextMenu?: (event: ModClickEvent) => void;
  highlightedLines?: number[];
  highlightedRanges?: HighlightedRange[];
};

const setHoveredRange = StateEffect.define<HighlightedRange | null>();

function clampRange(range: HighlightedRange, length: number): HighlightedRange {
  return {
    from: Math.max(0, Math.min(range.from, length)),
    to: Math.max(0, Math.min(range.to, length)),
  };
}

function narrowestRangeAt(ranges: HighlightedRange[], pos: number): HighlightedRange | null {
  return (
    ranges
      .filter((range) => pos >= range.from && pos <= range.to)
      .sort((a, b) => a.to - a.from - (b.to - b.from) || a.from - b.from)[0] ?? null
  );
}

function rangeHighlightExtension(ranges: HighlightedRange[]): Extension {
  function build(state: EditorState, hovered: HighlightedRange | null): DecorationSet {
    const length = state.doc.length;
    const marks = ranges
      .map((range) => clampRange(range, length))
      .filter((range) => range.to > range.from)
      .map((range) => Decoration.mark({ class: "cm-originRange" }).range(range.from, range.to));
    if (hovered) {
      const range = clampRange(hovered, length);
      if (range.to > range.from) {
        marks.push(Decoration.mark({ class: "cm-originRangeHover" }).range(range.from, range.to));
      }
    }
    return Decoration.set(marks, true);
  }

  return StateField.define<{ hovered: HighlightedRange | null; decorations: DecorationSet }>({
    create: (state) => ({ hovered: null, decorations: build(state, null) }),
    update(value, transaction) {
      let hovered = value.hovered;
      let changed = transaction.docChanged;
      for (const effect of transaction.effects) {
        if (effect.is(setHoveredRange)) {
          hovered = effect.value;
          changed = true;
        }
      }
      if (!changed) return value;
      return { hovered, decorations: build(transaction.state, hovered) };
    },
    provide: (field) => EditorView.decorations.from(field, (value) => value.decorations),
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
  onModContextMenu,
  highlightedLines = [],
  highlightedRanges = [],
}: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  const onSelectionChangeRef = useRef(onSelectionChange);
  const onModClickRef = useRef(onModClick);
  const onModContextMenuRef = useRef(onModContextMenu);
  const suppressChangeRef = useRef(false);
  const highlightedRangesRef = useRef(highlightedRanges);
  const hoveredRangeKeyRef = useRef("");
  const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
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
    onModContextMenuRef.current = onModContextMenu;
  }, [onModContextMenu]);

  useEffect(() => {
    if (!hostRef.current) return;

    const extensions = [
      basicSetup,
      editorTheme,
      syntaxHighlighting(brightHighlightStyle),
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
        contextmenu(event, view) {
          if (!onModContextMenuRef.current || (!event.ctrlKey && !event.metaKey)) return false;
          const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
          if (pos === null) return false;
          const line = view.state.doc.lineAt(pos);
          event.preventDefault();
          onModContextMenuRef.current({ pos, line: line.number, lineText: line.text });
          return true;
        },
        mousemove(event, view) {
          lastPointerRef.current = { x: event.clientX, y: event.clientY };
          const ranges = highlightedRangesRef.current;
          let hovered: HighlightedRange | null = null;
          if ((event.ctrlKey || event.metaKey) && ranges.length) {
            const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
            if (pos !== null) hovered = narrowestRangeAt(ranges, pos);
          }
          const key = hovered ? `${hovered.from}:${hovered.to}` : "";
          if (key === hoveredRangeKeyRef.current) return false;
          hoveredRangeKeyRef.current = key;
          view.dispatch({ effects: setHoveredRange.of(hovered) });
          return false;
        },
        mouseleave(event, view) {
          lastPointerRef.current = null;
          if (!hoveredRangeKeyRef.current) return false;
          hoveredRangeKeyRef.current = "";
          view.dispatch({ effects: setHoveredRange.of(null) });
          return false;
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
    highlightedRangesRef.current = highlightedRanges;
    hoveredRangeKeyRef.current = "";
    const view = viewRef.current;
    if (!view) return;

    view.dispatch({
      effects: compartmentsRef.current.ranges.reconfigure(
        highlightedRanges.length ? rangeHighlightExtension(highlightedRanges) : []
      ),
    });

    const pointer = lastPointerRef.current;
    if (!highlightedRanges.length || !pointer) return;
    const pos = view.posAtCoords(pointer);
    if (pos === null) return;
    const hovered = narrowestRangeAt(highlightedRanges, pos);
    if (!hovered) return;
    hoveredRangeKeyRef.current = `${hovered.from}:${hovered.to}`;
    view.dispatch({ effects: setHoveredRange.of(hovered) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeHighlightKey]);

  return <div ref={hostRef} className="h-full overflow-hidden" />;
}
