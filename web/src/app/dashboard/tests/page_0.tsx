import TestDashboard from "~/components/dashboard/TestDashboard";

export default function TestHarnessPage() {
  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-10 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-indigo-500/20 flex items-center justify-center border border-indigo-500/50">
            <span className="text-indigo-400 font-bold text-xl">V</span>
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Cobalt VLI Test Harness</h1>
            <p className="text-xs text-slate-400">Environment: VLI_TEST_MODE Evaluator</p>
          </div>
        </div>
      </header>
      
      <main className="flex-1 p-6">
        <TestDashboard />
      </main>
    </div>
  );
}
