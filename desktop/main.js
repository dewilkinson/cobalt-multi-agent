const { app, BrowserWindow, globalShortcut, session } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');

// Disable sandboxing to prevent renderer crashes in virtualized/service environments
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-gpu-sandbox');

let mainWindow;
let backendProcess;
let webProcess;

// Check for --dev flag
const isDev = process.argv.includes('--dev');

async function waitForServer() {
    console.log('[VLI-Electron] Waiting for Python backend to initialize...');
    const maxRetries = 60; // Wait up to 60 seconds
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch('http://127.0.0.1:8000/api/health');
            if (response.ok) {
                const data = await response.json();
                if (data.version) {
                    console.log('[VLI-Electron] Backend is online!');
                    return true;
                }
            }
        } catch (error) {
            console.log(`[VLI-Electron] Backend health check failed (attempt ${i + 1}/${maxRetries}):`, error.message);
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    return false;
}

async function waitForWeb() {
    const webPort = isDev ? 3000 : 8080;
    console.log(`[VLI-Electron] Waiting for Next.js web client to initialize on port ${webPort}...`);
    const maxRetries = 120; // Wait up to 120 seconds (Next.js compilation takes time)
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(`http://127.0.0.1:${webPort}/`);
            if (response.ok) {
                console.log('[VLI-Electron] Web client is online!');
                return true;
            }
        } catch (error) {
            console.log(`[VLI-Electron] Web client check failed (attempt ${i + 1}/${maxRetries}):`, error.message);
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    return false;
}

function killProcessOnPort(port) {
    try {
        if (process.platform === 'win32') {
            const output = execSync('netstat -ano').toString();
            const lines = output.split('\n');
            const pids = new Set();
            for (const line of lines) {
                if (line.includes('LISTENING')) {
                    const parts = line.trim().split(/\s+/);
                    if (parts.length >= 5) {
                        const localAddress = parts[1];
                        if (localAddress) {
                            const colonIdx = localAddress.lastIndexOf(':');
                            const localPort = localAddress.substring(colonIdx + 1);
                            if (localPort === String(port)) {
                                const pid = parts[parts.length - 1];
                                if (pid && !isNaN(pid) && pid !== '0') {
                                    pids.add(parseInt(pid));
                                }
                            }
                        }
                    }
                }
            }
            for (const pid of pids) {
                if (pid === process.pid) continue;
                console.log(`[VLI-Electron] Found zombie process (PID ${pid}) on port ${port}. Killing it...`);
                try {
                    execSync(`taskkill /pid ${pid} /T /F`);
                    console.log(`[VLI-Electron] Successfully killed PID ${pid} on port ${port}.`);
                } catch (e) {
                    console.error(`[VLI-Electron] Failed to kill PID ${pid}:`, e.message);
                }
            }
        } else {
            try {
                const pid = execSync(`lsof -t -i:${port}`).toString().trim();
                if (pid) {
                    const pids = pid.split('\n');
                    for (const p of pids) {
                        const pidNum = parseInt(p);
                        if (pidNum && pidNum !== process.pid) {
                            console.log(`[VLI-Electron] Found zombie process (PID ${pidNum}) on port ${port}. Killing it...`);
                            execSync(`kill -9 ${pidNum}`);
                        }
                    }
                }
            } catch (e) {
                // lsof returns exit code 1 if no process found
            }
        }
    } catch (err) {
        console.error(`[VLI-Electron] Error checking/killing process on port ${port}:`, err.message);
    }
}

function startBackend() {
    const backendPath = path.join(__dirname, '..', 'backend');
    console.log('[VLI-Electron] Starting backend from:', backendPath);
    
    try {
        // Run bump_version.py synchronously
        execSync('uv run python bump_version.py', { cwd: backendPath, stdio: 'ignore' });
    } catch (e) {
        console.error('[VLI-Electron] Failed to bump version:', e.message);
    }

    const serverArgs = ['run', 'server.py'];
    if (isDev) {
        serverArgs.push('--reload');
    }

    backendProcess = spawn('uv', serverArgs, {
        cwd: backendPath,
        shell: true // required for Windows to resolve 'uv' in PATH
    });

    backendProcess.stdout.on('data', (data) => console.log(`[Backend] ${data.toString().trim()}`));
    backendProcess.stderr.on('data', (data) => console.error(`[Backend] ${data.toString().trim()}`));
    
    backendProcess.on('close', (code) => {
        console.log(`[Backend] Process exited with code ${code}`);
    });
}

function startWeb() {
    const webPath = path.join(__dirname, '..', 'web');
    console.log('[VLI-Electron] Starting Next.js web client from:', webPath);
    
    const webCmd = isDev ? 'dev' : 'start';
    
    webProcess = spawn('pnpm', [webCmd], {
        cwd: webPath,
        shell: true
    });

    webProcess.stdout.on('data', (data) => console.log(`[Web] ${data.toString().trim()}`));
    webProcess.stderr.on('data', (data) => console.error(`[Web] ${data.toString().trim()}`));
    
    webProcess.on('close', (code) => {
        console.log(`[Web] Process exited with code ${code}`);
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 2400,
        height: 1331,
        backgroundColor: '#0a0c10',
        autoHideMenuBar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });
    // We start loading the URL only after the Python server confirms it is alive
    mainWindow.loadFile('boot.html');
}

app.whenReady().then(async () => {
    createWindow();
    
    // Ensure no zombie processes are listening on our ports before launch
    const webPort = isDev ? 3000 : 8080;
    killProcessOnPort(8000);
    killProcessOnPort(webPort);
    
    startBackend();
    startWeb();

    const isOnline = await waitForServer();
    
    // We still start the web server in the background, but we don't block the Electron UI on it
    waitForWeb().catch(err => console.error('[VLI-Electron] Web check error:', err));
    
    if (isOnline) {
        console.log(`[VLI-Electron] Python backend is online. Delegating navigation to boot.html.`);
    } else {
        mainWindow.loadFile('error.html');
    }

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
    
    // Register shortcuts
    globalShortcut.register('CommandOrControl+R', () => {
        if (mainWindow) {
            mainWindow.webContents.reloadIgnoringCache();
        }
    });
    globalShortcut.register('F5', () => {
        if (mainWindow) {
            mainWindow.webContents.reloadIgnoringCache();
        }
    });
    globalShortcut.register('CommandOrControl+Shift+I', () => {
        if (mainWindow) {
            mainWindow.webContents.toggleDevTools();
        }
    });
});

app.on('will-quit', () => {
    globalShortcut.unregisterAll();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Ensure child processes are killed when the electron app closes
app.on('will-quit', () => {
    console.log('[VLI-Electron] Shutting down subprocesses...');
    if (backendProcess) {
        backendProcess.kill();
    }
    if (webProcess) {
        webProcess.kill();
    }
    
    // On Windows, child processes spawned with shell:true sometimes leave orphan processes.
    // We can use taskkill to forcefully kill the process tree if needed.
    if (process.platform === 'win32') {
        try {
            if (backendProcess && backendProcess.pid) {
                execSync(`taskkill /pid ${backendProcess.pid} /T /F`, { stdio: 'ignore' });
            }
            if (webProcess && webProcess.pid) {
                execSync(`taskkill /pid ${webProcess.pid} /T /F`, { stdio: 'ignore' });
            }
        } catch (e) {
            // ignore
        }
    }
});
