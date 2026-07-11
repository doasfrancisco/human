import * as vscode from "vscode"
import { FranppState } from "../state"
import { ProvenanceDecorator } from "./decorations"
import { classify, resolveContextUri, resolvePythonUri } from "./locate"
import { defaultPythonTarget, lineMatchesForPhrase, linesForPhrase, narrowestPhraseMatchesAt } from "./phrases"

export class PhraseDefinitionProvider implements vscode.DefinitionProvider {
  constructor(
    private readonly state: FranppState,
    private readonly decorator: ProvenanceDecorator
  ) {}

  async provideDefinition(
    document: vscode.TextDocument,
    position: vscode.Position
  ): Promise<vscode.LocationLink[] | undefined> {
    const files = this.state.current()
    if (!files) return undefined
    if (classify(document, files)?.kind !== "human") return undefined
    const pos = document.offsetAt(position)
    const matches = narrowestPhraseMatchesAt(
      document.getText(),
      [...files.contextProvenance, ...files.pythonProvenance],
      pos
    )
    if (!matches.length) return undefined

    const phrase = matches[0].phrase
    const origin = new vscode.Range(
      document.positionAt(matches[0].range.start),
      document.positionAt(matches[0].range.end)
    )
    this.decorator.previewPhrase(phrase)

    const pythonMatches = lineMatchesForPhrase(files.pythonProvenance, phrase)
      .filter((match) => Number.isFinite(match.line))
      .sort((a, b) => a.line - b.line)
    for (const match of pythonMatches) {
      const uri = await resolvePythonUri(match.target ?? defaultPythonTarget(files), files)
      if (!uri) continue
      const link = await this.toLink(uri, match.line, origin)
      if (link) return [link]
    }

    const contextUri = await resolveContextUri(files)
    if (!contextUri) return undefined
    for (const line of linesForPhrase(files.contextProvenance, phrase)) {
      const link = await this.toLink(contextUri, line, origin)
      if (link) return [link]
    }
    return undefined
  }

  private async toLink(
    uri: vscode.Uri,
    line: number,
    origin: vscode.Range
  ): Promise<vscode.LocationLink | undefined> {
    let target: vscode.Range
    try {
      const document = await vscode.workspace.openTextDocument(uri)
      if (!Number.isFinite(line) || line < 1 || line > document.lineCount) return undefined
      target = document.lineAt(line - 1).range
    } catch {
      return undefined
    }
    return { originSelectionRange: origin, targetUri: uri, targetRange: target, targetSelectionRange: target }
  }
}
