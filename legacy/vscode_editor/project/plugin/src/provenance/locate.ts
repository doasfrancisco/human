import * as vscode from "vscode"
import { FilesResponse, programName } from "../api"
import { defaultPythonTarget, narrowestPhraseMatchesAt } from "./phrases"

export type DocKind = { kind: "human" } | { kind: "context" } | { kind: "python"; target: string }

function pathEndsWith(uri: vscode.Uri, suffix: string): boolean {
  return uri.path.toLowerCase().endsWith(suffix.toLowerCase())
}

async function findWorkspaceFile(pattern: string): Promise<vscode.Uri | undefined> {
  const found = await vscode.workspace.findFiles(pattern, "**/node_modules/**", 1)
  return found[0]
}

export function knownPythonTargets(files: FilesResponse | undefined): Set<string> {
  const targets = new Set<string>([defaultPythonTarget(files)])
  for (const entry of files?.pythonProvenance ?? []) {
    if (entry.target) targets.add(entry.target)
  }
  for (const entry of files?.contextProvenance ?? []) {
    if (entry.target && entry.target.endsWith(".py")) targets.add(entry.target)
  }
  return targets
}

export function classify(document: vscode.TextDocument, files: FilesResponse | undefined): DocKind | undefined {
  if (document.uri.scheme !== "file") return undefined
  const name = programName(files)
  if (pathEndsWith(document.uri, `/human/${name}.human`)) return { kind: "human" }
  if (pathEndsWith(document.uri, `/human/${name}.context`)) return { kind: "context" }
  const base = document.uri.path.split("/").pop() ?? ""
  if (base.endsWith(".py") && knownPythonTargets(files).has(base) && pathEndsWith(document.uri, `/project/${base}`)) {
    return { kind: "python", target: base }
  }
  return undefined
}

export async function resolvePythonUri(target: string, files: FilesResponse | undefined): Promise<vscode.Uri | undefined> {
  const found = await findWorkspaceFile(`**/project/${target}`)
  if (found) return found
  const fallback = defaultPythonTarget(files)
  if (target !== fallback) return resolvePythonUri(fallback, files)
  return undefined
}

export async function resolveContextUri(files: FilesResponse | undefined): Promise<vscode.Uri | undefined> {
  return findWorkspaceFile(`**/human/${programName(files)}.context`)
}

export function tracedPhraseRangeAt(
  editor: vscode.TextEditor,
  files: FilesResponse | undefined
): vscode.Range | undefined {
  if (!editor.selection.isEmpty) return new vscode.Range(editor.selection.start, editor.selection.end)
  if (!files) return undefined
  const matches = narrowestPhraseMatchesAt(
    editor.document.getText(),
    [...files.contextProvenance, ...files.pythonProvenance],
    editor.document.offsetAt(editor.selection.active)
  )
  if (!matches.length) return undefined
  return new vscode.Range(
    editor.document.positionAt(matches[0].range.start),
    editor.document.positionAt(matches[0].range.end)
  )
}
