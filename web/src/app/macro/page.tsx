"use client";

import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  AlertTriangle, 
  CheckCircle2, 
  Info,
  RefreshCw,
  Globe,
  Gauge,
  BarChart3, 
  Loader2,
  Radar,
  Square,
  Activity,
  Target,
  Terminal as TerminalIcon
} from 'lucide-react';
import React, { useState, useEffect, useRef } from 'react';
import { 
  Sheet, 
  SheetContent, 
  SheetHeader, 
  SheetTitle,
} from "@/components/ui/sheet";
import { Terminal, AnimatedSpan } from "@/components/ui/terminal";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

type SparklinePoint = {
  v: number;
  t: string;
};

type MacroData = {
  label: string;
  name: string;
  ticker: string;
  price: number;
  change: number;
  sortino: number;
  trends: Record<string, string>;
  sparkline?: SparklinePoint[];
  error?: string;
};

const Sparkline = ({ data, color }: { data: SparklinePoint[], color: string }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  
  if (!data || data.length < 2) return <div className="w-16 h-6" />;
  
  const min = Math.min(...data.map(d => d.v));
  const max = Math.max(...data.map(d => d.v));
  const range = max - min || 1;
  const width = 64;
  const height = 24;
  
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((d.v - min) / range) * height;
    return { x, y };
  });

  const polylinePoints = points.map(p => `${p.x},${p.y}`).join(' ');

  return (
    <div className="relative group/sparkline">
      <svg 
        width={width} 
        height={height} 
        className="overflow-visible cursor-crosshair"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const index = Math.round((x / width) * (data.length - 1));
          setHoveredIndex(Math.max(0, Math.min(data.length - 1, index)));
        }}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={polylinePoints}
          className="drop-shadow-[0_0_4px_rgba(192,132,252,0.4)]"
        />
        
        {hoveredIndex !== null && points[hoveredIndex] && (
          <g>
            <line 
              x1={points[hoveredIndex].x} 
              y1={0} 
              x2={points[hoveredIndex].x} 
              y2={height} 
              stroke="white" 
              strokeWidth="0.5" 
              strokeDasharray="2,2" 
              className="opacity-50"
            />
            <circle 
              cx={points[hoveredIndex].x} 
              cy={points[hoveredIndex].y} 
              r="3" 
              fill={color} 
              className="drop-shadow-[0_0_8px_white]"
            />
          </g>
        )}
      </svg>
      
      <AnimatePresence>
        {hoveredIndex !== null && data[hoveredIndex] !== undefined && (
          <motion.div
            initial={{ opacity: 0, y: 5, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.9 }}
            className="absolute -top-20 left-1/2 -translate-x-1/2 z-50 pointer-events-none"
          >
            <div className="bg-white/95 backdrop-blur-sm border border-slate-200 px-3 py-2 rounded-lg flex flex-col items-center gap-1.5 shadow-xl">
              <div className="text-sm text-slate-900 font-black uppercase tracking-tight leading-none whitespace-pre">
                {data[hoveredIndex].t}
              </div>
              <div className="w-full h-px bg-slate-100/80" />
              <div className="flex items-center gap-1">
                <span className="text-slate-400 font-bold text-xs">$</span>
                <span className="text-slate-500 font-bold text-xs tracking-tight leading-none tabular-nums">
                  {data[hoveredIndex].v.toLocaleString(undefined, { 
                    minimumFractionDigits: 2, 
                    maximumFractionDigits: data[hoveredIndex].v < 1 ? 4 : 2 
                  })}
                </span>
              </div>
            </div>
            <div className="w-2 h-2 bg-white border-r border-b border-slate-200 rotate-45 absolute -bottom-1 left-1/2 -translate-x-1/2" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default function MacroDashboard() {
  const [data, setData] = useState<MacroData[]>([]);
  const [prevPrices, setPrevPrices] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [syncCount, setSyncCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [countdown, setCountdown] = useState(60); // 60s Institutional Refresh Cycle
  const [isScanning, setIsScanning] = useState(false);
  const [showConsole, setShowConsole] = useState(false);
  const [scannerLogs, setScannerLogs] = useState<string[]>([]);
  const [strikeCandidates, setStrikeCandidates] = useState<any[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  const stopScanner = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsScanning(false);
    setScannerLogs(prev => [...prev, "--- SCAN TERMINATED BY USER ---"]);
  };

  const startScanner = () => {
    if (isScanning) return;
    
    setIsScanning(true);
    setShowConsole(true);
    setScannerLogs(["[SYSTEM] Initiating Market-Wide Sniper Trawl...", "[SYSTEM] Connecting to backend SSE pipeline..."]);
    setStrikeCandidates([]);

    const es = new EventSource('http://localhost:8000/api/scanner/stream');
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      const payload = JSON.parse(e.data);
      const type = payload.type;
      
      if (type === 'telemetry') {
        setScannerLogs(prev => [...prev, `[TELEMETRY] ${payload.msg || payload.message}`]);
        if (payload.msg === 'Pipeline execution finished cleanly.') {
          es.close();
          setIsScanning(false);
          setScannerLogs(prev => [...prev, "--- SCAN COMPLETED SUCCESSFULLY ---"]);
        }
      } else if (type === 'phase0') {
        setScannerLogs(prev => [...prev, `[PHASE 0] Discovery Pool: ${payload.count} symbols identified.`]);
      } else if (type === 'phase1') {
        setScannerLogs(prev => [...prev, `[PHASE 1] Sortino Static: ${payload.pass_count}/${payload.total_count} passing sniper hurdle.`]);
      } else if (type === 'phase2') {
        const candidates = payload.data || [];
        if (candidates && candidates.length > 0) {
          setStrikeCandidates(prev => {
            const existing = new Set(prev.map((c: any) => c.symbol));
            const filtered = candidates.filter((c: any) => !existing.has(c.symbol));
            const updated = [...prev, ...filtered.map((c: any) => ({
              ...c,
              timestamp: new Date().toLocaleTimeString()
            }))];
            return updated.sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));
          });
          
          candidates.forEach((c: any) => {
            setScannerLogs(prev => [...prev, `[SELECTED] ${c.symbol} (Score: ${c.heat_score || 'N/A'}) - Passing Pulse Filter.`]);
          });
        }
      }
    };

    es.onerror = (err) => {
      console.error("Scanner SSE Error:", err);
      setScannerLogs(prev => [...prev, "[ERROR] Connection lost or server failed to respond."]);
      stopScanner();
    };

    // Cleanup after 5 minutes if not stopped
    setTimeout(() => {
      if (eventSourceRef.current === es) {
        setScannerLogs(prev => [...prev, "[SYSTEM] Scan timeout reached. Closing connection."]);
        stopScanner();
      }
    }, 300000);
  };

  const fetchMacros = async () => {
    setLoading(true);
    setCountdown(60); // Reset countdown on any refresh
    try {
      const response = await fetch('http://localhost:8000/api/research/macros/data');
      if (!response.ok) throw new Error("Failed to fetch");
      const json = await response.json();
      if (Array.isArray(json)) {
        // Save previous prices before updating state
        const prev: Record<string, number> = {};
        data.forEach(item => {
          prev[item.ticker] = item.price;
        });
        setPrevPrices(prev);

        setData(json);
        setLastUpdated(new Date());
        setSyncCount(prev => prev + 1);
      } else {
        console.error("Expected array from API, got:", json);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchMacros();

    // 1s Heartbeat for Countdown & Auto-refresh
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          void fetchMacros();
          return 60;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      clearInterval(timer);
    };
  }, []);

  const SectorLink = ({ name, type }: { name: string, type: 'buyer' | 'seller' | 'vol' }) => (
    <div className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-tighter border ${
      type === 'buyer' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
      type === 'seller' ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' :
      'bg-amber-500/10 border-amber-500/30 text-amber-400'
    }`}>
      {name}
    </div>
  );

  const getTNXIndicator = (yieldValue: number) => {
    const isRestrictive = yieldValue > 4.2;
    return (
      <div className="flex flex-col gap-2">
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${
          isRestrictive ? 'bg-rose-500/10 border-rose-500/30 text-rose-500' : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500'
        }`}>
          {isRestrictive ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
          {isRestrictive ? 'Restrictive' : 'Accommodative'}
        </div>
        <div className="flex flex-wrap gap-1">
          {isRestrictive ? (
            <>
              <SectorLink name="Financials" type="buyer" />
              <SectorLink name="Real Estate" type="seller" />
              <SectorLink name="Technology" type="seller" />
            </>
          ) : (
            <>
              <SectorLink name="Real Estate" type="buyer" />
              <SectorLink name="Technology" type="buyer" />
              <SectorLink name="Financials" type="seller" />
            </>
          )}
        </div>
      </div>
    );
  };

  const getVIXIndicator = (vixValue: number) => {
    let styles = 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500';
    let label = 'Stable (Risk-On)';
    let sectors: { name: string, type: 'buyer' | 'seller' | 'vol' }[] = [
      { name: "Growth", type: "buyer" },
      { name: "Technology", type: "buyer" },
      { name: "Small Cap", type: "buyer" }
    ];
    
    if (vixValue > 25) {
      styles = 'bg-rose-500/10 border-rose-500/30 text-rose-500';
      label = 'High Volatility';
      sectors = [
        { name: "Healthcare", type: "buyer" },
        { name: "Utilities", type: "buyer" },
        { name: "Growth", type: "seller" }
      ];
    } else if (vixValue > 20) {
      styles = 'bg-orange-500/10 border-orange-500/30 text-orange-500';
      label = 'Elevated Risk';
      sectors = [
        { name: "Cons Staples", type: "buyer" },
        { name: "Technology", type: "vol" }
      ];
    } else if (vixValue > 15) {
      styles = 'bg-amber-500/10 border-amber-500/30 text-amber-500';
      label = 'Normal Noise';
      sectors = [
        { name: "Broad Indices", type: "vol" }
      ];
    }

    return (
      <div className="flex flex-col gap-2">
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${styles}`}>
          <Gauge className="w-3 h-3" />
          {label}
        </div>
        <div className="flex flex-wrap gap-1">
          {sectors.map(s => <SectorLink key={s.name} name={s.name} type={s.type} />)}
        </div>
      </div>
    );
  };

  const getDXYIndicator = (dxyValue: number) => {
    let styles = 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500';
    let label = 'Strong Risk Appetite';
    let sectors: { name: string, type: 'buyer' | 'seller' | 'vol' }[] = [
      { name: "Technology", type: "buyer" },
      { name: "Gold", type: "buyer" },
      { name: "Crypto", type: "buyer" }
    ];
    
    if (dxyValue > 105) {
      styles = 'bg-rose-500/10 border-rose-500/30 text-rose-500';
      label = 'Liquidity Crunch';
      sectors = [
        { name: "Multinationals", type: "seller" },
        { name: "Technology", type: "seller" },
        { name: "Emerging Mkts", type: "seller" }
      ];
    } else if (dxyValue > 102) {
      styles = 'bg-orange-500/10 border-orange-500/30 text-orange-500';
      label = 'Bearish Pressure';
      sectors = [
        { name: "Small Cap", type: "buyer" },
        { name: "Technology", type: "seller" }
      ];
    } else if (dxyValue > 100) {
      styles = 'bg-amber-500/10 border-amber-500/30 text-amber-500';
      label = 'Neutral';
      sectors = [
        { name: "Cons Staples", type: "buyer" }
      ];
    }

    return (
      <div className="flex flex-col gap-2">
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${styles}`}>
          <TrendingUp className="w-3 h-3" />
          {label}
        </div>
        <div className="flex flex-wrap gap-1">
          {sectors.map(s => <SectorLink key={s.name} name={s.name} type={s.type} />)}
        </div>
      </div>
    );
  };

  const getAssetIndicator = (item: MacroData) => {
    // 1. Maintain specialized indicators for core macro metrics (TNX, VIX, DXY)
    if (item.label === 'TNX') return getTNXIndicator(item.price);
    if (item.label === 'VIX') return getVIXIndicator(item.price);
    if (item.label === 'DXY') return getDXYIndicator(item.price);

    // 2. Sentiment Logic for Main Indices (SPY, QQQ, IWM)
    if (['SPY', 'QQQ', 'IWM'].includes(item.label)) {
      const isBullish = item.trends?.['1d'] === 'Bullish' || item.sortino > 1.5;
      const isBearish = item.trends?.['1d'] === 'Bearish' || item.sortino < -0.5;
      
      let label = 'Neutral Consolidation';
      let styles = 'bg-slate-500/10 border-slate-500/30 text-slate-400';
      let sectors: { name: string, type: 'buyer' | 'seller' | 'vol' }[] = [{ name: "Index", type: "vol" }];

      if (isBullish) {
        label = 'Strong Accumulation';
        styles = 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
        sectors = [{ name: "Growth", type: "buyer" }, { name: "Momentum", type: "buyer" }];
      } else if (isBearish) {
        label = 'Heavy Distribution';
        styles = 'bg-rose-500/10 border-rose-500/30 text-rose-400';
        sectors = [{ name: "Defensive", type: "buyer" }, { name: "Cash", type: "vol" }];
      }

      return (
        <div className="flex flex-col gap-2">
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-widest ${styles}`}>
            <BarChart3 className="w-3 h-3" />
            {label}
          </div>
          <div className="flex flex-wrap gap-1">
            {sectors.map(s => <SectorLink key={s.name} name={s.name} type={s.type} />)}
          </div>
        </div>
      );
    }

    // 3. Gold (GLD) Sentiment
    if (item.label === 'GLD') {
      const isBullish = item.trends?.['1d'] === 'Bullish';
      return (
        <div className="flex flex-col gap-2">
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-widest ${isBullish ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' : 'bg-slate-500/10 border-slate-500/30 text-slate-500'}`}>
            <RefreshCw className="w-3 h-3" />
            {isBullish ? 'Inflation Hedge' : 'Yield Sensitive'}
          </div>
          <div className="flex flex-wrap gap-1">
            <SectorLink name="Safety" type="buyer" />
            <SectorLink name="Metals" type="vol" />
          </div>
        </div>
      );
    }

    // 4. Bitcoin (BTC) Sentiment
    if (item.label === 'BTC') {
      const isBullish = item.trends?.['1h'] === 'Bullish';
      return (
        <div className="flex flex-col gap-2">
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-widest ${isBullish ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-500' : 'bg-rose-500/10 border-rose-500/30 text-rose-500'}`}>
            <TrendingUp className="w-3 h-3" />
            {isBullish ? 'Risk-On Liquidity' : 'De-risking Phase'}
          </div>
          <div className="flex flex-wrap gap-1">
            <SectorLink name="Web3" type={isBullish ? "buyer" : "vol"} />
            <SectorLink name="Altcoins" type={isBullish ? "buyer" : "seller"} />
          </div>
        </div>
      );
    }

    // 5. Oil (USO) Sentiment
    if (item.label === 'USO') {
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-widest bg-slate-500/10 border-slate-500/30 text-slate-400">
            <Globe className="w-3 h-3" />
            Energy Demand
          </div>
          <div className="flex flex-wrap gap-1">
            <SectorLink name="Commodities" type="vol" />
            <SectorLink name="Energy" type="buyer" />
          </div>
        </div>
      );
    }

    return <span className="text-slate-600 text-xs">—</span>;
  };

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
        <span className="absolute text-[8px] font-black text-blue-400/80 font-mono tracking-tighter">
          {value}
        </span>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#050505] text-slate-200 p-8 font-sans selection:bg-indigo-500/30">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3 text-indigo-400 font-mono text-sm tracking-widest uppercase">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full border border-indigo-500/50 flex items-center justify-center text-[10px] font-black text-indigo-300 bg-indigo-500/10 shadow-[0_0_10px_rgba(99,102,241,0.2)]">
                  M6
                </div>
                <RefreshCountdownRing value={countdown} />
              </div>
              <div className="w-px h-4 bg-white/10 mx-1" />
              <Globe className="w-4 h-4" />
              Global Market Intelligence
            </div>
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
              Macro Sentiment Dashboard
            </h1>
          </div>
          
          <div className="flex items-center gap-6">
            {lastUpdated && (
              <motion.div 
                key={syncCount}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-right"
              >
                <div className="text-[10px] text-slate-500 font-black uppercase tracking-widest flex items-center justify-end gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full bg-emerald-500 ${loading ? 'animate-ping' : ''}`} />
                  Live Sync Active
                </div>
                <div className="text-sm text-white font-mono font-bold">
                  {lastUpdated.toLocaleTimeString()}
                </div>
              </motion.div>
            )}
            <div className="flex items-center gap-3">
              <button 
                onClick={isScanning ? stopScanner : startScanner}
                className={`relative px-4 py-2.5 rounded-xl border transition-all active:scale-95 flex items-center gap-2 group font-mono text-sm tracking-tight ${
                  isScanning 
                    ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20' 
                    : 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/20'
                }`}
              >
                {isScanning ? (
                  <>
                    <div className="relative">
                      <Square className="w-4 h-4 fill-current" />
                      <div className="absolute inset-0 bg-rose-400/20 blur-sm rounded-full animate-pulse" />
                    </div>
                    STOP SCAN
                  </>
                ) : (
                  <>
                    <Radar className="w-4 h-4 group-hover:rotate-90 transition-transform duration-500" />
                    RUN MARKET SCAN
                  </>
                )}
              </button>

              <button 
                onClick={fetchMacros}
                disabled={loading}
                className="relative p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all active:scale-95 disabled:opacity-50 group"
                title="Refresh Macro Data"
              >
                <RefreshCw className={`w-5 h-5 text-slate-400 ${loading ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-500'}`} />
              </button>
              
              {scannerLogs.length > 0 && !showConsole && (
                <button 
                   onClick={() => setShowConsole(true)}
                   className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-500/20 active:scale-95 transition-all"
                   title="View Scanner Console"
                >
                  <Activity className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
        </div>


        {/* Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <motion.div 
            whileHover={{ y: -5 }}
            className="p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-transparent border border-indigo-500/20 backdrop-blur-md shadow-lg"
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-indigo-500/20">
                <Globe className="w-5 h-5 text-indigo-400" />
              </div>
              <h3 className="font-medium text-slate-300">Dollar Strength (DXY)</h3>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Institutional benchmark for liquidity. Below 100 is risk-on (Green). 103-105 indicates bearish pressure (Orange). Above 105 signals a liquidity crunch (Red).
            </p>
          </motion.div>
          
          <motion.div 
            whileHover={{ y: -5 }}
            className="p-6 rounded-2xl bg-gradient-to-br from-purple-500/10 to-transparent border border-purple-500/20 backdrop-blur-md shadow-lg"
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-purple-500/20">
                <Gauge className="w-5 h-5 text-purple-400" />
              </div>
              <h3 className="font-medium text-slate-300">Volatility (VIX)</h3>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Institutional fear gauge. Below 15 is stable (Green). 20-25 denotes elevated risk (Orange). Above 25 signals extreme market panic (Red).
            </p>
          </motion.div>

          <motion.div 
            whileHover={{ y: -5 }}
            className="p-6 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-transparent border border-emerald-500/20 backdrop-blur-md shadow-lg"
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-emerald-500/20">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="font-medium text-slate-300">SMC Trends</h3>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Smart Money Concepts analysis. We evaluate multi-timeframe structure from 15m to 1d to identify institutional trend confluence and reversal zones.
            </p>
          </motion.div>
        </div>

        {/* Main Table */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10 bg-white/[0.02]">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Asset</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Price</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Change</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Sortino (3mo)</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Macro Indicator</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Trend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <AnimatePresence mode="popLayout">
                  {loading && data.length === 0 ? (
                    <motion.tr
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <td colSpan={6} className="px-6 py-20 text-center text-slate-500 font-mono">
                        <div className="flex flex-col items-center gap-4">
                          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                          Indexing global markets...
                        </div>
                      </td>
                    </motion.tr>
                  ) : (
                    data.map((item, idx) => (
                      <motion.tr 
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        key={item.ticker}
                        className={`hover:bg-white/[0.02] transition-colors group ${
                          strikeCandidates.some(c => c.symbol === item.ticker) ? 'bg-emerald-500/[0.08] border-l-2 border-l-emerald-500' : ''
                        }`}
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-4">
                            <div className="flex-shrink-0 opacity-80 ring-1 ring-violet-500/20 rounded p-1 bg-violet-500/5">
                              <Sparkline data={item.sparkline ?? []} color="#c084fc" />
                            </div>
                            <div className="flex flex-col min-w-0">
                              <span className="font-bold text-white text-lg tracking-tight group-hover:text-indigo-300 transition-colors uppercase leading-tight">
                                {item.label}
                              </span>
                              <span className="text-sm text-slate-200 font-semibold mb-1 truncate">{item.name}</span>
                              <span className="text-[10px] text-slate-500 font-mono tracking-wider">{item.ticker}</span>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`font-mono text-lg border-b border-white/5 pb-1 ${
                            (item.change ?? 0) > 0 ? 'text-emerald-400' : (item.change ?? 0) < 0 ? 'text-rose-400' : 'text-white'
                          }`}>
                            {item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {(() => {
                             const lastPrice = prevPrices[item.ticker];
                             const refreshDelta = lastPrice !== undefined ? item.price - lastPrice : 0;
                             const arrowStyle = refreshDelta > 0 ? 'text-emerald-400 font-bold' : refreshDelta < 0 ? 'text-rose-400 font-bold' : 'text-white';
                             
                             return (
                               <div className={`flex items-center gap-1 font-mono text-sm ${arrowStyle}`}>
                                 {refreshDelta > 0 ? <TrendingUp className="w-4 h-4" /> : refreshDelta < 0 ? <TrendingDown className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
                                 <span className={ (item.change ?? 0) > 0 ? 'text-emerald-400/80' : (item.change ?? 0) < 0 ? 'text-rose-400/80' : 'text-slate-400' }>
                                   {(item.change ?? 0) > 0 ? '+' : ''}{(item.change ?? 0).toFixed(2)}%
                                 </span>
                               </div>
                             );
                          })()}
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-white font-bold text-lg font-mono tracking-wider">
                            {(item.sortino ?? 0).toFixed(2)}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {getAssetIndicator(item)}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex gap-2">
                            {['5m', '15m', '1h', '4h', '1d'].map(tf => {
                              const trend = item.trends?.[tf];
                              const isBullish = trend === 'Bullish' || trend === 'Uptrend';
                              const isBearish = trend === 'Bearish' || trend === 'Downtrend';
                              const isWeakBullish = trend === 'Weak Bullish';
                              const isWeakBearish = trend === 'Weak Bearish';
                              
                              return (
                                <motion.div 
                                  whileHover={{ scale: 1.2, zIndex: 10 }}
                                  key={tf}
                                  title={`${tf === '1d' ? '1D' : tf}: ${trend || 'No Data'}`}
                                  className={`w-9 h-9 rounded-lg flex items-center justify-center border shadow-sm transition-all ${
                                    isBullish ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 shadow-emerald-500/10' :
                                    isWeakBullish ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400 shadow-yellow-500/10' :
                                    isWeakBearish ? 'bg-amber-500/20 border-amber-500/40 text-amber-400 shadow-amber-500/10' :
                                    isBearish ? 'bg-rose-500/20 border-rose-500/40 text-rose-400 shadow-rose-500/10' :
                                    'bg-slate-800/50 border-slate-700 text-slate-500'
                                  }`}
                                >
                                  <span className="text-[11px] font-black uppercase tracking-tighter">
                                    {tf === '1d' ? '1D' : tf}
                                  </span>
                                </motion.div>
                              );
                            })}
                          </div>
                        </td>
                      </motion.tr>
                    ))
                  )}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-center gap-4 pt-8 border-t border-white/5">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
             <Info className="w-3.5 h-3.5" />
             DATA SOURCE: YAHOO FINANCE & COBALT SMC ENGINE
          </div>
        </div>
        {/* Scanner Console Sheet */}
        <Sheet open={showConsole} onOpenChange={setShowConsole}>
          <SheetContent side="right" className="bg-[#080808] border-white/10 w-[400px] sm:w-[500px] p-0 flex flex-col">
            <SheetHeader className="p-6 border-b border-white/5">
              <div className="flex items-center justify-between">
                <SheetTitle className="text-white flex items-center gap-3 font-mono tracking-widest text-lg uppercase">
                  <Radar className={`w-5 h-5 text-indigo-400 ${isScanning ? 'animate-spin' : ''}`} />
                  Scanner Console
                </SheetTitle>
                <div className="flex items-center gap-2">
                   <div className={`w-2 h-2 rounded-full ${isScanning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-700'}`} />
                   <span className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">
                     {isScanning ? 'Scanning Live' : 'Scan Idle'}
                   </span>
                </div>
              </div>
            </SheetHeader>
            
            <Tabs defaultValue="console" className="flex-1 flex flex-col overflow-hidden">
              <div className="px-6 border-b border-white/5 bg-white/[0.01]">
                <TabsList className="bg-transparent border-none p-0 gap-6">
                  <TabsTrigger value="console" className="h-12 rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent text-xs uppercase tracking-widest font-bold">
                    Console
                  </TabsTrigger>
                  <TabsTrigger value="strikes" className="h-12 rounded-none border-b-2 border-transparent data-[state=active]:border-emerald-500 data-[state=active]:bg-transparent text-xs uppercase tracking-widest font-bold flex items-center gap-2">
                    Strike List
                    {strikeCandidates.length > 0 && (
                      <span className="bg-emerald-500 text-black text-[9px] px-1.5 py-0.5 rounded-full">
                        {strikeCandidates.length}
                      </span>
                    )}
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="console" className="flex-1 overflow-hidden p-4 m-0">
                <Terminal sequence={false} className="h-full max-h-none max-w-none bg-black/40 border-white/5 shadow-inner">
                  {scannerLogs.map((log, index) => {
                    const isError = log.includes("[ERROR]");
                    const isSelected = log.includes("[SELECTED]");
                    const isSystem = log.includes("[SYSTEM]");
                    
                    let textColor = "text-slate-400";
                    if (isSelected) textColor = "text-emerald-400 font-bold";
                    if (isError) textColor = "text-rose-400";
                    if (isSystem) textColor = "text-indigo-400 italic";

                    return (
                      <AnimatedSpan key={index} className={textColor}>
                        <span className="font-bold opacity-30 mr-2 tabular-nums">{index + 1}</span>
                        {log}
                      </AnimatedSpan>
                    );
                  })}
                  {isScanning && (
                    <AnimatedSpan className="text-indigo-500/50 flex items-center gap-2">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Listening for pulse displacement...
                    </AnimatedSpan>
                  )}
                </Terminal>
              </TabsContent>

              <TabsContent value="strikes" className="flex-1 overflow-auto p-0 m-0">
                {strikeCandidates.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-4 opacity-50">
                    <Target className="w-12 h-12 stroke-[1px]" />
                    <div className="text-xs uppercase tracking-widest font-bold">No candidates identified yet</div>
                  </div>
                ) : (
                  <div className="p-4">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-white/5">
                          <th className="pb-3 text-[10px] uppercase text-slate-500 font-bold">Symbol</th>
                          <th className="pb-3 text-[10px] uppercase text-slate-500 font-bold">Price</th>
                          <th className="pb-3 text-[10px] uppercase text-slate-500 font-bold">Trend</th>
                          <th className="pb-3 text-[10px] uppercase text-slate-500 font-bold text-right">Heat Score</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {strikeCandidates.map((c, i) => (
                          <motion.tr 
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            key={c.symbol + i} 
                            className="group"
                          >
                            <td className="py-3">
                              <div className="flex items-center gap-3">
                                <div className="flex-shrink-0 opacity-80 ring-1 ring-emerald-500/20 rounded p-0.5 bg-emerald-500/5">
                                  <Sparkline data={c.sparkline ?? []} color="#10b981" />
                                </div>
                                <div className="flex flex-col">
                                  <div className="flex items-center gap-2">
                                    <span className="text-emerald-400 font-bold text-sm">{c.symbol}</span>
                                    {c.cvd_warning && (
                                      <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-rose-500/20 border border-rose-500/50 text-[9px] font-bold text-rose-400 uppercase tracking-tighter" title="BULL TRAP: Negative CVD Divergence (Volume eroding on Higher Highs)">
                                        <AlertTriangle className="w-3 h-3 animate-pulse" />
                                        TRAP
                                      </div>
                                    )}
                                  </div>
                                  <span className="text-[9px] text-slate-600 font-mono">{c.timestamp}</span>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 text-white font-mono text-xs">
                              ${c.price?.toFixed(2) || '---'}
                            </td>
                            <td className="py-3">
                              <div className="flex gap-1">
                                {['5m', '15m', '1h', '4h', '1d'].map(tf => {
                                  const trend = c.trends?.[tf];
                                  const isBullish = trend === 'Bullish' || trend === 'Uptrend';
                                  const isBearish = trend === 'Bearish' || trend === 'Downtrend';
                                  const isWeakBullish = trend === 'Weak Bullish';
                                  const isWeakBearish = trend === 'Weak Bearish';
                                  
                                  return (
                                    <div 
                                      key={tf}
                                      title={`${tf === '1d' ? '1D' : tf}: ${trend || 'No Data'}`}
                                      className={`w-5 h-5 rounded flex items-center justify-center border text-[7px] font-black uppercase tracking-tighter transition-all ${
                                        isBullish ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 shadow-emerald-500/10' :
                                        isWeakBullish ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400 shadow-yellow-500/10' :
                                        isWeakBearish ? 'bg-amber-500/20 border-amber-500/40 text-amber-400 shadow-amber-500/10' :
                                        isBearish ? 'bg-rose-500/20 border-rose-500/40 text-rose-400 shadow-rose-500/10' :
                                        'bg-slate-800/50 border-slate-700 text-slate-500'
                                      }`}
                                    >
                                      {tf === '1d' ? '1D' : tf}
                                    </div>
                                  );
                                })}
                              </div>
                            </td>
                            <td className="py-3 text-right">
                              {(() => {
                                const score = c.heat_score || 0;
                                let colorClass = "bg-slate-500/10 border-slate-500/20 text-slate-400";
                                if (score >= 95) colorClass = "bg-amber-500/10 border-amber-500/30 text-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.2)]"; // S
                                else if (score >= 82) colorClass = "bg-fuchsia-500/10 border-fuchsia-500/30 text-fuchsia-400 shadow-[0_0_10px_rgba(217,70,239,0.2)]"; // A
                                else if (score >= 65) colorClass = "bg-indigo-500/10 border-indigo-500/30 text-indigo-400"; // B
                                else if (score >= 50) colorClass = "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"; // C
 
                                return (
                                  <div className="flex flex-col items-end gap-1">
                                    <span className={`px-2 py-0.5 border rounded text-[10px] font-bold font-mono ${colorClass}`}>
                                      {score} {c.grade ? `(${c.grade})` : ''}
                                    </span>
                                  </div>
                                );
                              })()}
                            </td>
                          </motion.tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </TabsContent>
            </Tabs>

            <div className="p-6 border-t border-white/5 bg-white/[0.02]">
              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-500 font-mono">
                   SESSION STRIKES: <span className="text-emerald-400 font-bold">{strikeCandidates.length}</span>
                </div>
                <button 
                  onClick={() => {
                    setScannerLogs([]);
                    setStrikeCandidates([]);
                  }}
                  className="text-[10px] text-slate-600 hover:text-slate-400 font-bold uppercase tracking-widest transition-colors"
                >
                  Clear Session
                </button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}
