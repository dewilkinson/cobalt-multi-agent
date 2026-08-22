/**
 * Miris Performance Overlay & API Call Profiler
 * Real-time WebGL Renderer Details & API Call Profiling HUD for Miris Model Viewer
 * 
 * Author: Antigravity / Google DeepMind Team
 * Version: 1.0.0
 */

(function (global) {
  'use strict';

  if (global.__MIRIS_PERF_OVERLAY__) {
    console.log('[MirisPerfOverlay] Already initialized.');
    global.__MIRIS_PERF_OVERLAY__.toggle();
    return;
  }

  // --- WebGL Context & Method Profiler ---
  const webglStats = {
    drawCalls: 0,
    triangles: 0,
    points: 0,
    lines: 0,
    useProgramCalls: 0,
    bindTextureCalls: 0,
    bindBufferCalls: 0,
    bufferDataCalls: 0,
    texImageCalls: 0,
    uniformCalls: 0,
    shaderCompiles: 0,
    apiTimeMs: 0,
    totalFrameCalls: 0,
    methodCounts: {},
    methodTimes: {},
    resetFrame() {
      this.drawCalls = 0;
      this.triangles = 0;
      this.points = 0;
      this.lines = 0;
      this.useProgramCalls = 0;
      this.bindTextureCalls = 0;
      this.bindBufferCalls = 0;
      this.bufferDataCalls = 0;
      this.texImageCalls = 0;
      this.uniformCalls = 0;
      this.shaderCompiles = 0;
      this.apiTimeMs = 0;
      this.totalFrameCalls = 0;
      this.methodCounts = {};
      this.methodTimes = {};
    }
  };

  const webglHistory = [];
  const MAX_HISTORY = 60;

  // Intercept WebGL Context Creation
  const origGetContext = HTMLCanvasElement.prototype.getContext;
  const activeGLContexts = new Set();

  function wrapGLContext(gl) {
    if (!gl || gl.__wrappedForMirisPerf__) return gl;
    gl.__wrappedForMirisPerf__ = true;
    activeGLContexts.add(gl);

    const wrapMethod = (name, trackerFn) => {
      const orig = gl[name];
      if (typeof orig !== 'function') return;
      gl[name] = function (...args) {
        const t0 = performance.now();
        const res = orig.apply(this, args);
        const dt = performance.now() - t0;
        
        webglStats.totalFrameCalls++;
        webglStats.apiTimeMs += dt;
        webglStats.methodCounts[name] = (webglStats.methodCounts[name] || 0) + 1;
        webglStats.methodTimes[name] = (webglStats.methodTimes[name] || 0) + dt;

        if (trackerFn) trackerFn(gl, args);
        return res;
      };
    };

    // Wrap Draw Calls
    wrapMethod('drawElements', (gl, args) => {
      webglStats.drawCalls++;
      const count = args[1] || 0;
      const mode = args[0];
      if (mode === gl.TRIANGLES) webglStats.triangles += Math.floor(count / 3);
      else if (mode === gl.TRIANGLE_STRIP || mode === gl.TRIANGLE_FAN) webglStats.triangles += Math.max(0, count - 2);
      else if (mode === gl.POINTS) webglStats.points += count;
      else if (mode === gl.LINES) webglStats.lines += Math.floor(count / 2);
    });

    wrapMethod('drawArrays', (gl, args) => {
      webglStats.drawCalls++;
      const count = args[2] || 0;
      const mode = args[0];
      if (mode === gl.TRIANGLES) webglStats.triangles += Math.floor(count / 3);
      else if (mode === gl.POINTS) webglStats.points += count;
      else if (mode === gl.LINES) webglStats.lines += Math.floor(count / 2);
    });

    if (gl.drawElementsInstanced) {
      wrapMethod('drawElementsInstanced', (gl, args) => {
        webglStats.drawCalls++;
        const count = args[1] || 0;
        const primCount = args[4] || 1;
        webglStats.triangles += Math.floor(count / 3) * primCount;
      });
    }

    if (gl.drawArraysInstanced) {
      wrapMethod('drawArraysInstanced', (gl, args) => {
        webglStats.drawCalls++;
        const count = args[2] || 0;
        const primCount = args[3] || 1;
        webglStats.triangles += Math.floor(count / 3) * primCount;
      });
    }

    // State & Texture / Shader Methods
    wrapMethod('useProgram', () => webglStats.useProgramCalls++);
    wrapMethod('bindTexture', () => webglStats.bindTextureCalls++);
    wrapMethod('bindBuffer', () => webglStats.bindBufferCalls++);
    wrapMethod('bufferData', () => webglStats.bufferDataCalls++);
    wrapMethod('texImage2D', () => webglStats.texImageCalls++);
    wrapMethod('compileShader', () => webglStats.shaderCompiles++);

    // Uniform setters
    ['uniform1f', 'uniform1i', 'uniform2fv', 'uniform3fv', 'uniform4fv', 'uniformMatrix4fv'].forEach(uName => {
      wrapMethod(uName, () => webglStats.uniformCalls++);
    });

    return gl;
  }

  HTMLCanvasElement.prototype.getContext = function (type, flags) {
    const gl = origGetContext.call(this, type, flags);
    if (gl && (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl')) {
      wrapGLContext(gl);
    }
    return gl;
  };

  // --- Network API Profiler ---
  const networkStats = {
    activeRequests: 0,
    totalRequests: 0,
    bytesTransferred: 0,
    recentRequests: [],
    addRequest(req) {
      this.totalRequests++;
      this.bytesTransferred += req.size || 0;
      this.recentRequests.unshift(req);
      if (this.recentRequests.length > 20) this.recentRequests.pop();
    }
  };

  // Intercept fetch
  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const t0 = performance.now();
    const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || 'fetch';
    networkStats.activeRequests++;
    try {
      const res = await origFetch.apply(this, args);
      const dt = performance.now() - t0;
      networkStats.activeRequests = Math.max(0, networkStats.activeRequests - 1);
      
      const clone = res.clone();
      let size = 0;
      try {
        const blob = await clone.blob();
        size = blob.size;
      } catch (e) {
        size = 0;
      }
      
      networkStats.addRequest({
        type: 'fetch',
        url: url.length > 60 ? '...' + url.slice(-57) : url,
        fullUrl: url,
        status: res.status,
        duration: Math.round(dt),
        size,
        timestamp: Date.now()
      });
      return res;
    } catch (err) {
      networkStats.activeRequests = Math.max(0, networkStats.activeRequests - 1);
      throw err;
    }
  };

  // --- UI HUD Component ---
  class MirisPerfHUD {
    constructor() {
      this.visible = true;
      this.minimized = false;
      this.activeTab = 'overview';
      this.fpsHistory = new Array(60).fill(60);
      this.frameTimeHistory = new Array(60).fill(16.6);
      this.lastFrameTime = performance.now();
      this.frameCount = 0;
      this.currentFps = 60;
      this.currentFrameTimeMs = 16.6;
      
      this.createDOM();
      this.setupListeners();
      this.startLoop();
    }

    createDOM() {
      const overlay = document.createElement('div');
      overlay.id = 'miris-perf-overlay';
      overlay.innerHTML = `
        <style>
          #miris-perf-overlay {
            position: fixed;
            top: 16px;
            right: 16px;
            width: 380px;
            max-height: 90vh;
            background: rgba(12, 16, 24, 0.88);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            color: #e2e8f0;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 12px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
            z-index: 999999;
            overflow: hidden;
            user-select: none;
            transition: width 0.2s ease, max-height 0.2s ease;
          }
          #miris-perf-overlay.minimized {
            width: 220px;
            max-height: 42px;
          }
          .mpo-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            background: rgba(255, 255, 255, 0.04);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            cursor: move;
          }
          .mpo-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: #38bdf8;
            font-size: 13px;
          }
          .mpo-badge {
            background: #0284c7;
            color: #fff;
            font-size: 9px;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
          }
          .mpo-controls {
            display: flex;
            gap: 6px;
          }
          .mpo-btn {
            background: rgba(255, 255, 255, 0.08);
            border: none;
            color: #94a3b8;
            width: 22px;
            height: 22px;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            transition: all 0.15s;
          }
          .mpo-btn:hover {
            background: rgba(255, 255, 255, 0.18);
            color: #fff;
          }
          .mpo-tabs {
            display: flex;
            background: rgba(0, 0, 0, 0.2);
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          }
          .mpo-tab {
            flex: 1;
            padding: 8px 4px;
            text-align: center;
            background: transparent;
            border: none;
            color: #64748b;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
            border-bottom: 2px solid transparent;
          }
          .mpo-tab:hover {
            color: #cbd5e1;
          }
          .mpo-tab.active {
            color: #38bdf8;
            border-bottom-color: #38bdf8;
            background: rgba(56, 189, 248, 0.06);
          }
          .mpo-body {
            padding: 12px;
            overflow-y: auto;
            max-height: 480px;
          }
          .mpo-metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-bottom: 12px;
          }
          .mpo-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 8px 10px;
          }
          .mpo-card-label {
            color: #64748b;
            font-size: 10px;
            font-weight: 500;
            margin-bottom: 2px;
          }
          .mpo-card-val {
            font-size: 15px;
            font-weight: 700;
            color: #f8fafc;
            font-family: monospace;
          }
          .mpo-card-val.accent-green { color: #4ade80; }
          .mpo-card-val.accent-cyan { color: #38bdf8; }
          .mpo-card-val.accent-amber { color: #fbbf24; }
          .mpo-card-val.accent-purple { color: #c084fc; }
          
          canvas.mpo-graph {
            width: 100%;
            height: 48px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 6px;
            margin-bottom: 12px;
          }
          .mpo-section-title {
            font-size: 11px;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 10px 0 6px 0;
          }
          .mpo-list {
            list-style: none;
            padding: 0;
            margin: 0;
          }
          .mpo-list-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px dotted rgba(255, 255, 255, 0.06);
            font-family: monospace;
          }
          .mpo-list-item:last-child { border-bottom: none; }
          .mpo-bar-container {
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            height: 6px;
            overflow: hidden;
            margin-top: 2px;
          }
          .mpo-bar-fill {
            height: 100%;
            background: #38bdf8;
            border-radius: 3px;
            transition: width 0.15s ease;
          }
          .mpo-req-item {
            font-size: 10px;
            padding: 6px;
            background: rgba(0,0,0,0.25);
            border-radius: 4px;
            margin-bottom: 4px;
          }
          .mpo-req-url {
            color: #38bdf8;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .mpo-req-meta {
            display: flex;
            justify-content: space-between;
            color: #64748b;
            margin-top: 2px;
          }
        </style>

        <div class="mpo-header" id="mpo-header">
          <div class="mpo-title">
            <span>MIRIS PROFILER</span>
            <span class="mpo-badge">WebGL / API</span>
          </div>
          <div class="mpo-controls">
            <button class="mpo-btn" id="mpo-export-btn" title="Export Trace Data">💾</button>
            <button class="mpo-btn" id="mpo-min-btn" title="Minimize">—</button>
            <button class="mpo-btn" id="mpo-close-btn" title="Close Overlay (HotKey ~)">✕</button>
          </div>
        </div>

        <div class="mpo-tabs" id="mpo-tabs">
          <button class="mpo-tab active" data-tab="overview">OVERVIEW</button>
          <button class="mpo-tab" data-tab="renderer">RENDERER</button>
          <button class="mpo-tab" data-tab="api">API PROFILER</button>
          <button class="mpo-tab" data-tab="network">NETWORK</button>
          <button class="mpo-tab" data-tab="miris">MIRIS ENGINE</button>
        </div>

        <div class="mpo-body" id="mpo-body">
          <!-- Overview Tab -->
          <div class="mpo-tab-content" id="mpo-tab-overview">
            <div class="mpo-metrics-grid">
              <div class="mpo-card">
                <div class="mpo-card-label">FRAMERATE</div>
                <div class="mpo-card-val accent-green" id="mpo-val-fps">60 FPS</div>
              </div>
              <div class="mpo-card">
                <div class="mpo-card-label">FRAME TIME</div>
                <div class="mpo-card-val accent-cyan" id="mpo-val-frametime">16.6 ms</div>
              </div>
              <div class="mpo-card">
                <div class="mpo-card-label">DRAW CALLS / FRM</div>
                <div class="mpo-card-val accent-amber" id="mpo-val-drawcalls">0</div>
              </div>
              <div class="mpo-card">
                <div class="mpo-card-label">TRIANGLES / FRM</div>
                <div class="mpo-card-val accent-purple" id="mpo-val-triangles">0</div>
              </div>
            </div>

            <div class="mpo-card-label">FPS & FRAME DURATION TRACE</div>
            <canvas class="mpo-graph" id="mpo-fps-graph" width="350" height="48"></canvas>

            <div class="mpo-metrics-grid">
              <div class="mpo-card">
                <div class="mpo-card-label">JS HEAP MEMORY</div>
                <div class="mpo-card-val" id="mpo-val-jsmem">N/A</div>
              </div>
              <div class="mpo-card">
                <div class="mpo-card-label">WEBGL API TIME</div>
                <div class="mpo-card-val" id="mpo-val-apitime">0.0 ms</div>
              </div>
            </div>
          </div>

          <!-- Renderer Tab -->
          <div class="mpo-tab-content" id="mpo-tab-renderer" style="display:none;">
            <div class="mpo-section-title">THREE.JS / WEBGL DETAILS</div>
            <ul class="mpo-list" id="mpo-renderer-list">
              <li class="mpo-list-item"><span>Active Draw Calls:</span><strong id="mpo-r-calls">0</strong></li>
              <li class="mpo-list-item"><span>Triangles:</span><strong id="mpo-r-triangles">0</strong></li>
              <li class="mpo-list-item"><span>Points:</span><strong id="mpo-r-points">0</strong></li>
              <li class="mpo-list-item"><span>Lines:</span><strong id="mpo-r-lines">0</strong></li>
              <li class="mpo-list-item"><span>Geometries Allocated:</span><strong id="mpo-r-geoms">0</strong></li>
              <li class="mpo-list-item"><span>Textures Allocated:</span><strong id="mpo-r-textures">0</strong></li>
              <li class="mpo-list-item"><span>Shader Programs:</span><strong id="mpo-r-programs">0</strong></li>
            </ul>

            <div class="mpo-section-title">HARDWARE DRIVER & CONTEXT</div>
            <ul class="mpo-list" id="mpo-gl-driver-list">
              <li class="mpo-list-item"><span>GPU Vendor:</span><strong id="mpo-gl-vendor">Detecting...</strong></li>
              <li class="mpo-list-item"><span>Renderer:</span><strong id="mpo-gl-renderer">Detecting...</strong></li>
              <li class="mpo-list-item"><span>Max Texture Size:</span><strong id="mpo-gl-maxtex">N/A</strong></li>
              <li class="mpo-list-item"><span>WebGL Version:</span><strong id="mpo-gl-ver">N/A</strong></li>
            </ul>
          </div>

          <!-- API Profiler Tab -->
          <div class="mpo-tab-content" id="mpo-tab-api" style="display:none;">
            <div class="mpo-section-title">WEBGL CALL COUNTS (CURRENT FRAME)</div>
            <div id="mpo-api-calls-breakdown">
              <p style="color:#64748b; font-style:italic;">Intercepting WebGL context calls...</p>
            </div>
          </div>

          <!-- Network Tab -->
          <div class="mpo-tab-content" id="mpo-tab-network" style="display:none;">
            <div class="mpo-metrics-grid">
              <div class="mpo-card">
                <div class="mpo-card-label">ACTIVE REQS</div>
                <div class="mpo-card-val accent-cyan" id="mpo-net-active">0</div>
              </div>
              <div class="mpo-card">
                <div class="mpo-card-label">TOTAL DATA</div>
                <div class="mpo-card-val accent-green" id="mpo-net-bytes">0 KB</div>
              </div>
            </div>
            <div class="mpo-section-title">RECENT API & STREAM REQUESTS</div>
            <div id="mpo-net-list">
              <p style="color:#64748b; font-style:italic;">No network requests captured yet.</p>
            </div>
          </div>

          <!-- Miris Engine Tab -->
          <div class="mpo-tab-content" id="mpo-tab-miris" style="display:none;">
            <div class="mpo-section-title">MIRIS SCENE NODES</div>
            <ul class="mpo-list">
              <li class="mpo-list-item"><span>&lt;miris-scene&gt; Elements:</span><strong id="mpo-miris-scenes">0</strong></li>
              <li class="mpo-list-item"><span>&lt;miris-stream&gt; Nodes:</span><strong id="mpo-miris-streams">0</strong></li>
              <li class="mpo-list-item"><span>Active LOD Splat Meshes:</span><strong id="mpo-miris-lods">0</strong></li>
              <li class="mpo-list-item"><span>Camera Fit:</span><strong id="mpo-miris-camfit">none</strong></li>
              <li class="mpo-list-item"><span>Exposure:</span><strong id="mpo-miris-exposure">1.0</strong></li>
            </ul>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);
      this.dom = overlay;
    }

    setupListeners() {
      // Dragging
      const header = this.dom.querySelector('#mpo-header');
      let isDragging = false, startX, startY, initialLeft, initialTop;

      header.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('mpo-btn')) return;
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = this.dom.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;
        this.dom.style.right = 'auto';
      });

      window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        this.dom.style.left = `${initialLeft + dx}px`;
        this.dom.style.top = `${initialTop + dy}px`;
      });

      window.addEventListener('mouseup', () => { isDragging = false; });

      // Minimize & Close Buttons
      this.dom.querySelector('#mpo-min-btn').addEventListener('click', () => {
        this.minimized = !this.minimized;
        this.dom.classList.toggle('minimized', this.minimized);
      });

      this.dom.querySelector('#mpo-close-btn').addEventListener('click', () => {
        this.toggle();
      });

      // Export Button
      this.dom.querySelector('#mpo-export-btn').addEventListener('click', () => {
        this.exportData();
      });

      // Tabs switching
      const tabs = this.dom.querySelectorAll('.mpo-tab');
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          tabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          this.activeTab = tab.getAttribute('data-tab');

          const contents = this.dom.querySelectorAll('.mpo-tab-content');
          contents.forEach(c => c.style.display = 'none');
          const target = this.dom.querySelector(`#mpo-tab-${this.activeTab}`);
          if (target) target.style.display = 'block';
        });
      });

      // Hotkey ~ or Ctrl+Shift+P to toggle
      window.addEventListener('keydown', (e) => {
        if (e.key === '`' || e.key === '~' || (e.ctrlKey && e.shiftKey && e.key === 'P')) {
          this.toggle();
        }
      });
    }

    toggle() {
      this.visible = !this.visible;
      this.dom.style.display = this.visible ? 'block' : 'none';
    }

    startLoop() {
      const update = () => {
        const now = performance.now();
        const dt = now - this.lastFrameTime;
        this.lastFrameTime = now;
        this.frameCount++;

        this.currentFrameTimeMs = dt;
        this.currentFps = Math.round(1000 / Math.max(1, dt));

        this.fpsHistory.shift();
        this.fpsHistory.push(this.currentFps);
        this.frameTimeHistory.shift();
        this.frameTimeHistory.push(this.currentFrameTimeMs);

        this.renderStats();
        webglStats.resetFrame();

        requestAnimationFrame(update);
      };
      requestAnimationFrame(update);
    }

    renderStats() {
      if (!this.visible || this.minimized) return;

      // Update Overview Values
      this.dom.querySelector('#mpo-val-fps').textContent = `${this.currentFps} FPS`;
      this.dom.querySelector('#mpo-val-frametime').textContent = `${this.currentFrameTimeMs.toFixed(1)} ms`;
      this.dom.querySelector('#mpo-val-drawcalls').textContent = webglStats.drawCalls;
      this.dom.querySelector('#mpo-val-triangles').textContent = webglStats.triangles.toLocaleString();
      this.dom.querySelector('#mpo-val-apitime').textContent = `${webglStats.apiTimeMs.toFixed(2)} ms`;

      if (performance.memory) {
        const usedMb = (performance.memory.usedJSHeapSize / (1024 * 1024)).toFixed(1);
        const totalMb = (performance.memory.totalJSHeapSize / (1024 * 1024)).toFixed(1);
        this.dom.querySelector('#mpo-val-jsmem').textContent = `${usedMb} / ${totalMb} MB`;
      }

      // Draw FPS Graph
      this.drawGraph();

      // Detect Three.js / Miris scene renderer
      let threeRenderer = null;
      const mirisScenes = document.querySelectorAll('miris-scene');
      mirisScenes.forEach(ms => {
        if (ms.threeRenderer) threeRenderer = ms.threeRenderer;
      });

      if (threeRenderer && threeRenderer.info) {
        const rInfo = threeRenderer.info;
        this.dom.querySelector('#mpo-r-calls').textContent = rInfo.render.calls;
        this.dom.querySelector('#mpo-r-triangles').textContent = rInfo.render.triangles.toLocaleString();
        this.dom.querySelector('#mpo-r-points').textContent = rInfo.render.points.toLocaleString();
        this.dom.querySelector('#mpo-r-lines').textContent = rInfo.render.lines.toLocaleString();
        this.dom.querySelector('#mpo-r-geoms').textContent = rInfo.memory.geometries;
        this.dom.querySelector('#mpo-r-textures').textContent = rInfo.memory.textures;
        this.dom.querySelector('#mpo-r-programs').textContent = rInfo.programs ? rInfo.programs.length : 'N/A';
      } else {
        this.dom.querySelector('#mpo-r-calls').textContent = webglStats.drawCalls;
        this.dom.querySelector('#mpo-r-triangles').textContent = webglStats.triangles.toLocaleString();
        this.dom.querySelector('#mpo-r-points').textContent = webglStats.points.toLocaleString();
        this.dom.querySelector('#mpo-r-lines').textContent = webglStats.lines.toLocaleString();
      }

      // WebGL Driver parameters
      if (activeGLContexts.size > 0) {
        const gl = activeGLContexts.values().next().value;
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        if (debugInfo) {
          this.dom.querySelector('#mpo-gl-vendor').textContent = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || 'Unknown';
          this.dom.querySelector('#mpo-gl-renderer').textContent = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || 'Unknown';
        }
        this.dom.querySelector('#mpo-gl-maxtex').textContent = gl.getParameter(gl.MAX_TEXTURE_SIZE) + ' px';
        this.dom.querySelector('#mpo-gl-ver').textContent = gl.getParameter(gl.VERSION) || 'WebGL';
      }

      // Render API Breakdown
      if (this.activeTab === 'api') {
        const container = this.dom.querySelector('#mpo-api-calls-breakdown');
        const sorted = Object.entries(webglStats.methodCounts).sort((a, b) => b[1] - a[1]);
        if (sorted.length === 0) {
          container.innerHTML = '<p style="color:#64748b; font-style:italic;">No WebGL calls recorded in active frame.</p>';
        } else {
          const maxCount = Math.max(...sorted.map(s => s[1]), 1);
          container.innerHTML = sorted.map(([method, count]) => {
            const pct = Math.min(100, Math.round((count / maxCount) * 100));
            const time = (webglStats.methodTimes[method] || 0).toFixed(2);
            return `
              <div style="margin-bottom: 6px;">
                <div style="display:flex; justify-content:space-between; font-size:11px;">
                  <span style="font-family:monospace; color:#e2e8f0;">${method}</span>
                  <span style="color:#38bdf8; font-weight:600;">${count}x <span style="color:#64748b; font-size:10px;">(${time}ms)</span></span>
                </div>
                <div class="mpo-bar-container">
                  <div class="mpo-bar-fill" style="width: ${pct}%;"></div>
                </div>
              </div>
            `;
          }).join('');
        }
      }

      // Network Stats
      if (this.activeTab === 'network') {
        this.dom.querySelector('#mpo-net-active').textContent = networkStats.activeRequests;
        const kb = (networkStats.bytesTransferred / 1024).toFixed(1);
        this.dom.querySelector('#mpo-net-bytes').textContent = `${kb} KB`;

        const netList = this.dom.querySelector('#mpo-net-list');
        if (networkStats.recentRequests.length === 0) {
          netList.innerHTML = '<p style="color:#64748b; font-style:italic;">No network requests captured yet.</p>';
        } else {
          netList.innerHTML = networkStats.recentRequests.map(r => `
            <div class="mpo-req-item">
              <div class="mpo-req-url">${r.url}</div>
              <div class="mpo-req-meta">
                <span>Status: ${r.status}</span>
                <span>Time: ${r.duration}ms</span>
                <span>Size: ${(r.size / 1024).toFixed(1)} KB</span>
              </div>
            </div>
          `).join('');
        }
      }

      // Miris Engine Stats
      if (this.activeTab === 'miris') {
        const scenes = document.querySelectorAll('miris-scene');
        const streams = document.querySelectorAll('miris-stream');
        this.dom.querySelector('#mpo-miris-scenes').textContent = scenes.length;
        this.dom.querySelector('#mpo-miris-streams').textContent = streams.length;
        
        let splatCount = document.querySelectorAll('miris-lod').length;
        this.dom.querySelector('#mpo-miris-lods').textContent = splatCount;

        if (scenes.length > 0) {
          const sc = scenes[0];
          this.dom.querySelector('#mpo-miris-camfit').textContent = sc.getAttribute('camera-fit') || 'none';
          this.dom.querySelector('#mpo-miris-exposure').textContent = sc.getAttribute('exposure') || '1.0';
        }
      }
    }

    drawGraph() {
      const canvas = this.dom.querySelector('#mpo-fps-graph');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);

      // Grid lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2);
      ctx.stroke();

      // FPS line (Green)
      ctx.strokeStyle = '#4ade80';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      const step = w / (this.fpsHistory.length - 1);

      this.fpsHistory.forEach((fps, i) => {
        const x = i * step;
        const y = h - Math.min(h, Math.max(0, (fps / 60) * h));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Frame time line (Cyan)
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 1;
      ctx.beginPath();
      this.frameTimeHistory.forEach((ft, i) => {
        const x = i * step;
        const y = Math.min(h, (ft / 33.3) * h);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    exportData() {
      const trace = {
        timestamp: new Date().toISOString(),
        fps: this.currentFps,
        frameTimeMs: this.currentFrameTimeMs,
        webglStats: {
          drawCalls: webglStats.drawCalls,
          triangles: webglStats.triangles,
          apiTimeMs: webglStats.apiTimeMs,
          methodCounts: webglStats.methodCounts
        },
        networkStats: {
          totalRequests: networkStats.totalRequests,
          bytesTransferred: networkStats.bytesTransferred,
          recentRequests: networkStats.recentRequests
        }
      };

      const blob = new Blob([JSON.stringify(trace, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `miris-perf-trace-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  // Auto Init HUD
  const hud = new MirisPerfHUD();
  global.__MIRIS_PERF_OVERLAY__ = hud;

  console.log('%c[MirisPerfOverlay] Initialized. Press `~` or `Ctrl+Shift+P` to toggle overlay.', 'color:#38bdf8; font-weight:bold;');
})(window);
