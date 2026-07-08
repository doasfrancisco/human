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

export type Files = {
  human: string;
  context: string;
  python: string;
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
  const files = await request<Omit<Files, "pythonProvenance"> & { pythonProvenance?: ContextProvenance[] }>(path, init);
  return { ...files, pythonProvenance: files.pythonProvenance ?? [] };
}

export function getFiles() {
  return requestFiles("/api/files");
}

export function saveFiles(files: Partial<Pick<Files, "human" | "context" | "python">>) {
  return requestFiles("/api/save", {
    method: "POST",
    body: JSON.stringify(files),
  });
}

export function checkout(kind: "human" | "context" | "python", hash: string) {
  return requestFiles("/api/checkout", {
    method: "POST",
    body: JSON.stringify({ kind, hash }),
  });
}

export function deleteSnapshot(kind: "human" | "context" | "python", hash: string) {
  return requestFiles("/api/delete", {
    method: "POST",
    body: JSON.stringify({ kind, hash }),
  });
}

export function getBundle(humanHash: string) {
  return request<Bundle>("/api/bundle", {
    method: "POST",
    body: JSON.stringify({ humanHash }),
  });
}

export function humanToContext(human: string, force = false) {
  return requestFiles("/api/human-to-context", {
    method: "POST",
    body: JSON.stringify({ human, force }),
  });
}

export function humanToSplit(human: string, force = false) {
  return requestFiles("/api/human-to-split", {
    method: "POST",
    body: JSON.stringify({ human, force }),
  });
}

export function contextToPython(context: string, force = false) {
  return requestFiles("/api/context-to-python", {
    method: "POST",
    body: JSON.stringify({ context, force }),
  });
}

export function compile(human: string, force = false) {
  return requestFiles("/api/compile", {
    method: "POST",
    body: JSON.stringify({ human, force }),
  });
}

export function reword(human: string) {
  return requestFiles("/api/reword", {
    method: "POST",
    body: JSON.stringify({ human }),
  });
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

export function selectProject(id: string) {
  return requestFiles("/api/projects/select", {
    method: "POST",
    body: JSON.stringify({ id }),
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
