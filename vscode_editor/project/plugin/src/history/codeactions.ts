import * as vscode from "vscode"
import { FranppState } from "../state"
import { tracedPhraseRangeAt } from "../provenance/locate"

export class RewordCodeActionProvider implements vscode.CodeActionProvider {
  static readonly metadata: vscode.CodeActionProviderMetadata = {
    providedCodeActionKinds: [vscode.CodeActionKind.Refactor],
  }

  constructor(private readonly state: FranppState) {}

  provideCodeActions(document: vscode.TextDocument, range: vscode.Range | vscode.Selection): vscode.CodeAction[] {
    const editor = vscode.window.activeTextEditor
    if (!editor || editor.document !== document) {
      return []
    }
    if (range.isEmpty && !tracedPhraseRangeAt(editor, this.state.current())) {
      return []
    }
    const action = new vscode.CodeAction("Reword this phrase (keep compiled output)", vscode.CodeActionKind.Refactor)
    action.command = { command: "franpp.rewordPhrase", title: "Reword Phrase (keep compiled output)" }
    return [action]
  }
}
