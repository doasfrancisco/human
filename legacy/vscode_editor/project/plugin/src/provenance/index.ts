import * as vscode from "vscode"
import { FranppState } from "../state"
import { ProvenanceDecorator } from "./decorations"
import { PhraseDefinitionProvider } from "./definition"
import { GeneratedLineHoverProvider } from "./hover"
import { classify } from "./locate"

export function registerProvenance(context: vscode.ExtensionContext, state: FranppState): void {
  const decorator = new ProvenanceDecorator(state)

  context.subscriptions.push(
    decorator,
    vscode.window.onDidChangeTextEditorSelection((event) => {
      if (event.textEditor === vscode.window.activeTextEditor) decorator.refresh()
    }),
    vscode.window.onDidChangeVisibleTextEditors(() => decorator.refresh()),
    vscode.window.onDidChangeActiveTextEditor(() => decorator.refresh()),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (classify(event.document, state.current())) decorator.refresh()
    }),
    state.onDidChange(() => decorator.refresh()),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("franpp.provenanceEnabled")) decorator.refresh()
    }),
    vscode.commands.registerCommand("franpp.toggleProvenance", async () => {
      const configuration = vscode.workspace.getConfiguration("franpp")
      const next = !configuration.get<boolean>("provenanceEnabled", true)
      const target = vscode.workspace.workspaceFolders?.length
        ? vscode.ConfigurationTarget.Workspace
        : vscode.ConfigurationTarget.Global
      await configuration.update("provenanceEnabled", next, target)
      decorator.refresh()
      vscode.window.showInformationMessage(
        next ? "fran++: provenance highlighting enabled" : "fran++: provenance highlighting disabled"
      )
    }),
    vscode.languages.registerDefinitionProvider(
      { scheme: "file", language: "human" },
      new PhraseDefinitionProvider(state, decorator)
    ),
    vscode.languages.registerHoverProvider(
      [
        { scheme: "file", pattern: "**/*.py" },
        { scheme: "file", pattern: "**/*.context" },
      ],
      new GeneratedLineHoverProvider(state)
    )
  )
}
