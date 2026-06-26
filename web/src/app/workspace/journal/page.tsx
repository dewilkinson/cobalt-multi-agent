"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  BookOpen, 
  Calendar, 
  Save, 
  Sparkles, 
  Sliders, 
  Smile, 
  Moon, 
  Compass, 
  Zap, 
  ShieldCheck, 
  Award,
  ChevronRight,
  RefreshCw
} from "lucide-react";
import { toast } from "sonner";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Markdown } from "@/components/cobalt-multi-agent/markdown";
import { cn } from "@/lib/utils";

export default function JournalPage() {
  const [dateStr, setDateStr] = useState<string>(() => {
    const today = new Date();
    const offset = today.getTimezoneOffset();
    const localDate = new Date(today.getTime() - offset * 60 * 1000);
    return localDate.toISOString().split("T")[0] ?? "";
  });

  const [grades, setGrades] = useState({
    prep: 3,
    sleep: 3,
    mood: 3,
    energy: 3,
    confidence: 3,
    performance: "C"
  });

  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showGradesPane, setShowGradesPane] = useState(true);

  const [preview, setPreview] = useState({
    trader_notes: "",
    self_assessment: ""
  });

  const panelRef = useRef<any>(null);

  useEffect(() => {
    // Force the grades pane to expand to default 33% width on mount
    const timer = setTimeout(() => {
      console.log("DEBUG: panelRef.current is:", panelRef.current);
      if (panelRef.current) {
        console.log("DEBUG: panelRef.current keys:", Object.keys(panelRef.current));
        console.log("DEBUG: before resize, size is:", panelRef.current.getSize());
        panelRef.current.resize("33%");
        console.log("DEBUG: after resize, size is:", panelRef.current.getSize());
        setShowGradesPane(true);
      }
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  const handleToggleGradesPane = () => {
    if (panelRef.current) {
      if (panelRef.current.isCollapsed()) {
        panelRef.current.expand();
        setShowGradesPane(true);
      } else {
        panelRef.current.collapse();
        setShowGradesPane(false);
      }
    }
  };

  // Track the last saved/loaded baseline to determine if any edits have occurred
  const [lastSavedData, setLastSavedData] = useState<{
    grades: typeof grades;
    markdown: string;
  } | null>(null);

  const hasChanges = lastSavedData ? (
    markdown !== lastSavedData.markdown ||
    grades.prep !== lastSavedData.grades.prep ||
    grades.sleep !== lastSavedData.grades.sleep ||
    grades.mood !== lastSavedData.grades.mood ||
    grades.energy !== lastSavedData.grades.energy ||
    grades.confidence !== lastSavedData.grades.confidence ||
    grades.performance !== lastSavedData.grades.performance
  ) : false;

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

  const fetchJournalData = async (date: string) => {
    setLoading(true);
    try {
      let loadedMarkdown = "";
      let loadedGrades = {
        prep: 3,
        sleep: 3,
        mood: 3,
        energy: 3,
        confidence: 3,
        performance: "C"
      };

      // 1. Fetch journal content and grades
      const response = await fetch(`${apiUrl}/vli/journal/${date}`);
      if (response.ok) {
        const data = await response.json();
        loadedMarkdown = data.markdown || "";
        setMarkdown(loadedMarkdown);
        if (data.grades) {
          loadedGrades = {
            prep: data.grades.prep ?? 3,
            sleep: data.grades.sleep ?? 3,
            mood: data.grades.mood ?? 3,
            energy: data.grades.energy ?? 3,
            confidence: data.grades.confidence ?? 3,
            performance: data.grades.performance ?? "C"
          };
          setGrades(loadedGrades);
        } else {
          setGrades(loadedGrades);
        }
      } else {
        setMarkdown("");
        setGrades(loadedGrades);
      }

      setLastSavedData({ grades: loadedGrades, markdown: loadedMarkdown });
      
      // 2. Fetch synthesized preview
      const previewResponse = await fetch(`${apiUrl}/vli/journal/${date}/preview`);
      if (previewResponse.ok) {
        const previewData = await previewResponse.json();
        setPreview({
          trader_notes: previewData.trader_notes || "",
          self_assessment: previewData.self_assessment || ""
        });
      } else {
        setPreview({ trader_notes: "", self_assessment: "" });
      }
    } catch (error) {
      console.error("Failed to load journal:", error);
      toast.error("Failed to load journal data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchJournalData(dateStr);
  }, [dateStr]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${apiUrl}/vli/journal/${dateStr}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grades, markdown })
      });

      if (response.ok) {
        toast.success("Daily journal saved successfully");
        setLastSavedData({ grades, markdown }); // Reset changes baseline
        
        // Refetch preview to show LLM synthesis
        const previewResponse = await fetch(`${apiUrl}/vli/journal/${dateStr}/preview`);
        if (previewResponse.ok) {
          const previewData = await previewResponse.json();
          setPreview({
            trader_notes: previewData.trader_notes || "",
            self_assessment: previewData.self_assessment || ""
          });
        }
      } else {
        toast.error("Failed to save daily journal");
      }
    } catch (error) {
      console.error("Failed to save journal:", error);
      toast.error("Network error saving journal");
    } finally {
      setSaving(false);
    }
  };

  const getSliderColor = (val: number) => {
    if (val <= 2) return "bg-red-500";
    if (val === 3) return "bg-yellow-500";
    return "bg-emerald-500";
  };

  const getGradeBadgeColor = (grade: string) => {
    if (grade.startsWith("A")) return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    if (grade.startsWith("B")) return "bg-blue-500/10 text-blue-400 border-blue-500/30";
    if (grade.startsWith("C")) return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
    return "bg-red-500/10 text-red-400 border-red-500/30";
  };

  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100 font-sans">
      {/* Header Bar */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center space-x-3">
          <div className="rounded-lg bg-indigo-600/20 p-2 text-indigo-400 border border-indigo-500/20">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">Journalling Module</h1>
            <p className="text-xs text-zinc-400">Record subjective mindset data & synthesize end-of-day reports</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm">
            <Calendar className="h-4 w-4 text-zinc-400" />
            <input 
              type="date" 
              value={dateStr}
              onChange={(e) => setDateStr(e.target.value)}
              className="bg-transparent border-none text-zinc-200 focus:outline-none focus:ring-0 text-sm font-medium selection:bg-zinc-800 cursor-pointer"
            />
          </div>

          <button
            onClick={() => void fetchJournalData(dateStr)}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2 text-zinc-400 hover:text-white transition-colors"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>

          <button
            onClick={handleToggleGradesPane}
            className={`flex items-center space-x-2 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
              showGradesPane 
                ? "bg-zinc-900 text-zinc-100 border-zinc-700" 
                : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:text-white"
            }`}
          >
            <Sliders className="h-4 w-4" />
            <span>Grades Pane</span>
          </button>

          <button
            onClick={handleSave}
            disabled={saving || loading || !hasChanges}
            className="flex items-center space-x-2 rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white shadow-md hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-zinc-900 disabled:text-zinc-500 border disabled:border-zinc-800 transition-colors"
          >
            <Save className="h-4 w-4" />
            <span>{saving ? "Saving..." : "Save Journal"}</span>
          </button>
        </div>
      </header>

      {/* Main Workspace layout */}
      <div className="flex flex-1 overflow-hidden">
        <ResizablePanelGroup direction="horizontal" id="journal-panel-group">
          {/* Left Hand side: Markdown raw notes editor */}
          <ResizablePanel defaultSize="67%" minSize="30%" id="journal-left-panel">
            <div className="flex flex-1 flex-col p-6 h-full">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold tracking-wider uppercase text-zinc-400">Raw Notes (Markdown)</h2>
                <span className="text-xs text-zinc-500">Edit notes written throughout the session</span>
              </div>
              
              {loading ? (
                <div className="flex flex-1 items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
                </div>
              ) : (
                <textarea
                  value={markdown}
                  onChange={(e) => setMarkdown(e.target.value)}
                  className="flex-1 w-full bg-zinc-900/20 text-zinc-200 border border-zinc-800 rounded-lg p-5 font-mono text-sm leading-relaxed focus:outline-none focus:border-zinc-700 resize-none overflow-y-auto placeholder-zinc-600 focus:ring-0 selection:bg-zinc-800"
                  placeholder="Write raw session candidates, morning observations, risk factors, or intraday feelings here..."
                />
              )}
            </div>
          </ResizablePanel>

          <ResizableHandle
            withHandle
            className={cn(
              "bg-zinc-850 hover:bg-zinc-700 w-1 transition-colors",
              !showGradesPane && "pointer-events-none opacity-0"
            )}
          />
          
          {/* Floating/Adjustable Right Pane for grades and preview */}
          <ResizablePanel
            ref={panelRef}
            collapsible={true}
            defaultSize="33%"
            minSize="20%"
            maxSize="60%"
            id="journal-right-panel"
            className="bg-zinc-950"
          >
            <div className="flex flex-col h-full overflow-y-auto border-l border-zinc-800">
              {/* Self Assessment Card */}
              <div className="p-6 border-b border-zinc-800 bg-zinc-900/10">
                <div className="mb-6 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <ShieldCheck className="h-4 w-4 text-indigo-400" />
                    <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Self Assessment Scoring</h3>
                  </div>
                </div>

                <div className="space-y-5">
                  {/* Prep Score */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="flex items-center space-x-1.5 text-zinc-400">
                        <Compass className="h-3.5 w-3.5" />
                        <span>Prep / Homework</span>
                      </span>
                      <span className="text-zinc-200">{grades.prep} / 5</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={grades.prep}
                      onChange={(e) => setGrades({ ...grades, prep: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                  </div>

                  {/* Sleep Score */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="flex items-center space-x-1.5 text-zinc-400">
                        <Moon className="h-3.5 w-3.5" />
                        <span>Sleep Quality</span>
                      </span>
                      <span className="text-zinc-200">{grades.sleep} / 5</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={grades.sleep}
                      onChange={(e) => setGrades({ ...grades, sleep: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                  </div>

                  {/* Mood Score */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="flex items-center space-x-1.5 text-zinc-400">
                        <Smile className="h-3.5 w-3.5" />
                        <span>Mindset / Mood</span>
                      </span>
                      <span className="text-zinc-200">{grades.mood} / 5</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={grades.mood}
                      onChange={(e) => setGrades({ ...grades, mood: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                  </div>

                  {/* Energy Score */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="flex items-center space-x-1.5 text-zinc-400">
                        <Zap className="h-3.5 w-3.5" />
                        <span>Physical Energy</span>
                      </span>
                      <span className="text-zinc-200">{grades.energy} / 5</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={grades.energy}
                      onChange={(e) => setGrades({ ...grades, energy: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                  </div>

                  {/* Confidence Score */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="flex items-center space-x-1.5 text-zinc-400">
                        <Award className="h-3.5 w-3.5" />
                        <span>Trade Confidence</span>
                      </span>
                      <span className="text-zinc-200">{grades.confidence} / 5</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={grades.confidence}
                      onChange={(e) => setGrades({ ...grades, confidence: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                  </div>

                  {/* Execution Letter Grade */}
                  <div className="space-y-2 pt-2">
                    <label className="text-xs font-semibold text-zinc-400">Self-Graded Execution Performance</label>
                    <select
                      value={grades.performance}
                      onChange={(e) => setGrades({ ...grades, performance: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-zinc-700 cursor-pointer"
                    >
                      <option value="A+">A+ (Perfect Execution, Full Rules Adherence)</option>
                      <option value="A">A (Excellent, No major drift)</option>
                      <option value="A-">A- (Great setup selection)</option>
                      <option value="B+">B+ (Adhered to stops but chased slightly)</option>
                      <option value="B">B (Good recovery, moderate discipline)</option>
                      <option value="B-">B- (A few minor over-trades)</option>
                      <option value="C+">C+ (Struggled with patience)</option>
                      <option value="C">C (Average, execution drift present)</option>
                      <option value="C-">C- (Slightly chased breakouts)</option>
                      <option value="D+">D+ (Notable over-trading/FOMO)</option>
                      <option value="D">D (Poor discipline, ignored rules)</option>
                      <option value="D-">D- (Severe execution drift/chasing)</option>
                      <option value="F">F (Rules broken, high emotional tilt)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* AI Synthesis Preview Pane */}
              <div className="p-6 flex-1 bg-zinc-950">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="h-4 w-4 text-amber-400 animate-pulse" />
                    <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">AI Synthesis Preview</h3>
                  </div>
                  {saving && (
                    <div className="flex items-center space-x-1.5 text-xs text-amber-400 font-semibold animate-pulse">
                      <RefreshCw className="h-3 w-3 animate-spin" />
                      <span>Resynthesizing...</span>
                    </div>
                  )}
                </div>

                {loading ? (
                  <div className="flex h-32 items-center justify-center">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
                  </div>
                ) : preview.trader_notes || preview.self_assessment ? (
                  <div className={cn("space-y-6 transition-all duration-300 relative", saving && "opacity-40 grayscale blur-[1px] pointer-events-none")}>
                    {/* Trader Notes Preview */}
                    {preview.trader_notes && (
                      <div className="space-y-2">
                        <div className="flex items-center text-xs font-semibold text-zinc-400">
                          <ChevronRight className="h-3 w-3 text-zinc-600" />
                          <span>POLISHED TRADER NOTES</span>
                        </div>
                        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300 font-sans leading-relaxed">
                          <Markdown className="prose-sm max-w-none">{preview.trader_notes}</Markdown>
                        </div>
                      </div>
                    )}

                    {/* Self Assessment Preview */}
                    {preview.self_assessment && (
                      <div className="space-y-2">
                        <div className="flex items-center text-xs font-semibold text-zinc-400">
                          <ChevronRight className="h-3 w-3 text-zinc-600" />
                          <span>COACH SELF ASSESSMENT & PATTERNS</span>
                        </div>
                        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300 font-sans leading-relaxed">
                          <Markdown className="prose-sm max-w-none">{preview.self_assessment}</Markdown>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex h-40 flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 text-center p-6 text-zinc-500">
                    <Sparkles className="h-8 w-8 text-zinc-600 mb-2" />
                    <p className="text-xs">No end-of-day report synthesized yet.</p>
                    <p className="text-[10px] text-zinc-600 mt-1">Press "Save Journal" to trigger AI synthesis preview.</p>
                  </div>
                )}
              </div>
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </div>
  );
}
