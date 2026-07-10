export type TreePython = {
  hash: string;
  preview: string;
  active: boolean;
  target?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ContextRole = "leaf" | "split" | "direct";

export type TreeContext = {
  hash: string;
  preview: string;
  active: boolean;
  role: ContextRole;
  python: TreePython | null;
  pythons: TreePython[];
  createdAt: string;
  updatedAt: string;
};

export type TreeHuman = {
  hash: string;
  preview: string;
  active: boolean;
  context: TreeContext | null;
  contexts: TreeContext[];
  createdAt: string;
  updatedAt: string;
};

export type ContextProvenance = {
  line: number | string;
  status: string;
  source: string;
  text: string;
  previousLine?: number | string | null;
  target?: string | null;
};

export type CompiledUnit = {
  target: string;
  python: string;
  hash: string;
};

export type Files = {
  name: string;
  human: string;
  context: string;
  python: string;
  units: CompiledUnit[];
  active: {
    humanHash: string | null;
    contextHash: string | null;
    pythonHash: string | null;
  };
  status: {
    hasContext: boolean;
    hasPython: boolean;
  };
  contextRole: ContextRole | null;
  contextProvenance: ContextProvenance[];
  pythonProvenance: ContextProvenance[];
  tree: TreeHuman[];
};

export type Bundle = {
  human: string;
  context: string;
  python: string;
};

export type FileNode = {
  name: string;
  path: string;
  type: "dir" | "file";
  children: FileNode[];
};

export type PickedFolder = {
  path: string | null;
};

export type Project = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  active: boolean;
};

export type ProjectList = {
  projects: Project[];
};

export const DEFAULT_PROGRAM = "program";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

async function requestFiles(path: string, init?: RequestInit): Promise<Files> {
  const files = await request<
    Omit<Files, "pythonProvenance" | "units"> & {
      pythonProvenance?: ContextProvenance[];
      units?: CompiledUnit[];
    }
  >(path, init);
  return { ...files, pythonProvenance: files.pythonProvenance ?? [], units: files.units ?? [] };
}

export function getFiles(name: string = DEFAULT_PROGRAM) {
  return requestFiles(`/api/files?name=${encodeURIComponent(name)}`);
}

export function saveFiles(
  files: Partial<Pick<Files, "human" | "context" | "python">>,
  name: string = DEFAULT_PROGRAM
) {
  return requestFiles("/api/save", {
    method: "POST",
    body: JSON.stringify({ ...files, name }),
  });
}

export function checkout(kind: "human" | "context" | "python", hash: string, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/checkout", {
    method: "POST",
    body: JSON.stringify({ kind, hash, name }),
  });
}

export function deleteSnapshot(kind: "human" | "context" | "python", hash: string, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/delete", {
    method: "POST",
    body: JSON.stringify({ kind, hash, name }),
  });
}

export function getBundle(humanHash: string, name: string = DEFAULT_PROGRAM) {
  return request<Bundle>("/api/bundle", {
    method: "POST",
    body: JSON.stringify({ humanHash, name }),
  });
}

export function humanToContext(human: string, force = false, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/human-to-context", {
    method: "POST",
    body: JSON.stringify({ human, force, name }),
  });
}

export function humanToSplit(human: string, force = false, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/human-to-split", {
    method: "POST",
    body: JSON.stringify({ human, force, name }),
  });
}

export function contextToPython(context: string, force = false, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/context-to-python", {
    method: "POST",
    body: JSON.stringify({ context, force, name }),
  });
}

export function compile(human: string, force = false, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/compile", {
    method: "POST",
    body: JSON.stringify({ human, force, name }),
  });
}

export function compileAll(human: string, force = false, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/compile-all", {
    method: "POST",
    body: JSON.stringify({ human, force, name }),
  });
}

export function reword(human: string, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/reword", {
    method: "POST",
    body: JSON.stringify({ human, name }),
  });
}

export function getFileTree(path?: string, depth?: number) {
  const params = new URLSearchParams();
  if (path) params.set("path", path);
  if (depth !== undefined) params.set("depth", String(depth));
  const query = params.toString();
  return request<FileNode>(`/api/fs/tree${query ? `?${query}` : ""}`);
}

export type FsFile = {
  path: string;
  name: string;
  content: string;
};

export type FsEntry = {
  name: string;
  path: string;
  type: "dir" | "file";
};

export function fsRead(path: string) {
  return request<FsFile>(`/api/fs/read?path=${encodeURIComponent(path)}`);
}

export function fsWrite(path: string, content: string) {
  return request<{ ok: boolean; path: string }>("/api/fs/write", {
    method: "POST",
    body: JSON.stringify({ path, content }),
  });
}

export function fsCreate(parent: string, name: string, kind: "file" | "dir") {
  return request<FsEntry>("/api/fs/create", {
    method: "POST",
    body: JSON.stringify({ parent, name, kind }),
  });
}

export function fsDelete(path: string) {
  return request<{ ok: boolean }>("/api/fs/delete", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function pickFolder() {
  return request<PickedFolder>("/api/fs/pick-folder", { method: "POST" });
}

export function getProjects() {
  return request<ProjectList>("/api/projects");
}

export function createProject(name: string) {
  return request<ProjectList>("/api/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function selectProject(id: string, name: string = DEFAULT_PROGRAM) {
  return requestFiles("/api/projects/select", {
    method: "POST",
    body: JSON.stringify({ id, name }),
  });
}

export function deleteProject(id: string) {
  return request<ProjectList>("/api/projects/delete", {
    method: "POST",
    body: JSON.stringify({ id }),
  });
}

export function renameProject(id: string, name: string) {
  return request<ProjectList>("/api/projects/rename", {
    method: "POST",
    body: JSON.stringify({ id, name }),
  });
}

export function wipeProjects() {
  return request<ProjectList>("/api/projects/wipe", {
    method: "POST",
  });
}
