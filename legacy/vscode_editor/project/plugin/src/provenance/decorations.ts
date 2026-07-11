import * as vscode from "vscode"
import { FilesResponse } from "../api"
import { FranppState } from "../state"
import { classify, DocKind } from "./locate"
import {
  defaultPythonTarget,
  entriesForContextLine,
  entriesForPythonLine,
  humanPhrasesFromSource,
  lineMatchesForPhrase,
  linesForPhrase,
  narrowestPhraseMatchesAt,
  originRangesForPhrases,
  phraseRanges,
  PhraseRange,
} from "./phrases"

export class ProvenanceDecorator implements vscode.Disposable {
  private readonly lineType = vscode.window.createTextEditorDecorationType({
    isWholeLine: true,
    backgroundColor: new vscode.ThemeColor("editor.wordHighlightBackground"),
    overviewRulerColor: new vscode.ThemeColor("editorOverviewRuler.wordHighlightForeground"),
    overviewRulerLane: vscode.OverviewRulerLane.Center,
  })

  private readonly phraseType = vscode.window.createTextEditorDecorationType({
    backgroundColor: new vscode.ThemeColor("editor.selectionHighlightBackground"),
    border: "1px solid",
    borderColor: new vscode.ThemeColor("editor.selectionHighlightBorder"),
    overviewRulerColor: new vscode.ThemeColor("editorOverviewRuler.selectionHighlightForeground"),
    overviewRulerLane: vscode.OverviewRulerLane.Center,
  })

  constructor(private readonly state: FranppState) {}

  enabled(): boolean {
    return vscode.workspace.getConfiguration("franpp").get<boolean>("provenanceEnabled", true)
  }

  refresh(): void {
    this.clearAll()
    if (!this.enabled()) return
    const files = this.state.current()
    const editor = vscode.window.activeTextEditor
    if (!files || !editor) return
    const kind = classify(editor.document, files)
    if (!kind || this.isStale(editor.document, kind, files)) return
    if (kind.kind === "human") this.highlightFromHuman(editor, files)
    else this.highlightFromGenerated(editor, kind, files)
  }

  previewPhrase(phrase: string): void {
    if (!this.enabled()) return
    const files = this.state.current()
    if (!files) return
    this.clearAll()
    this.paintPhrase(files, phrase)
  }

  clearAll(): void {
    for (const editor of vscode.window.visibleTextEditors) {
      editor.setDecorations(this.lineType, [])
      editor.setDecorations(this.phraseType, [])
    }
  }

  dispose(): void {
    this.lineType.dispose()
    this.phraseType.dispose()
  }

  private isStale(document: vscode.TextDocument, kind: DocKind, files: FilesResponse): boolean {
    const reference =
      kind.kind === "human"
        ? files.human
        : kind.kind === "context"
          ? files.context
          : kind.target === defaultPythonTarget(files)
            ? files.python
            : undefined
    if (reference === undefined) return false
    return document.getText().replace(/\r\n/g, "\n").trimEnd() !== reference.replace(/\r\n/g, "\n").trimEnd()
  }

  private highlightFromHuman(editor: vscode.TextEditor, files: FilesResponse): void {
    const text = editor.document.getText()
    const pos = editor.document.offsetAt(editor.selection.active)
    const matches = narrowestPhraseMatchesAt(text, [...files.contextProvenance, ...files.pythonProvenance], pos)
    if (!matches.length) return
    this.paintPhrase(files, matches[0].phrase)
  }

  private paintPhrase(files: FilesResponse, phrase: string): void {
    const contextLines = linesForPhrase(files.contextProvenance, phrase)
    const pythonMatches = lineMatchesForPhrase(files.pythonProvenance, phrase)
    for (const target of vscode.window.visibleTextEditors) {
      const kind = classify(target.document, files)
      if (!kind || this.isStale(target.document, kind, files)) continue
      if (kind.kind === "human") {
        target.setDecorations(
          this.phraseType,
          phraseRanges(target.document.getText(), phrase).map((range) => this.toRange(target.document, range))
        )
      } else if (kind.kind === "context") {
        target.setDecorations(this.lineType, this.lineRanges(target.document, contextLines))
      } else {
        const lines = pythonMatches
          .filter((match) => (match.target ?? defaultPythonTarget(files)) === kind.target)
          .map((match) => match.line)
        target.setDecorations(this.lineType, this.lineRanges(target.document, lines))
      }
    }
  }

  private highlightFromGenerated(editor: vscode.TextEditor, kind: DocKind, files: FilesResponse): void {
    const line = editor.selection.active.line + 1
    const entries =
      kind.kind === "context"
        ? entriesForContextLine(files.contextProvenance, line)
        : kind.kind === "python"
          ? entriesForPythonLine(files.pythonProvenance, line, kind.target, defaultPythonTarget(files))
          : []
    if (!entries.length) return
    const phrases = entries.flatMap((entry) => humanPhrasesFromSource(entry.source))
    if (!phrases.length) return
    editor.setDecorations(this.lineType, this.lineRanges(editor.document, [line]))
    for (const target of vscode.window.visibleTextEditors) {
      const targetKind = classify(target.document, files)
      if (targetKind?.kind !== "human" || this.isStale(target.document, targetKind, files)) continue
      const ranges = originRangesForPhrases(target.document.getText(), phrases)
      target.setDecorations(
        this.phraseType,
        ranges.map((range) => this.toRange(target.document, range))
      )
    }
  }

  private toRange(document: vscode.TextDocument, range: PhraseRange): vscode.Range {
    return new vscode.Range(document.positionAt(range.start), document.positionAt(range.end))
  }

  private lineRanges(document: vscode.TextDocument, lines: number[]): vscode.Range[] {
    return lines
      .filter((line) => line >= 1 && line <= document.lineCount)
      .map((line) => document.lineAt(line - 1).range)
  }
}
