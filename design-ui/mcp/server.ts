import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { DesignUiApiClient } from "./client.ts";
import { designUiMcpTools, executeDesignUiTool } from "./tools.ts";

export function createDesignUiMcpServer() {
  const apiClient = new DesignUiApiClient();
  const server = new Server(
    {
      name: "design-ui-mcp",
      version: "0.1.0"
    },
    {
      capabilities: {
        tools: {}
      }
    }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: designUiMcpTools
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const result = await executeDesignUiTool(
      apiClient,
      request.params.name,
      (request.params.arguments ?? {}) as Record<string, unknown>
    );
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2)
        }
      ],
      structuredContent: result
    };
  });

  return server;
}

export async function runStdioServer() {
  const server = createDesignUiMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runStdioServer().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  });
}
