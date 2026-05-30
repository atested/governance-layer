import { DEFAULT_API_URL } from "./schemas.ts";

export class DesignUiApiError extends Error {
  readonly details?: { status?: number; url?: string };

  constructor(message: string, details?: { status?: number; url?: string }) {
    super(message);
    this.name = "DesignUiApiError";
    this.details = details;
  }
}

export type FetchLike = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;

export type DesignUiApiClientOptions = {
  baseUrl?: string;
  fetchImpl?: FetchLike;
};

export class DesignUiApiClient {
  readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;

  constructor(options: DesignUiApiClientOptions = {}) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl ?? process.env.DESIGN_UI_API_URL ?? DEFAULT_API_URL);
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "GET" });
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: "POST", body: JSON.stringify(body) });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        ...init,
        headers: {
          "content-type": "application/json",
          ...(init.headers ?? {})
        }
      });
    } catch (error) {
      throw new DesignUiApiError(
        `Design UI API is unavailable at ${this.baseUrl}. Start Design UI before using MCP tools.`,
        { url }
      );
    }

    if (!response.ok) {
      let body = "";
      try {
        body = await response.text();
      } catch {
        body = "";
      }
      throw new DesignUiApiError(
        `Design UI API request failed (${response.status}) for ${url}${body ? `: ${body}` : ""}`,
        { status: response.status, url }
      );
    }

    return (await response.json()) as T;
  }
}

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.replace(/\/+$/, "");
}

export function params(projectId: string) {
  return new URLSearchParams({ projectId }).toString();
}
