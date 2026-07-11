import * as vscode from "vscode"
import { FilesResponse, FranppApi } from "./api"
import { FranppState } from "./state"
import { registerProvenance } from "./provenance"
import { tracedPhraseRangeAt } from "./provenance/locate"
import { registerHistory } from "./history"
import { registerDiff } from "./diff"

function activeHumanEditor(): vscode.TextEditor | undefined {
  const editor = vscode.window.activeTextEditor
  if (!editor || !editor.document.fileName.endsWith(".human")) {
    return undefined
  }
  return editor
}

function humanNameOf(document: vscode.TextDocument): string {
  const base = document.uri.path.split("/").pop() ?? ""
  return base.endsWith(".human") ? base.slice(0, -".human".length) : base
}

async function runStage(state: FranppState, title: string, task: () => Promise<FilesResponse>): Promise<void> {
  try {
    const result = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title },
      () => task()
    )
    state.update(result)
  } catch (error) {
    vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error))
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const api = new FranppApi()
  const state = new FranppState()
  context.subscriptions.push(state)

  registerProvenance(context, state)
  registerHistory(context, api, state)
  registerDiff(context, api, state)

  const syncActiveProgram = async () => {
    const editor = activeHumanEditor()
    if (!editor) {
      return
    }
    const name = humanNameOf(editor.document)
    if (state.current()?.name === name) {
      return
    }
    try {
      state.update(await api.files(name))
    } catch {
      return
    }
  }
  context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(() => void syncActiveProgram()))
  void syncActiveProgram()

  context.subscriptions.push(
    vscode.commands.registerCommand("franpp.compile", async () => {
      const editor = activeHumanEditor()
      if (!editor) {
        vscode.window.showErrorMessage("fran++: open a .human file first")
        return
      }
      const human = editor.document.getText()
      const name = humanNameOf(editor.document)
      await runStage(state, `fran++: compiling ${name}.human`, () => api.compile(human, name))
    }),
    vscode.commands.registerCommand("franpp.generateContext", async () => {
      const editor = activeHumanEditor()
      if (!editor) {
        vscode.window.showErrorMessage("fran++: open a .human file first")
        return
      }
      const human = editor.document.getText()
      const name = humanNameOf(editor.document)
      await runStage(state, `fran++: generating ${name}.context`, () => api.humanToContext(human, name))
    }),
    vscode.commands.registerCommand("franpp.reword", async () => {
      const editor = activeHumanEditor()
      if (!editor) {
        vscode.window.showErrorMessage("fran++: open a .human file first")
        return
      }
      const human = editor.document.getText()
      const name = humanNameOf(editor.document)
      const reworded = await vscode.window.showInputBox({
        prompt: "New wording for the file (compiled output is kept)",
        value: human,
      })
      if (reworded === undefined) {
        return
      }
      await runStage(state, "fran++: rewording", () => api.reword(reworded, name))
    }),
    vscode.commands.registerCommand("franpp.rewordPhrase", async () => {
      const editor = activeHumanEditor()
      if (!editor) {
        vscode.window.showErrorMessage("fran++: open a .human file first")
        return
      }
      const range = tracedPhraseRangeAt(editor, state.current())
      if (!range) {
        vscode.window.showErrorMessage("fran++: place the cursor inside a traced phrase, or select the text to reword")
        return
      }
      const current = editor.document.getText(range)
      const reworded = await vscode.window.showInputBox({
        prompt: "New wording for this phrase (compiled output is kept)",
        value: current,
      })
      if (reworded === undefined || reworded === current) {
        return
      }
      const edit = new vscode.WorkspaceEdit()
      edit.replace(editor.document.uri, range, reworded)
      if (!(await vscode.workspace.applyEdit(edit))) {
        vscode.window.showErrorMessage("fran++: could not rewrite the phrase")
        return
      }
      await editor.document.save()
      await runStage(state, "fran++: rewording phrase", () =>
        api.reword(editor.document.getText(), humanNameOf(editor.document))
      )
    })
  )

  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left)
  statusBar.text = "$(sparkle) fran++"
  statusBar.show()
  context.subscriptions.push(statusBar)
  context.subscriptions.push(
    state.onDidChange((files) => {
      const hash = files.active.humanHash
      statusBar.text = hash ? `$(sparkle) ${files.name} ${hash.slice(0, 8)}` : `$(sparkle) ${files.name}`
    })
  )
}

export function deactivate(): void {}
