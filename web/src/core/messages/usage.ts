import type { Message } from "@langchain/langgraph-sdk";

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
}

/**
 * Extract usage_metadata from an AI message if present.
 * The field is added by the backend (PR #1218) but not typed in the SDK.
 */
function getUsageMetadata(
  message: Message,
): TokenUsage | null {
  if (message.type !== "ai") {
    return null;
  }
  const usage = (message as Record<string, unknown>).usage_metadata as
    | { input_tokens?: number; output_tokens?: number; total_tokens?: number }
    | undefined;
  if (!usage) {
    return null;
  }
  return {
    inputTokens: usage.input_tokens ?? 0,
    outputTokens: usage.output_tokens ?? 0,
    totalTokens: usage.total_tokens ?? 0,
  };
}

/**
 * Accumulate token usage across all AI messages in a thread.
 */
export function accumulateUsage(messages: Message[]): TokenUsage | null {
  const cumulative: TokenUsage = {
    inputTokens: 0,
    outputTokens: 0,
    totalTokens: 0,
  };
  let hasUsage = false;
  for (const message of messages) {
    const usage = getUsageMetadata(message);
    if (usage) {
      hasUsage = true;
      cumulative.inputTokens += usage.inputTokens;
      cumulative.outputTokens += usage.outputTokens;
      cumulative.totalTokens += usage.totalTokens;
    }
  }
  return hasUsage ? cumulative : null;
}

/**
 * Format a token count for display: 1234 -> "1,234", 12345 -> "12.3K"
 */
export function formatTokenCount(count: number): string {
  if (count < 10_000) {
    return count.toLocaleString();
  }
  return `${(count / 1000).toFixed(1)}K`;
}

export interface StageTokenUsage {
  stage: string;
  model: string;
  tokens: number;
  percentage: number;
}

/**
 * Get a detailed token breakdown per stage for the LAST command in the thread.
 */
export function getCommandUsageBreakdown(messages: Message[]): StageTokenUsage[] {
  let lastHumanIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg && msg.type === "human") {
      lastHumanIndex = i;
      break;
    }
  }

  const currentCommandMessages = lastHumanIndex >= 0 ? messages.slice(lastHumanIndex) : messages;

  let totalTokens = 0;
  const stageMap = new Map<string, { stage: string; model: string; tokens: number }>();

  for (const message of currentCommandMessages) {
    const usage = getUsageMetadata(message);
    if (usage && usage.totalTokens > 0) {
      // The backend adds name=agent_type_finalize or similar
      let stageName = message.name || "unknown_stage";
      stageName = stageName.replace("_finalize", "").toUpperCase();
      
      const record = message as Record<string, unknown>;
      const responseMetadata = record.response_metadata as Record<string, unknown> | undefined;
      const modelName = typeof responseMetadata?.model_name === "string" 
        ? responseMetadata.model_name 
        : typeof responseMetadata?.model === "string"
        ? responseMetadata.model
        : "unknown_model";

      const key = `${stageName}_${modelName}`;
      if (!stageMap.has(key)) {
        stageMap.set(key, { stage: stageName, model: modelName, tokens: 0 });
      }

      stageMap.get(key)!.tokens += usage.totalTokens;
      totalTokens += usage.totalTokens;
    }
  }

  if (totalTokens === 0) return [];

  const breakdown: StageTokenUsage[] = Array.from(stageMap.values()).map(item => ({
    ...item,
    percentage: (item.tokens / totalTokens) * 100
  }));

  // Sort by tokens descending
  return breakdown.sort((a, b) => b.tokens - a.tokens);
}
