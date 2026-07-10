import * as vscode from "vscode"
import { FilesResponse, programName } from "../api"
import { FranppState } from "../state"

export const SNAPSHOT_SCHEME = "franpp-snapshot"

export type ArtifactKey = "human" | "context" | "python"

export function artifactFileNames(files: FilesResponse | undefined): string[] {
  const name = programName(files)
  return [`${name}.human`, `${name}.context`, `${name}.py`]
}

export function artifactKeyFor(fileName: string, files: FilesResponse | undefined): ArtifactKey | undefined {
  const name = programName(files)
  if (fileName === `${name}.human`) return "human"
  if (fileName === `${name}.context`) return "context"
  if (fileName === `${name}.py`) return "python"
  return undefined
}

export function baseName(uri: vscode.Uri): string {
  const segments = uri.path.split("/")
  return segments[segments.length - 1]
}

export function snapshotUri(fileName: string): vscode.Uri {
  return vscode.Uri.from({ scheme: SNAPSHOT_SCHEME, path: fileName })
}

export function snapshotText(files: FilesResponse, key: ArtifactKey): string | undefined {
  if (key === "human") {
    return files.human
  }
  if (key === "context") {
    return files.status.hasContext ? files.context : undefined
  }
  return files.status.hasPython ? files.python : undefined
}

export function registerSnapshotProvider(context: vscode.ExtensionContext, state: FranppState): void {
  const emitter = new vscode.EventEmitter<vscode.Uri>()
  const provider: vscode.TextDocumentContentProvider = {
    onDidChange: emitter.event,
    provideTextDocumentContent(uri: vscode.Uri): string | undefined {
      const files = state.current()
      if (!files) {
        return undefined
      }
      const key = artifactKeyFor(baseName(uri), files)
      return key ? snapshotText(files, key) : undefined
    },
  }
  const knownFileNames = new Set<string>()
  context.subscriptions.push(
    emitter,
    vscode.workspace.registerTextDocumentContentProvider(SNAPSHOT_SCHEME, provider),
    state.onDidChange((files) => {
      for (const fileName of artifactFileNames(files)) {
        knownFileNames.add(fileName)
      }
      for (const fileName of knownFileNames) {
        emitter.fire(snapshotUri(fileName))
      }
    })
  )
}
