import React from 'react';

/**
 * PipIndicator: A high-fidelity, color-coded 10-pip activity indicator.
 * 
 * @param value - Nominal value (0-100) representing the percentage fill.
 * @param autonomic - If true, the widget will independently bounce and flutter its value.
 */
export interface PipIndicatorProps {
  value: number;
}

export const PipIndicator = ({ value }: PipIndicatorProps) => {
  const currentLevel = Math.ceil(Math.max(0, Math.min(100, value)) / 10);

  const getPipColor = (pipIdx: number): string => {
    if (pipIdx <= 3) return 'bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.3)]';
    if (pipIdx <= 6) return 'bg-amber-400 shadow-[0_0_4px_rgba(251,191,36,0.3)]';
    if (pipIdx <= 8) return 'bg-orange-500 shadow-[0_0_4px_rgba(249,115,22,0.3)]';
    return 'bg-rose-500 shadow-[0_0_4px_rgba(244,63,94,0.3)]';
  };

  return (
    <div className="flex gap-0.5 min-w-[120px] items-center h-full">
      {Array.from({ length: 10 }).map((_, pIdx) => {
        const pNum = pIdx + 1;
        const isActive = pNum <= currentLevel;
        return (
          <div 
            key={pIdx} 
            className={`w-2 h-3.5 rounded-sm transition-all duration-300 ${isActive ? getPipColor(pNum) : 'bg-white/5'}`} 
          />
        );
      })}
    </div>
  );
};
