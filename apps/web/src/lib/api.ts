/**
 * API client and Server-Sent Events (SSE) streaming helpers.
 */

export type RoleType = "Admin" | "Editor" | "Viewer" | "Auditor";

export interface UserContext {
  workspaceId: string;
  role: RoleType;
  token?: string;
}

export const defaultUserContext: UserContext = {
  workspaceId: "default",
  role: "Admin",
};

export function getAuthHeaders(ctx: UserContext = defaultUserContext): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Workspace-Id": ctx.workspaceId,
    "X-Role": ctx.role,
  };
  if (ctx.token) {
    headers["Authorization"] = `Bearer ${ctx.token}`;
  }
  return headers;
}

export interface AskEventPayload {
  event: string;
  data: any;
}

export async function* streamAskQuestion(
  question: string,
  asOf: string | null = null,
  ctx: UserContext = defaultUserContext
): AsyncGenerator<AskEventPayload> {
  const response = await fetch("/api/v1/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(ctx),
    },
    body: JSON.stringify({
      question,
      as_of: asOf || null,
      stream: true,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API error (${response.status}): ${errText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body is not readable");
  }

  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "message";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      if (trimmed.startsWith("event:")) {
        currentEvent = trimmed.replace("event:", "").trim();
      } else if (trimmed.startsWith("data:")) {
        const rawData = trimmed.replace("data:", "").trim();
        try {
          const parsed = JSON.parse(rawData);
          yield { event: currentEvent, data: parsed };
        } catch {
          yield { event: currentEvent, data: rawData };
        }
      }
    }
  }
}
