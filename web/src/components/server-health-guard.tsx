"use client";

import React, { useState, useEffect, useRef } from "react";
import { getBackendBaseURL, getSystemMode } from "@/core/config";
import { CLIENT_VERSION } from "@/core/config/version";

export function ServerHealthGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"connecting" | "restarting" | "connected" | "failed">("connecting");
  const [seconds, setSeconds] = useState(0);
  const [reason, setReason] = useState("");
  const [visible, setVisible] = useState(true);

  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const restartAttempted = useRef(false);

  const startHandshake = () => {
    setStatus("connecting");
    setSeconds(0);
    setReason("");
    setVisible(true);
    restartAttempted.current = false;

    if (getSystemMode() === "LOCAL") {
      fetch("/api/system/startup", { method: "POST" }).catch(() => {});
    }

    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(async () => {
      setSeconds((s) => {
        if (s >= 45) {
          setStatus((prev) => {
            if (prev !== "connected") {
              setReason(restartAttempted.current ? "Version Mismatch (Restart Failed)" : "Connection Timeout");
              return "failed";
            }
            return prev;
          });
          return s;
        }
        return s + 1;
      });

      try {
        const res = await fetch(`${getBackendBaseURL()}/api/health`, {
          signal: AbortSignal.timeout(2000),
        });
        
        if (res.ok) {
          const data = await res.json();
          if (data.version === CLIENT_VERSION) {
            if (intervalRef.current) clearInterval(intervalRef.current);
            setStatus("connected");
            setTimeout(() => setVisible(false), 1000);
          } else if (!restartAttempted.current) {
            restartAttempted.current = true;
            setStatus("restarting");
            await fetch(`${getBackendBaseURL()}/api/system/restart`, { method: "POST" });
          }
        }
      } catch (err) {
        // Just keep polling until timeout
      }
    }, 1000);
  };

  useEffect(() => {
    startHandshake();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  if (!visible) {
    return <>{children}</>;
  }

  const isFailed = status === "failed";
  const isConnected = status === "connected";

  let title = `Connecting to Server (${seconds}s)`;
  if (status === "restarting") title = `Restarting Server (${seconds}s)`;
  if (isConnected) title = "Connected!";
  if (isFailed) title = `Failed to Connect`;

  return (
    <>
      {/* 
        We still render children in the background but disabled/inert 
        so the app layout visually exists behind the modal. 
      */}
      <div className="pointer-events-none opacity-20 blur-sm w-full h-full">
        {children}
      </div>

      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md">
        <div className="flex w-full max-w-md flex-col items-center justify-center rounded-xl border border-white/10 bg-[#0a0a0a] p-8 shadow-2xl">
          <div className="mb-4 text-[17px] font-bold uppercase tracking-[0.3px] text-[#8b949e]">
            {title}
          </div>
          
          {isFailed && (
            <div className="mb-6 text-sm text-red-400 font-mono">
              Reason: {reason}
            </div>
          )}

          {!isFailed && (
            <div className="relative h-1 w-full overflow-hidden rounded-full bg-white/10 mt-2 mb-4">
              <div 
                className="absolute inset-y-0 left-0"
                style={{
                  width: isConnected ? "100%" : "70%",
                  background: isConnected 
                    ? "var(--emerald-green, #3fb950)" 
                    : "linear-gradient(90deg, transparent 0%, var(--cobalt-blue, #58a6ff) 50%, transparent 100%)",
                  boxShadow: isConnected 
                    ? "0 0 15px rgba(63, 185, 80, 0.4)"
                    : "0 0 15px rgba(88, 166, 255, 0.4)",
                  animation: isConnected ? "none" : "sweep 1.2s ease-in-out infinite",
                  transition: "width 0.3s ease, background 0.3s ease",
                  transform: isConnected ? "translateX(0)" : "translateX(-100%)"
                }}
              />
            </div>
          )}

          {isFailed && (
            <div className="flex w-full gap-3 mt-4">
              <button 
                onClick={() => setVisible(false)}
                className="flex-1 rounded-md border border-white/20 bg-transparent py-2 text-sm text-white hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={startHandshake}
                className="flex-1 rounded-md bg-[#58a6ff] py-2 text-sm font-semibold text-black hover:bg-[#79b8ff] transition-colors"
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="pointer-events-none fixed bottom-3 right-4 z-[999999] select-none font-mono text-[11px] text-white/20">
        Ver. {CLIENT_VERSION}
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes sweep {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(140%); }
        }
      `}} />
    </>
  );
}
