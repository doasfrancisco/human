import * as vscode from "vscode"
import { FilesResponse, FranppApi, programName } from "../api"
import { FranppState } from "../state"
import { artifactKeyFor, baseName, registerSnapshotProvider, snapshotText, snapshotUri } from "./snapshot"
import { registerQuickDiff } from "./quickdiff"

const NESTING_KEY = "*.human"
const NESTING_CHILDREN = "${capture}.context, ${capture}.py, ${capture}.explain"

async function ensureFiles(api: FranppApi, state: FranppState): Promise<FilesResponse | undefined> {
  const existing = state.current()
  if (existing) {
    return existing
  }
  try {
    const fetched = await api.files()
    state.update(fetched)
    return fetched
  } catch {
    return undefined
  }
}

function activeArtifact(files: FilesResponse | undefined): vscode.Uri | undefined {
  const editor = vscode.window.activeTextEditor
  if (!editor || editor.document.uri.scheme !== "file") {
    return undefined
  }
  return artifactKeyFor(baseName(editor.document.uri), files) ? editor.document.uri : undefined
}

async function pickArtifact(files: FilesResponse | undefined): Promise<vscode.Uri | undefined> {
  const candidates = await vscode.workspace.findFiles(`**/${programName(files)}.{human,context,py}`, "**/node_modules/**")
  if (candidates.length === 0) {
    return undefined
  }
  const items = candidates
    .map((uri) => ({ label: vscode.workspace.asRelativePath(uri), uri }))
    .sort((a, b) => a.label.localeCompare(b.label))
  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: "fran++: pick an artifact to diff against the last compiled snapshot",
  })
  return picked?.uri
}

async function showDiff(api: FranppApi, state: FranppState): Promise<void> {
  const files = await ensureFiles(api, state)
  const target = activeArtifact(files) ?? (await pickArtifact(files))
  if (!target) {
    const program = programName(files)
    vscode.window.showInformationMessage(
      `fran++: no artifact to diff (open ${program}.human, ${program}.context, or ${program}.py)`
    )
    return
  }
  const name = baseName(target)
  const key = artifactKeyFor(name, files)
  const before = files && key ? snapshotText(files, key) : undefined
  if (before === undefined) {
    vscode.window.showInformationMessage(`fran++: no compiled snapshot for ${name} yet`)
    return
  }
  await vscode.commands.executeCommand("vscode.diff", snapshotUri(name), target, `${name} — compiled ↔ working`)
}

async function toggleGenerated(): Promise<void> {
  const config = vscode.workspace.getConfiguration()
  const show = !config.get<boolean>("franpp.showGenerated", true)
  await config.update("franpp.showGenerated", show, vscode.ConfigurationTarget.Workspace)
  const workspacePatterns = config.inspect<Record<string, string>>("explorer.fileNesting.patterns")?.workspaceValue
  const patterns = { ...(workspacePatterns ?? {}) }
  if (show) {
    delete patterns[NESTING_KEY]
    const remaining = Object.keys(patterns).length > 0 ? patterns : undefined
    await config.update("explorer.fileNesting.patterns", remaining, vscode.ConfigurationTarget.Workspace)
    await config.update("explorer.fileNesting.enabled", undefined, vscode.ConfigurationTarget.Workspace)
  } else {
    patterns[NESTING_KEY] = NESTING_CHILDREN
    await config.update("explorer.fileNesting.enabled", true, vscode.ConfigurationTarget.Workspace)
    await config.update("explorer.fileNesting.patterns", patterns, vscode.ConfigurationTarget.Workspace)
  }
}

export function registerDiff(context: vscode.ExtensionContext, api: FranppApi, state: FranppState): void {
  registerSnapshotProvider(context, state)
  registerQuickDiff(context, state)
  context.subscriptions.push(
    vscode.commands.registerCommand("franpp.showDiff", () => showDiff(api, state)),
    vscode.commands.registerCommand("franpp.toggleGenerated", () => toggleGenerated())
  )
}
