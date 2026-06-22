"use client";

import React from 'react';
import { motion } from 'framer-motion';

export type DynamicTableHeader = string;

export type DynamicTableRow = (string | number | { type: string; value: any })[];

interface DynamicTableProps {
  headers: DynamicTableHeader[];
  rows: DynamicTableRow[];
  id?: string;
}

export const DynamicTable: React.FC<DynamicTableProps> = ({ headers, rows, id }) => {
  const renderSparkline = (values: number[]) => {
    if (!values || values.length < 2) return null;
    
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const width = 64;
    const height = 16;
    
    const points = values.map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    }).join(' ');

    const isUp = values[values.length - 1]! >= values[0]!;
    const colorClass = isUp ? 'stroke-emerald-400' : 'stroke-rose-400';
    const fillClass = isUp ? 'fill-emerald-400/10' : 'fill-rose-400/10';
    const gradientId = `gradient-${Math.random().toString(36).substr(2, 9)}`;

    return (
      <div className="w-16 h-4">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={isUp ? '#34d399' : '#fb7185'} stopOpacity="0.2" />
              <stop offset="100%" stopColor="transparent" />
            </linearGradient>
          </defs>
          <path
            d={`M 0 ${height} ${points.split(' ').map((p, i) => (i === 0 ? `M ${p}` : `L ${p}`)).join(' ')} L ${width} ${height} Z`}
            fill={`url(#${gradientId})`}
          />
          <motion.polyline
            fill="none"
            className={`${colorClass}`}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={points}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 1.5, ease: "easeInOut" }}
            style={{ filter: `drop-shadow(0 0 4px ${isUp ? 'rgba(52, 211, 153, 0.4)' : 'rgba(251, 113, 133, 0.4)'})` }}
          />
        </svg>
      </div>
    );
  };

  const PriceCell = ({ value, initialVelocity = 'neutral' }: { value: string, initialVelocity?: 'up' | 'down' | 'neutral' }) => {
    const prevValueRef = React.useRef<string>(value);
    const [velocity, setVelocity] = React.useState<'up' | 'down' | 'neutral'>(initialVelocity);

    React.useEffect(() => {
      // Extract numeric value from string (e.g., "$170.50" -> 170.5)
      const parse = (v: string) => parseFloat(v.replace(/[$,%]/g, ''));
      const prev = parse(prevValueRef.current);
      const curr = parse(value);

      if (!isNaN(prev) && !isNaN(curr)) {
        if (curr > prev) setVelocity('up');
        else if (curr < prev) setVelocity('down');
        else setVelocity('neutral');
      }

      prevValueRef.current = value;
    }, [value]);

    const colorClass = velocity === 'up' ? 'text-emerald-400' : velocity === 'down' ? 'text-rose-400' : 'text-white';
    const bgClass = velocity === 'up' ? 'bg-emerald-500/10' : velocity === 'down' ? 'bg-rose-500/10' : 'bg-transparent';

    return (
      <motion.span 
        animate={velocity !== 'neutral' ? { scale: [1, 1.05, 1] } : {}}
        className={`font-mono font-bold px-1.5 py-0.5 rounded transition-all duration-500 ${colorClass} ${bgClass}`}
      >
        {value}
      </motion.span>
    );
  };

  const renderCell = (cell: any, idx: number, row: any[]) => {
    if (typeof cell === 'object' && cell !== null) {
      if (cell.type === 'indicator') {
        const value = Number(cell.value) || 0;
        return (
          <div className="flex items-center gap-1.5" key={`cell-${idx}`}>
            {[...Array(5)].map((_, i) => (
              <div 
                key={i}
                className={`w-2 h-2 rounded-full transform transition-all duration-300 ${
                  i < value 
                    ? 'bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.6)]' 
                    : 'bg-slate-700/50'
                }`}
              />
            ))}
          </div>
        );
      }
      
      if (cell.type === 'sparkline') {
        return <div key={`cell-${idx}`}>{renderSparkline(cell.value)}</div>;
      }

      if (cell.type === 'text') {
        const val = Number(cell.value);
        const color = val >= 0 ? 'text-emerald-400' : 'text-rose-400';
        return <span className={`font-mono font-medium ${color}`} key={`cell-${idx}`}>{val > 0 ? '+' : ''}{cell.value}%</span>;
      }
    }

    if (typeof cell === 'number') {
      return <span className="font-mono text-indigo-300" key={`cell-${idx}`}>{cell.toLocaleString()}</span>;
    }

    // Special handling for Price column (Index 2)
    if (idx === 2 && typeof cell === 'string') {
      let initialVel: 'up' | 'down' | 'neutral' = 'neutral';
      if (row && row[5] && row[5].type === 'sparkline' && Array.isArray(row[5].value) && row[5].value.length >= 2) {
        const sparkArr = row[5].value;
        const curr = sparkArr[sparkArr.length - 1];
        const prev = sparkArr[sparkArr.length - 2];
        if (curr > prev) initialVel = 'up';
        else if (curr < prev) initialVel = 'down';
      }
      return <PriceCell key={`cell-${idx}`} value={cell} initialVelocity={initialVel} />;
    }

    return <span className="text-slate-300" key={`cell-${idx}`}>{String(cell)}</span>;
  };

  return (
    <div id={id} className="w-full overflow-hidden border border-white/10 bg-black/20 backdrop-blur-md rounded-xl shadow-2xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[9pt] border-collapse">
          <thead>
            <tr className="bg-white/5 border-b border-white/10">
              {headers.map((header, i) => (
                <th key={i} className="px-2 py-0.5 font-black uppercase tracking-widest text-slate-500 whitespace-nowrap">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((row, i) => (
              <motion.tr 
                key={i}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="hover:bg-white/[0.02] transition-colors"
              >
                {row.map((cell, j) => (
                  <td key={j} className="px-2 py-0.5 whitespace-nowrap align-middle">
                    {renderCell(cell, j, row)}
                  </td>
                ))}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
