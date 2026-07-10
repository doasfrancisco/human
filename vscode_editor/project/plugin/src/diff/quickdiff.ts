import * as vscode from "vscode"
import { FranppState } from "../state"
import { artifactKeyFor, baseName, snapshotText, snapshotUri } from "./snapshot"

export function registerQuickDiff(context: vscode.ExtensionContext, state: FranppState): void {
  const sourceControl = vscode.scm.createSourceControl("franpp", "fran++")
  sourceControl.quickDiffProvider = {
    provideOriginalResource(uri: vscode.Uri): vscode.Uri | undefined {
      if (uri.scheme !== "file") {
        return undefined
      }
      const files = state.current()
      if (!files) {
        return undefined
      }
      const name = baseName(uri)
      const key = artifactKeyFor(name, files)
      if (!key || snapshotText(files, key) === undefined) {
        return undefined
      }
      return snapshotUri(name)
    },
  }
  context.subscriptions.push(sourceControl)
}
