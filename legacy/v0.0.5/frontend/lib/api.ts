export type TreePython = {
  hash: string;
  preview: string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type TreeContext = {
  hash: string;
  preview: string;
  active: boolean;
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
  contextProvenance: ContextProvenance[];
  tree: TreeHuman[];
};

export type Bundle = {
  human: string;
  context: string;
  python: string;
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

export function getFiles() {
  return request<Files>("/api/files");
}

export function saveFiles(files: Partial<Pick<Files, "human" | "context" | "python">>) {
  return request<Files>("/api/save", {
    method: "POST",
    body: JSON.stringify(files),
  });
}

export function checkout(kind: "human" | "context" | "python", hash: string) {
  return request<Files>("/api/checkout", {
    method: "POST",
    body: JSON.stringify({ kind, hash }),
  });
}

export function deleteSnapshot(kind: "human" | "context" | "python", hash: string) {
  return request<Files>("/api/delete", {
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
  return request<Files>("/api/human-to-context", {
    method: "POST",
    body: JSON.stringify({ human, force }),
  });
}

export function contextToPython(context: string, force = false) {
  return request<Files>("/api/context-to-python", {
    method: "POST",
    body: JSON.stringify({ context, force }),
  });
}

export function compileAll(human: string, force = false) {
  return request<Files>("/api/compile-all", {
    method: "POST",
    body: JSON.stringify({ human, force }),
  });
}
