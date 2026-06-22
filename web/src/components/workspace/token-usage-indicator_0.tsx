"use client";

import type { Message } from "@langchain/langgraph-sdk";
import { CoinsIcon } from "lucide-react";
import { useMemo } from "react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useI18n } from "@/core/i18n/hooks";
import { accumulateUsage, formatTokenCount, getCommandUsageBreakdown } from "@/core/messages/usage";
import { cn } from "@/lib/utils";

interface TokenUsageIndicatorProps {
  messages: Message[];
  className?: string;
}

export function TokenUsageIndicator({
  messages,
  className,
}: TokenUsageIndicatorProps) {
  const { t } = useI18n();

  const usage = useMemo(() => accumulateUsage(messages), [messages]);
  const breakdown = useMemo(() => getCommandUsageBreakdown(messages), [messages]);

  if (!usage) {
    return null;
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "text-muted-foreground flex cursor-pointer hover:text-foreground transition-colors items-center gap-1 text-xs",
            className,
          )}
        >
          <CoinsIcon size={14} />
          <span>{formatTokenCount(usage.totalTokens)}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent side="top" align="end" className="w-[380px] p-4">
        <div className="space-y-4">
          <div className="space-y-1 text-xs">
            <div className="font-medium text-sm border-b pb-2 mb-2">{t.tokenUsage.title} (Current Thread)</div>
            <div className="flex justify-between gap-4">
              <span>{t.tokenUsage.input}</span>
              <span className="font-mono">
                {formatTokenCount(usage.inputTokens)}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span>{t.tokenUsage.output}</span>
              <span className="font-mono">
                {formatTokenCount(usage.outputTokens)}
              </span>
            </div>
            <div className="border-t pt-1">
              <div className="flex justify-between gap-4">
                <span>{t.tokenUsage.total}</span>
                <span className="font-mono font-medium">
                  {formatTokenCount(usage.totalTokens)}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="font-medium text-xs text-muted-foreground">Current Command Breakdown</div>
            {breakdown.length === 0 ? (
              <div className="text-xs text-muted-foreground italic">No tokens used in current command.</div>
            ) : (
              <div className="rounded-md border overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-muted/50 border-b">
                    <tr>
                      <th className="px-2 py-1.5 font-medium text-muted-foreground">Stage</th>
                      <th className="px-2 py-1.5 font-medium text-muted-foreground">Model</th>
                      <th className="px-2 py-1.5 font-medium text-right text-muted-foreground">Tokens</th>
                      <th className="px-2 py-1.5 font-medium text-right text-muted-foreground">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {breakdown.map((item, idx) => (
                      <tr key={idx} className="bg-background">
                        <td className="px-2 py-1.5 whitespace-nowrap">{item.stage}</td>
                        <td className="px-2 py-1.5 text-muted-foreground truncate max-w-[100px]" title={item.model}>
                          {item.model}
                        </td>
                        <td className="px-2 py-1.5 font-mono text-right">{item.tokens.toLocaleString()}</td>
                        <td className="px-2 py-1.5 font-mono text-right text-muted-foreground">
                          {item.percentage.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
