import * as vscode from "vscode"
import { FilesResponse, FranppApi, programName } from "../api"
import { FranppState } from "../state"
import {
  ContextNode,
  FranppNode,
  HistoryTreeDataProvider,
  allNodes,
  contextsOf,
  isActive,
  nodeHash,
  nodeKind,
  nodePreview,
  pythonsOf,
} from "./tree"
import { HumanCodeLensProvider } from "./codelens"
import { RewordCodeActionProvider } from "./codeactions"

async function runBackend(state: FranppState, title: string, task: () => Promise<FilesResponse>): Promise<void> {
  try {
    const result = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title }, () => task())
    state.update(result)
  } catch (error) {
    vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error))
  }
}

async function pickNode(state: FranppState): Promise<FranppNode | undefined> {
  const tree = state.current()?.tree ?? []
  const nodes = allNodes(tree)
  if (nodes.length === 0) {
    vscode.window.showInformationMessage("fran++: no history yet — refresh the History view first")
    return undefined
  }
  const picked = await vscode.window.showQuickPick(
    nodes.map((node) => ({
      label: nodeHash(node).slice(0, 7),
      description: `${node.kind}${isActive(node) ? " · active" : ""}`,
      detail: nodePreview(node),
      node,
    })),
    { placeHolder: "Snapshot to check out" }
  )
  return picked?.node
}

function contextFlowLines(node: ContextNode): string[] {
  const lines = [`context [${node.context.role}]  ${node.context.hash}  ${node.context.preview}`]
  for (const python of pythonsOf(node.context)) {
    lines.push(`  python${python.target ? ` -> ${python.target}` : ""}  ${python.hash}  ${python.preview}`)
  }
  return lines
}

function flowText(node: FranppNode): string {
  const lines = [`human  ${node.human.hash}  ${node.human.preview}`]
  if (node.kind === "human") {
    for (const context of contextsOf(node.human)) {
      lines.push(...contextFlowLines({ kind: "context", context, human: node.human }).map((line) => `  ${line}`))
    }
    return lines.join("\n")
  }
  if (node.kind === "context") {
    lines.push(...contextFlowLines(node).map((line) => `  ${line}`))
    return lines.join("\n")
  }
  lines.push(`  context [${node.context.role}]  ${node.context.hash}  ${node.context.preview}`)
  lines.push(`    python${node.python.target ? ` -> ${node.python.target}` : ""}  ${node.python.hash}  ${node.python.preview}`)
  return lines.join("\n")
}

export function registerHistory(context: vscode.ExtensionContext, api: FranppApi, state: FranppState): void {
  const treeProvider = new HistoryTreeDataProvider(state)
  const treeView = vscode.window.createTreeView("franpp.history", { treeDataProvider: treeProvider })
  const lensProvider = new HumanCodeLensProvider(state)

  context.subscriptions.push(
    treeView,
    lensProvider,
    vscode.languages.registerCodeLensProvider({ language: "human" }, lensProvider),
    vscode.languages.registerCodeActionsProvider({ language: "human" }, new RewordCodeActionProvider(state), RewordCodeActionProvider.metadata),
    state.onDidChange(() => {
      treeProvider.refresh()
      lensProvider.refresh()
    }),
    vscode.commands.registerCommand("franpp.checkout", async (node?: FranppNode) => {
      const target = node ?? (await pickNode(state))
      if (!target) {
        return
      }
      const hash = nodeHash(target)
      await runBackend(state, `fran++: checking out ${hash.slice(0, 7)}`, () =>
        api.checkout(hash, nodeKind(target), programName(state.current()))
      )
    }),
    vscode.commands.registerCommand("franpp.deleteNode", async (node?: FranppNode) => {
      if (!node) {
        vscode.window.showErrorMessage("fran++: select a snapshot in the History view to delete")
        return
      }
      const hash = nodeHash(node)
      const confirmed = await vscode.window.showWarningMessage(
        `Delete ${node.kind} snapshot ${hash.slice(0, 7)}? This cannot be undone.`,
        { modal: true },
        "Delete"
      )
      if (confirmed !== "Delete") {
        return
      }
      await runBackend(state, `fran++: deleting ${hash.slice(0, 7)}`, () =>
        api.remove(hash, nodeKind(node), programName(state.current()))
      )
    }),
    vscode.commands.registerCommand("franpp.copyFlow", async (node?: FranppNode) => {
      if (!node) {
        vscode.window.showErrorMessage("fran++: select a snapshot in the History view to copy its flow")
        return
      }
      await vscode.env.clipboard.writeText(flowText(node))
      vscode.window.showInformationMessage("fran++: flow copied to clipboard")
    }),
    vscode.commands.registerCommand("franpp.refreshHistory", async () => {
      await runBackend(state, "fran++: refreshing history", () => api.files(programName(state.current())))
    })
  )
}
