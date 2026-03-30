'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Predefined layout map for standard nodes
const layoutMap: Record<string, { x: number; y: number }> = {
  'agent-planner': { x: 250, y: 50 },
  'agent-researcher': { x: 50, y: 200 },
  'agent-writer': { x: 450, y: 200 },
  'storage-global': { x: 250, y: 400 },
  'storage-local': { x: 450, y: 400 },
  'storage-obsidian': { x: 50, y: 400 },
  'vault-grid': { x: 50, y: 520 },
};

const FOLDERS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"];

export default function NetworkVisualizer() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [logs, setLogs] = useState<{ id: number; text: string }[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [gridState, setGridState] = useState<Record<number, string>>({});
  const [residentCells, setResidentCells] = useState<Set<number>>(new Set());
  const logCounter = useRef(0);

  const addLog = (text: string) => {
    logCounter.current += 1;
    setLogs((prev) => [...prev, { id: logCounter.current, text }]);
  };

  const startSimulation = useCallback(() => {
    setIsSimulating(true);
    setNodes([]);
    setEdges([]);
    setLogs([]);
    setGridState({});
    setResidentCells(new Set());

    const eventSource = new EventSource('http://localhost:8001/api/simulate');

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'init') {
        // Initialize graph nodes
        const initialNodes = data.nodes.map((n: any) => ({
          id: n.id,
          position: layoutMap[n.id] || { x: Math.random() * 500, y: Math.random() * 500 },
          data: { label: n.label },
          style: {
            background: n.type === 'agent' ? '#3B82F6' : '#10B981',
            color: '#fff',
            border: '1px solid #222',
            borderRadius: '8px',
            padding: '10px 15px',
            fontWeight: 'bold',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          },
        }));

        // Add the Grid Node
        initialNodes.push({
          id: 'vault-grid',
          type: 'default',
          position: layoutMap['vault-grid'],
          data: { label: 'Vault Physical Mirror (IO Grid)' },
          style: {
            background: '#18181b',
            color: '#a1a1aa',
            border: '1px solid #3f3f46',
            borderRadius: '12px',
            padding: '20px',
            width: 440,
            fontSize: '12px',
          },
        });

        setNodes(initialNodes);
        addLog('Initialized Network Grid');
      } 
      else if (data.type === 'event') {
        const timestamp = new Date().toLocaleTimeString();
        addLog(`[${data.action.toUpperCase()}] ${data.message}`);

        // Update Grid State if it's a folder-based operation
        const folderMatch = data.message.match(/(Alpha|Beta|Gamma|Delta|Epsilon)/);
        if (folderMatch) {
            const folder = folderMatch[0];
            const folderIndex = FOLDERS.indexOf(folder);
            const slotMatch = data.message.match(/(update|segment|cache|final|Slot)_(\d+)/) || data.message.match(/Slot (\d+)/);
            const iteration = slotMatch ? parseInt(slotMatch[1] === 'Slot' ? slotMatch[2] : slotMatch[2]) : Math.floor(Math.random() * 50);
            const cellIndex = (folderIndex * 10) + (iteration % 10);
            
            let color = '#27272a'; // Default
            if (data.action === 'write') {
                color = '#F59E0B'; // Amber
                setResidentCells(prev => new Set(prev).add(cellIndex));
            }
            else if (data.result === 'hit') color = '#10B981'; // Emerald
            else if (data.result === 'miss') color = '#EF4444'; // Crimson

            setGridState(prev => ({ ...prev, [cellIndex]: color }));
            
            // Clear flash after 1.5s
            setTimeout(() => {
                setGridState(prev => {
                    const newState = { ...prev };
                    delete newState[cellIndex];
                    return newState;
                });
            }, 1500);
        }

        if (data.action === 'read' || data.action === 'write') {
          // Flash nodes to indicate activity
          setNodes((nds) =>
            nds.map((node) => {
              if (node.id === data.source || node.id === data.target) {
                return {
                  ...node,
                  style: { ...node.style, background: '#F59E0B' }, // Flash orange
                };
              }
              // Reset other nodes to default color
              return {
                ...node,
                style: {
                  ...node.style,
                  background: node.id === 'vault-grid' ? '#18181b' : (node.id.startsWith('agent') ? '#3B82F6' : '#10B981'),
                },
              };
            })
          );

          // Add animating Edge showing data transfer
          const newEdge = {
            id: `e-${data.source}-${data.target}-${Date.now()}`,
            source: data.source,
            target: data.target,
            animated: true,
            label: data.action,
            style: { stroke: data.action === 'write' ? '#EF4444' : '#6366F1', strokeWidth: 3 },
            markerEnd: { type: MarkerType.ArrowClosed },
          };
          setEdges((eds) => addEdge(newEdge as unknown as Edge, eds));
          
          // Remove old edges to keep canvas clean
          setTimeout(() => {
            setEdges((eds) => eds.filter(e => e.id !== newEdge.id));
          }, 2000);
        }
      } 
      else if (data.type === 'complete') {
        addLog('Simulation Finished Successfully.');
        eventSource.close();
        setIsSimulating(false);
      }
      else if (data.type === 'error') {
        addLog(`[ERROR] ${data.message}`);
        eventSource.close();
        setIsSimulating(false);
      }
    };

    eventSource.onerror = (err) => {
      addLog('Connection to Simulation Backend Lost.');
      eventSource.close();
      setIsSimulating(false);
    };
  }, [setNodes, setEdges]);

  // Handle node style reset logic
  useEffect(() => {
    if (!isSimulating) {
        setNodes(nds => nds.map(n => ({
            ...n,
            style: {
                ...n.style,
                background: n.id === 'vault-grid' ? '#18181b' : (n.id.startsWith('agent') ? '#3B82F6' : '#10B981'),
            }
        })));
    }
  }, [isSimulating, setNodes]);

  return (
    <div className="flex h-screen w-full bg-zinc-950 text-white overflow-hidden">
      {/* Visualizer Canvas */}
      <div className="flex-grow h-full relative border-r border-zinc-800">
        <h1 className="absolute top-4 left-4 z-10 text-2xl font-bold tracking-tight text-white drop-shadow-md">
          Agent Storage Flow Matrix
        </h1>
        
        <button
          onClick={startSimulation}
          disabled={isSimulating}
          className={`absolute top-4 right-4 z-10 px-6 py-2 rounded-md font-semibold transition-all ${
            isSimulating ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg'
          }`}
        >
          {isSimulating ? 'Simulating...' : 'Run Storage Mock'}
        </button>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          colorMode="dark"
        >
          <Background color="#333" gap={16} />
          <Controls />
          <MiniMap nodeColor={(n) => (n.style?.background as string) || '#fff'} />
          
          {/* Activity Grid Overlay via Node Data or custom component */}
          <div className="absolute bottom-10 left-10 z-20 pointer-events-none">
             <div className="bg-zinc-900/90 p-8 rounded-2xl border border-zinc-600 backdrop-blur-md shadow-[0_0_50px_rgba(0,0,0,0.5)]">
                <div className="flex items-center justify-between mb-6 gap-8">
                    <span className="text-sm font-bold uppercase tracking-[0.2em] text-zinc-400">Physical Vault Mirror [I/O Grid]</span>
                    <div className="flex gap-4">
                        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]"></div><span className="text-xs font-bold text-zinc-300">WRITE</span></div>
                        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div><span className="text-xs font-bold text-zinc-300">HIT</span></div>
                        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]"></div><span className="text-xs font-bold text-zinc-300">MISS</span></div>
                    </div>
                </div>
                <div className="grid grid-rows-5 grid-cols-10 gap-2 mt-2">
                    {Array.from({ length: 50 }).map((_, i) => (
                        <div 
                            key={i} 
                            style={{ 
                                background: gridState[i] || (residentCells.has(i) ? '#3f3f46' : '#18181b'),
                                border: residentCells.has(i) ? '1px solid #52525b' : '1px solid #27272a'
                            }}
                            className="w-6 h-6 rounded-md transition-all duration-700 shadow-inner"
                        ></div>
                    ))}
                </div>
             </div>
          </div>
        </ReactFlow>
      </div>

      {/* Live Event Log */}
      <div className="w-96 flex flex-col h-full bg-zinc-900 border-l border-zinc-800 shadow-xl">
        <div className="p-4 border-b border-zinc-800 bg-zinc-950">
          <h2 className="text-lg font-semibold text-emerald-400">Activity Telemetry</h2>
          <p className="text-xs text-zinc-500 mt-1">Real-time IO event stream</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm">
          {logs.map((log) => (
            <div key={log.id} className="p-2 bg-zinc-800/50 rounded border border-zinc-700/50 animate-in fade-in slide-in-from-right-2">
              <span className="text-zinc-400">{new Date().toLocaleTimeString()}</span>
              <span className="block mt-1 text-zinc-200">{log.text}</span>
            </div>
          ))}
          {logs.length === 0 && !isSimulating && (
            <div className="text-center text-zinc-500 mt-10 italic">Awaiting Simulation...</div>
          )}
        </div>
      </div>
    </div>
  );
}
