import * as vscode from "vscode"

export type Active = { humanHash: string | null; contextHash: string | null; pythonHash: string | null }

export type Status = { hasContext: boolean; hasPython: boolean }

export type ContextRole = "leaf" | "split" | "direct"
export type NodeKind = "human" | "context" | "python"

export type ProvenanceEntry = {
  line: number | string
  status: string
  source: string
  text: string
  previousLine?: number | string | null
  target?: string | null
}

export type TreePython = { hash: string; preview: string; active: boolean; target?: string | null; createdAt: string; updatedAt: string }

export type TreeContext = { hash: string; preview: string; active: boolean; role: ContextRole; python?: TreePython | null; pythons: TreePython[]; createdAt: string; updatedAt: string }

export type TreeHuman = { hash: string; preview: string; active: boolean; context?: TreeContext | null; contexts: TreeContext[]; createdAt: string; updatedAt: string }

export type FilesResponse = {
  name: string
  human: string
  context: string
  python: string
  active: Active
  status: Status
  contextRole?: ContextRole | null
  contextProvenance: ProvenanceEntry[]
  pythonProvenance: ProvenanceEntry[]
  tree: TreeHuman[]
}

export const DEFAULT_PROGRAM = "program"

export function programName(files: FilesResponse | undefined): string {
  return files?.name ?? DEFAULT_PROGRAM
}

export class FranppApi {
  private baseUrl(): string {
    const configured = vscode.workspace.getConfiguration("franpp").get<string>("backendUrl", "http://localhost:8000")
    return configured.replace(/\/+$/, "")
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl()}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    })
    if (!response.ok) {
      const body = await response.text()
      throw new Error(body || `${response.status} ${response.statusText}`)
    }
    return (await response.json()) as T
  }

  private post(path: string, payload: unknown): Promise<FilesResponse> {
    return this.request<FilesResponse>(path, { method: "POST", body: JSON.stringify(payload) })
  }

  async health(): Promise<boolean> {
    try {
      const result = await this.request<{ ok: boolean }>("/api/health")
      return result.ok === true
    } catch {
      return false
    }
  }

  files(name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.request<FilesResponse>(`/api/files?name=${encodeURIComponent(name)}`)
  }

  save(human: string, name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/save", { human, name })
  }

  compile(human: string, name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/compile", { human, force: false, name })
  }

  humanToContext(human: string, name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/human-to-context", { human, force: false, name })
  }

  contextToPython(context: string, name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/context-to-python", { context, force: false, name })
  }

  reword(human: string, name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/reword", { human, name })
  }

  checkout(hash: string, kind: NodeKind = "human", name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/checkout", { kind, hash, name })
  }

  remove(hash: string, kind: NodeKind = "human", name: string = DEFAULT_PROGRAM): Promise<FilesResponse> {
    return this.post("/api/delete", { kind, hash, name })
  }
}
