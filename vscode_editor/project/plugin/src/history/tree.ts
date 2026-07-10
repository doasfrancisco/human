import * as vscode from "vscode"
import { NodeKind, TreeContext, TreeHuman, TreePython } from "../api"
import { FranppState } from "../state"

export type HumanNode = { kind: "human"; human: TreeHuman }
export type ContextNode = { kind: "context"; context: TreeContext; human: TreeHuman }
export type PythonNode = { kind: "python"; python: TreePython; context: TreeContext; human: TreeHuman }
export type FranppNode = HumanNode | ContextNode | PythonNode

export function contextsOf(human: TreeHuman): TreeContext[] {
  if (human.contexts && human.contexts.length > 0) {
    return human.contexts
  }
  return human.context ? [human.context] : []
}

export function pythonsOf(context: TreeContext): TreePython[] {
  if (context.pythons && context.pythons.length > 0) {
    return context.pythons
  }
  return context.python ? [context.python] : []
}

export function nodeHash(node: FranppNode): string {
  if (node.kind === "human") {
    return node.human.hash
  }
  if (node.kind === "context") {
    return node.context.hash
  }
  return node.python.hash
}

export function nodeKind(node: FranppNode): NodeKind {
  return node.kind
}

export function nodePreview(node: FranppNode): string {
  if (node.kind === "human") {
    return node.human.preview
  }
  if (node.kind === "context") {
    return node.context.preview
  }
  return node.python.preview
}

export function isActive(node: FranppNode): boolean {
  if (node.kind === "human") {
    return node.human.active
  }
  if (node.kind === "context") {
    return node.context.active
  }
  return node.python.active
}

export function allNodes(tree: TreeHuman[]): FranppNode[] {
  const nodes: FranppNode[] = []
  for (const human of tree) {
    nodes.push({ kind: "human", human })
    for (const context of contextsOf(human)) {
      nodes.push({ kind: "context", context, human })
      for (const python of pythonsOf(context)) {
        nodes.push({ kind: "python", python, context, human })
      }
    }
  }
  return nodes
}

function nodeIcon(node: FranppNode): vscode.ThemeIcon {
  const color = isActive(node) ? new vscode.ThemeColor("charts.green") : undefined
  if (node.kind === "human") {
    return new vscode.ThemeIcon(node.human.active ? "circle-filled" : "circle-outline", color)
  }
  if (node.kind === "context") {
    const roleIcon = node.context.role === "split" ? "split-horizontal" : node.context.role === "direct" ? "zap" : "note"
    return new vscode.ThemeIcon(roleIcon, color)
  }
  return new vscode.ThemeIcon(node.python.target ? "export" : "code", color)
}

function nodeTooltip(node: FranppNode): vscode.MarkdownString {
  const hash = nodeHash(node)
  const stamps = node.kind === "human" ? node.human : node.kind === "context" ? node.context : node.python
  const lines = [`**${node.kind}** \`${hash}\``]
  if (node.kind === "context") {
    lines.push(`role: ${node.context.role}`)
  }
  if (node.kind === "python" && node.python.target) {
    lines.push(`target: \`${node.python.target}\``)
  }
  lines.push(`created: ${stamps.createdAt}`)
  lines.push(`updated: ${stamps.updatedAt}`)
  if (isActive(node)) {
    lines.push("**active**")
  }
  return new vscode.MarkdownString(lines.join("\n\n"))
}

function collapsibleState(node: FranppNode): vscode.TreeItemCollapsibleState {
  if (node.kind === "python") {
    return vscode.TreeItemCollapsibleState.None
  }
  const hasChildren = node.kind === "human" ? contextsOf(node.human).length > 0 : pythonsOf(node.context).length > 0
  if (!hasChildren) {
    return vscode.TreeItemCollapsibleState.None
  }
  return isActive(node) ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.Collapsed
}

const CONTEXT_VALUES: Record<NodeKind, string> = {
  human: "franppHuman",
  context: "franppContext",
  python: "franppPython",
}

export class HistoryTreeDataProvider implements vscode.TreeDataProvider<FranppNode> {
  private readonly emitter = new vscode.EventEmitter<FranppNode | undefined | void>()
  readonly onDidChangeTreeData = this.emitter.event

  constructor(private readonly state: FranppState) {}

  refresh(): void {
    this.emitter.fire()
  }

  getTreeItem(node: FranppNode): vscode.TreeItem {
    const item = new vscode.TreeItem(nodeHash(node).slice(0, 7), collapsibleState(node))
    const preview = nodePreview(node)
    item.description = node.kind === "python" && node.python.target ? `${node.python.target} · ${preview}` : preview
    item.tooltip = nodeTooltip(node)
    item.iconPath = nodeIcon(node)
    item.contextValue = CONTEXT_VALUES[node.kind]
    item.command = { command: "franpp.checkout", title: "Checkout Snapshot", arguments: [node] }
    return item
  }

  getChildren(node?: FranppNode): FranppNode[] {
    if (!node) {
      const tree = this.state.current()?.tree ?? []
      return tree.map((human) => ({ kind: "human", human }))
    }
    if (node.kind === "human") {
      return contextsOf(node.human).map((context) => ({ kind: "context", context, human: node.human }))
    }
    if (node.kind === "context") {
      return pythonsOf(node.context).map((python) => ({ kind: "python", python, context: node.context, human: node.human }))
    }
    return []
  }
}
