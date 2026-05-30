export type HealthResponse = {
  ok: true;
  service: "design-ui-api";
  timestamp: string;
};

import type {
  ActiveContext,
  ChatMessage,
  DesignMap,
  DesignProject,
  DesignProposal,
  DiscoveryItem,
  LineageEvent,
  PurposeItem,
  SpecBuilderResponse,
  SpecExport
} from "../types/design";

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "content-type": "application/json",
      ...(options?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health");
}

export async function listProjects() {
  return requestJson<DesignProject[]>("/api/projects");
}

export async function createProject(title: string) {
  return requestJson<DesignProject>("/api/projects", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export async function listItems(projectId: string, kind: "discovery"): Promise<DiscoveryItem[]>;
export async function listItems(projectId: string, kind: "purpose"): Promise<PurposeItem[]>;
export async function listItems(projectId: string, kind: "discovery" | "purpose") {
  return requestJson(`/api/items?projectId=${encodeURIComponent(projectId)}&kind=${kind}`);
}

export async function createItem(
  projectId: string,
  kind: "discovery" | "purpose",
  input: { title: string; body?: string; discoveryType?: string; purposeType?: string }
) {
  return requestJson<DiscoveryItem | PurposeItem>(
    `/api/items?projectId=${encodeURIComponent(projectId)}&kind=${kind}`,
    {
      method: "POST",
      body: JSON.stringify(input)
    }
  );
}

export async function updateItem(
  projectId: string,
  kind: "discovery" | "purpose",
  id: string,
  input: { title?: string; body?: string; discoveryType?: string; purposeType?: string }
) {
  return requestJson<DiscoveryItem | PurposeItem>(
    `/api/items?projectId=${encodeURIComponent(projectId)}&kind=${kind}&id=${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    }
  );
}

export async function listProposals(projectId: string) {
  return requestJson<DesignProposal[]>(`/api/proposals?projectId=${encodeURIComponent(projectId)}`);
}

export async function createProposal(
  projectId: string,
  input: { proposalType: string; proposedChanges: unknown; rationale?: string; sourceMessageIds?: string[] }
) {
  return requestJson<DesignProposal>(`/api/proposals?projectId=${encodeURIComponent(projectId)}`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function acceptProposal(projectId: string, proposalId: string) {
  return requestJson(`/api/proposals/${encodeURIComponent(proposalId)}/accept?projectId=${encodeURIComponent(projectId)}`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function rejectProposal(projectId: string, proposalId: string) {
  return requestJson(`/api/proposals/${encodeURIComponent(proposalId)}/reject?projectId=${encodeURIComponent(projectId)}`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function listChatMessages(projectId: string) {
  return requestJson<ChatMessage[]>(`/api/chat?projectId=${encodeURIComponent(projectId)}`);
}

export async function sendChatMessage(projectId: string, content: string) {
  return requestJson<{
    operatorMessage: ChatMessage;
    assistantMessage: ChatMessage;
    proposals: DesignProposal[];
  }>(`/api/chat/send?projectId=${encodeURIComponent(projectId)}`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export async function listLineageEvents(projectId: string, subjectId?: string) {
  const params = new URLSearchParams({ projectId });
  if (subjectId) params.set("subjectId", subjectId);
  return requestJson<{ events: LineageEvent[] }>(`/api/lineage?${params.toString()}`);
}

export async function getDesignMap(projectId: string) {
  return requestJson<DesignMap>(`/api/map?projectId=${encodeURIComponent(projectId)}`);
}

export async function selectMapNode(projectId: string, nodeId: string) {
  return requestJson<{ activeContext: ActiveContext; map: DesignMap }>(
    `/api/map/context?projectId=${encodeURIComponent(projectId)}`,
    {
      method: "POST",
      body: JSON.stringify({ nodeId })
    }
  );
}

export async function getSpecBuilder(projectId: string) {
  return requestJson<SpecBuilderResponse>(`/api/spec?projectId=${encodeURIComponent(projectId)}`);
}

export async function createSpecExport(projectId: string, format: "markdown" | "json") {
  return requestJson<{ export: SpecExport }>(
    `/api/spec/export?projectId=${encodeURIComponent(projectId)}`,
    {
      method: "POST",
      body: JSON.stringify({ format })
    }
  );
}
