"use client";

import { motion, AnimatePresence } from 'framer-motion';
import { 
  ExternalLink, 
  RefreshCw, 
  Cpu, 
  Zap, 
  Clock, 
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  TrendingUp
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

type CreditData = {
  monthly: string | number;
  additional: string | number;
  total: string | number;
  status?: string;
  error?: string;
};

const CreditCardComponent = ({ 
  title, 
  value, 
  icon: Icon, 
  colorClass, 
  delay = 0 
}: { 
  title: string; 
  value: string | number; 
  icon: React.ElementType; 
  colorClass: string;
  delay?: number;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="relative group h-full"
  >
    <div className={`absolute inset-0 bg-gradient-to-br ${colorClass} opacity-10 blur-xl rounded-3xl transition-opacity group-hover:opacity-20`} />
    <div className="relative h-full p-8 rounded-3xl bg-white/[0.03] border border-white/10 backdrop-blur-xl flex flex-col justify-between overflow-hidden shadow-2xl">
      <div className="flex items-center justify-between mb-8">
        <div className={`p-3 rounded-2xl bg-white/5 border border-white/10 ${(colorClass.split(' ')[1] ?? 'to-indigo-500').replace('to-', 'text-')}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div className="flex h-1.5 w-1.5 rounded-full bg-white/20" />
      </div>
      
      <div>
        <h3 className="text-slate-500 font-bold text-xs uppercase tracking-widest mb-2">{title}</h3>
        <div className="flex items-baseline gap-2">
          <span className="text-5xl font-black text-white tracking-tighter">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </span>
          <span className="text-slate-500 text-sm font-bold uppercase tracking-widest">Credits</span>
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-white/5 flex items-center justify-between">
        <span className="text-[10px] text-slate-500 font-mono tracking-widest uppercase">Live Allocation</span>
        <ChevronRight className="w-4 h-4 text-slate-600" />
      </div>
    </div>
  </motion.div>
);

export default function StudioDashboard() {
  const [credits, setCredits] = useState<CreditData | null>(null);
  const [memory, setMemory] = useState<{used: number, limit: number, percent: number} | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [isOpening, setIsOpening] = useState(false);
  const [countdown, setCountdown] = useState(60); // 60s Institutional Refresh Cycle

  const fetchCredits = async () => {
    setLoading(true);
    try {
      // Fetch Credits
      const resCredits = await fetch('http://localhost:8000/api/studio/credits');
      if (resCredits.ok) {
        const data = await resCredits.json();
        setCredits(data);
      }

      // Fetch Context Memory
      const resContext = await fetch('http://localhost:8000/api/studio/context');
      if (resContext.ok) {
        const data = await resContext.json();
        setMemory(data);
      }

      setLastSync(new Date());
    } catch (err) {
      console.error(err);
      setCredits(prev => ({ 
        monthly: prev?.monthly ?? 'Error', 
        additional: prev?.additional ?? 'Error', 
        total: prev?.total ?? 'Error',
        error: "Sync Failed. Is the backend server running?"
      }));
    } finally {
      setLoading(false);
    }
  };

  const openStudio = async () => {
    setIsOpening(true);
    try {
      await fetch('http://localhost:8000/api/studio/login');
    } catch (err) {
      console.error(err);
    } finally {
      setIsOpening(false);
    }
  };

  useEffect(() => {
    void fetchCredits();
    
    // 1s Heartbeat for Countdown & Auto-refresh (60s Cycle)
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          void fetchCredits();
          return 60;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      clearInterval(timer);
    };
  }, []);

  const RefreshCountdownRing = ({ value }: { value: number }) => {
    const size = 24;
    const stroke = 2;
    const center = size / 2;
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const progress = (value / 60) * circumference;

    return (
      <div className="relative flex items-center justify-center w-6 h-6" title={`Next refresh in ${value}s`}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            className="text-white/5"
          />
          <motion.circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#60a5fa"
            strokeWidth={stroke}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - progress }}
            transition={{ duration: 1, ease: "linear" }}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute text-[8px] font-black text-blue-400 font-mono tracking-tighter">
          {value}
        </span>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#020202] text-slate-200 p-6 md:p-12 font-sans selection:bg-indigo-500/30 overflow-hidden relative">
      {/* Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-8 mb-16">
          <div className="space-y-4">
            <motion.div 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3"
            >
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full border border-indigo-500/50 flex items-center justify-center text-[10px] font-black text-indigo-300 bg-indigo-500/10 shadow-[0_0_10px_rgba(99,102,241,0.2)]">
                  V1
                </div>
                <RefreshCountdownRing value={countdown} />
              </div>
              <div className="w-px h-4 bg-white/10 mx-1" />
              <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400">
                <Cpu className="w-5 h-5" />
              </div>
              <span className="text-xs font-black uppercase tracking-[0.3em] text-indigo-400/80">Project Cobalt VLI</span>
            </motion.div>
            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-5xl md:text-7xl font-black text-white tracking-tighter leading-none"
            >
              AI Studio <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">Context Monitor</span>
            </motion.h1>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button 
              onClick={openStudio}
              disabled={isOpening}
              className="flex items-center gap-2 px-6 py-4 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all font-bold text-sm active:scale-95 disabled:opacity-50"
            >
              {isOpening ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
              🔑 Login to Studio
            </button>
            <button 
              onClick={fetchCredits}
              disabled={loading}
              className="relative p-4 rounded-2xl bg-indigo-500 text-white hover:bg-indigo-400 transition-all active:scale-95 disabled:opacity-50 group overflow-hidden shadow-[0_0_20px_rgba(99,102,241,0.4)]"
            >
              <RefreshCw className={`w-6 h-6 z-10 relative ${loading ? 'animate-spin' : ''}`} />
              <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
            </button>
          </div>
        </header>

        {/* Status Bar */}
        <div className="mb-12 space-y-2">
          <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-slate-500 px-1">
            <div className="flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${loading ? 'bg-indigo-400 animate-pulse' : 'bg-emerald-400'}`} />
              {loading ? 'Analyzing Session Logs' : 'Stream Ready'}
            </div>
            <div className="flex items-center gap-2">
               <Clock className="w-3 h-3 text-indigo-400" />
               Next Refresh in {countdown}s
            </div>
          </div>
          <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
            <motion.div 
              className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
              initial={{ width: 0 }}
              animate={{ width: `${( (60 - countdown) / 60) * 100}%` }}
              transition={{ ease: "linear" }}
            />
          </div>
        </div>

        {/* Error Alert */}
        <AnimatePresence>
          {credits?.error && (
            <motion.div 
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: 'auto', marginBottom: 32 }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm font-medium flex items-center gap-3 overflow-hidden"
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              {credits.error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
          <CreditCardComponent 
            title="Monthly Credits"
            value={credits?.monthly ?? '...'}
            icon={Clock}
            colorClass="from-indigo-600 to-indigo-900"
            delay={0.1}
          />
          <CreditCardComponent 
            title="Additional Credits"
            value={credits?.additional ?? '...'}
            icon={Zap}
            colorClass="from-purple-600 to-purple-900"
            delay={0.2}
          />
          <CreditCardComponent 
            title="Total Combined"
            value={credits?.total ?? '...'}
            icon={TrendingUp}
            colorClass="from-emerald-600 to-emerald-900"
            delay={0.3}
          />
        </div>

        {/* Context Memory Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="relative group mb-12"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-transparent blur-xl rounded-3xl" />
          <div className="relative p-10 rounded-3xl bg-white/[0.03] border border-white/10 backdrop-blur-xl shadow-2xl overflow-hidden">
              <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-blue-500/20 text-blue-400">
                      <Cpu className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Active Context Memory</span>
                  </div>
                  <div className="flex items-baseline gap-3">
                    <h2 className="text-6xl font-black text-white tracking-tighter">
                      {memory ? (memory.used / 1000).toFixed(1) : '...'}K
                    </h2>
                    <span className="text-slate-500 font-bold uppercase text-lg">/ 1.0 M Tokens</span>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2 text-right">
                  <span className="text-4xl font-black text-white tracking-tight">{memory?.percent ?? 0}%</span>
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Memory Consumed</span>
                </div>
              </div>

              <div className="mt-10 h-3 w-full bg-white/5 rounded-full overflow-hidden border border-white/5 p-0.5">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${memory?.percent ?? 0}%` }}
                  className="h-full bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 rounded-full shadow-[0_0_15px_rgba(59,130,246,0.5)]"
                />
              </div>
              
              <div className="mt-6 flex items-center justify-between text-[10px] uppercase font-bold tracking-widest text-slate-600">
                <span>Buffer Min: 1 Token</span>
                <span>Buffer Max: 1,048,576 Tokens (Gemini Flash)</span>
              </div>
          </div>
        </motion.div>

        {/* Footer Meta */}
        <footer className="mt-20 pt-8 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-4 text-slate-500 font-mono text-[10px] uppercase tracking-widest">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              Vision + Context Synchronized
            </div>
            <div className="flex items-center gap-2 text-indigo-400">
              <Clock className="w-3.5 h-3.5" />
              Last Update: {lastSync ? lastSync.toLocaleTimeString() : 'Awaiting Data'}
            </div>
          </div>
          <div>Cobalt Multiagent - VLI Studio Module</div>
        </footer>
      </div>
    </div>
  );
}
