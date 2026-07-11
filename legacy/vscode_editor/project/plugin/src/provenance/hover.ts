import * as vscode from "vscode"
import { FranppState } from "../state"
import { classify } from "./locate"
import { defaultPythonTarget, entriesForContextLine, entriesForPythonLine, humanPhrasesFromSource } from "./phrases"

export class GeneratedLineHoverProvider implements vscode.HoverProvider {
  constructor(private readonly state: FranppState) {}

  provideHover(document: vscode.TextDocument, position: vscode.Position): vscode.Hover | undefined {
    const files = this.state.current()
    if (!files) return undefined
    const kind = classify(document, files)
    if (!kind || kind.kind === "human") return undefined
    const line = position.line + 1
    const entries =
      kind.kind === "context"
        ? entriesForContextLine(files.contextProvenance, line)
        : entriesForPythonLine(files.pythonProvenance, line, kind.target, defaultPythonTarget(files))
    if (!entries.length) return undefined
    const markdown = new vscode.MarkdownString()
    for (const entry of entries) {
      const phrases = humanPhrasesFromSource(entry.source)
      const origin = phrases.length ? phrases.map((phrase) => `\`${phrase}\``).join(", ") : entry.source
      markdown.appendMarkdown(`fran++: from human phrase ${origin} — *${entry.status}*\n\n`)
    }
    return new vscode.Hover(markdown, document.lineAt(position.line).range)
  }
}
