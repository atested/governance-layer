export type HealthResponse = {
  ok: true;
  service: "design-ui-api";
  timestamp: string;
};

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json() as Promise<HealthResponse>;
}
