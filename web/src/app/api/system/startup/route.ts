import { spawn, execSync } from 'child_process';
import path from 'path';

const CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export async function OPTIONS() {
    return new Response(null, {
        status: 204,
        headers: CORS_HEADERS
    });
}

export async function POST() {
    // Attempt to see if the server is already responding
    try {
        const res = await fetch("http://127.0.0.1:8000/api/health", { cache: 'no-store', signal: AbortSignal.timeout(1000) });
        if (res.ok) {
            return Response.json({ status: "already_running" }, { headers: CORS_HEADERS });
        }
    } catch (e) {
        // Not running, or at least not responding on 8000
    }

    // --- PRE-FLIGHT STALE PROCESS CLEANUP ---
    // If the server didn't respond, we assume it's offline or hanging.
    // Forcefully kill any lingering zombie processes before spawning a new one.
    try {
        if (process.platform === 'win32') {
            execSync('wmic process where "CommandLine like \'%server.py%\' and name=\'python.exe\'" call terminate', { stdio: 'ignore' });
            execSync('wmic process where "CommandLine like \'%server.py%\' and name=\'uv.exe\'" call terminate', { stdio: 'ignore' });
        } else {
            execSync('pkill -f "server.py"', { stdio: 'ignore' });
        }
    } catch (cleanupError) {
        // Ignored. execSync throws if the command fails (e.g. no processes found to kill)
    }

    try {
        // process.cwd() is typically the `web` folder when running Next.js
        const backendPath = path.resolve(process.cwd(), '../backend');

        const child = spawn('uv', ['run', 'server.py'], {
            cwd: backendPath,
            detached: true,
            stdio: 'ignore',
            shell: true,
            windowsHide: true
        });
        
        child.unref(); // Detach the process from Node's event loop

        return Response.json({ status: "started" }, { headers: CORS_HEADERS });
    } catch (error) {
        return Response.json({ status: "error", message: String(error) }, { status: 500, headers: CORS_HEADERS });
    }
}

