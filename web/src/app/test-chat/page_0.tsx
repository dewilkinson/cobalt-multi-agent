"use client";

import { useStream } from "@langchain/langgraph-sdk/react";
import { useState } from "react";
import { getAPIClient } from "@/core/api";

export default function TestChatPage() {
  const client = getAPIClient();
  const [threadId, setThreadId] = useState(crypto.randomUUID());
  const [prompt, setPrompt] = useState("analyze NVDA smc");

  const [errorStr, setErrorStr] = useState<string | null>(null);

  const thread = useStream({
    apiUrl: client.apiUrl,
    assistantId: "lead_agent",
    onError: (err) => {
      console.error(err);
      setErrorStr(err.message || String(err));
    }
  });

  const handleStart = async () => {
    // Generate new thread just to be sure we are fresh
    const id = crypto.randomUUID();
    setThreadId(id);
    
    await thread.submit({
      messages: [{ type: "human", content: prompt }]
    }, {
      threadId: id,
      streamSubgraphs: true,
      streamMode: ["values", "messages", "updates"],
    });
  };

  return (
    <div className="flex flex-col p-8 bg-background text-foreground min-h-screen">
      <h1 className="text-2xl font-bold mb-4">Chat Fidelity Test</h1>
      
      <div className="flex gap-2 mb-4">
        <input 
          className="border p-2 rounded" 
          value={prompt} 
          onChange={(e) => setPrompt(e.target.value)} 
          style={{ width: "400px" }}
        />
        <button 
          className="bg-blue-500 text-white p-2 rounded" 
          onClick={handleStart}
        >
          Send Test Message
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-4">
        {errorStr && (
          <div className="col-span-2 p-4 bg-red-100 text-red-900 rounded border border-red-300">
            <strong>Error:</strong> {errorStr}
          </div>
        )}
        <div>
          <h2 className="font-bold border-b pb-2 mb-2">Rendered Output</h2>
          <div className="flex flex-col gap-2">
            {thread.messages.map((msg, i) => (
              <div key={i} className="p-4 border rounded shadow-sm opacity-100">
                <div className="text-xs text-muted-foreground uppercase">{msg.type}</div>
                <div className="mt-2 whitespace-pre-wrap">
                  {typeof msg.content === 'string' 
                    ? msg.content 
                    : JSON.stringify(msg.content, null, 2)}
                </div>
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <div className="mt-2 text-xs text-blue-500">
                    Tool Calls: {JSON.stringify(msg.tool_calls)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        
        <div>
          <h2 className="font-bold border-b pb-2 mb-2">Raw JSON State</h2>
          <pre className="text-xs bg-muted p-4 rounded overflow-auto max-h-[800px]">
            {JSON.stringify(thread.messages, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
