const { app, BrowserWindow, globalShortcut } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');

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

function startBackend() {
    const backendPath = path.join(__dirname, '..', 'backend');
    console.log('[VLI-Electron] Starting backend from:', backendPath);
    
    // Removed automatic version bumping on every launch

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
        width: 1600,
        height: 1000,
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
    
    startBackend();
    startWeb();

    const isOnline = await waitForServer();
    
    // We still start the web server in the background, but we don't block the Electron UI on it
    waitForWeb().catch(err => console.error('[VLI-Electron] Web check error:', err));
    
    if (isOnline) {
        console.log(`[VLI-Electron] Navigating to VLI Dashboard`);
        mainWindow.loadURL(`http://127.0.0.1:8000/vli_dashboard.html`)
            .then(() => console.log('[VLI-Electron] Successfully navigated to VLI Dashboard!'))
            .catch(err => console.log('[VLI-Electron] Failed to navigate:', err));
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
