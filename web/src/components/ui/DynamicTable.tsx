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
  const renderSparkline = (values: any[]) => {
    if (!values || values.length < 2) return null;
    
    // Parse values supporting both plain numbers and { v, is_prev } objects, dropping nulls
    const parsedValues = values
      .map((item, idx) => {
        if (item === null || item === undefined) return null;
        if (typeof item === 'number') {
          return { v: item, isPrev: false, originalIndex: idx };
        }
        if (typeof item === 'object' && 'v' in item) {
          return { v: Number(item.v), isPrev: !!item.is_prev, originalIndex: idx };
        }
        return null;
      })
      .filter((item): item is { v: number; isPrev: boolean; originalIndex: number } => item !== null);

    if (parsedValues.length === 0) return null;

    const validFloatValues = parsedValues.map(item => item.v);
    const min = Math.min(...validFloatValues);
    const max = Math.max(...validFloatValues);
    const range = max - min || 1;
    const width = 64;
    const height = 16;
    
    // Map parsed values to coordinates based on their original index positions
    const pointsArray = parsedValues.map(item => {
      const x = (item.originalIndex / (values.length - 1)) * width;
      const y = height - ((item.v - min) / range) * height;
      return { x, y, str: `${x},${y}`, isPrev: item.isPrev };
    });

    if (pointsArray.length === 0) return null;

    // Split points into previous session and current session arrays
    const prevPoints: typeof pointsArray = [];
    const currPoints: typeof pointsArray = [];
    
    pointsArray.forEach((p) => {
      if (p.isPrev) {
        prevPoints.push(p);
      } else {
        // Connect the current segment seamlessly to the end of the previous segment
        if (currPoints.length === 0 && prevPoints.length > 0) {
          currPoints.push(prevPoints[prevPoints.length - 1]!);
        }
        currPoints.push(p);
      }
    });

    // Determine direction from latest valid value to first valid value
    const latestVal = parsedValues[parsedValues.length - 1]?.v;
    const firstVal = parsedValues[0]?.v;
    const isUp = latestVal !== undefined && firstVal !== undefined ? latestVal >= firstVal : true;
    
    const colorClass = isUp ? 'stroke-emerald-400' : 'stroke-rose-400';
    const prevColorClass = isUp ? 'stroke-emerald-600' : 'stroke-rose-600';
    
    const fillClass = isUp ? 'fill-emerald-400/10' : 'fill-rose-400/10';
    const gradientId = `gradient-${Math.random().toString(36).substr(2, 9)}`;

    // Build fill path starting at floor of first point, tracing line, dropping to floor of last point, and closing
    const firstPoint = pointsArray[0]!;
    const lastPoint = pointsArray[pointsArray.length - 1]!;
    const fillPathD = `M ${firstPoint.x} ${height} ` + 
                      pointsArray.map(p => `L ${p.str}`).join(' ') + 
                      ` L ${lastPoint.x} ${height} Z`;

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
            d={fillPathD}
            fill={`url(#${gradientId})`}
          />
          {prevPoints.length >= 2 && (
            <motion.polyline
              fill="none"
              className={`${prevColorClass}`}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={prevPoints.map(p => p.str).join(' ')}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 0.6 }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
            />
          )}
          {currPoints.length >= 2 && (
            <motion.polyline
              fill="none"
              className={`${colorClass}`}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={currPoints.map(p => p.str).join(' ')}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
              style={{ filter: `drop-shadow(0 0 4px ${isUp ? 'rgba(52, 211, 153, 0.4)' : 'rgba(251, 113, 133, 0.4)'})` }}
            />
          )}
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
