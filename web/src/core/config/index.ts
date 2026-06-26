export const getBackendBaseURL = () => {
    if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        if (url.port === '3000' || url.port === '3001' || url.port === '8080' || url.port === '8089') {
            return `http://${url.hostname}:8000`;
        }
        return `http://${url.hostname}:${url.port}`;
    }
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

export const getBackendWSURL = () => {
    const base = getBackendBaseURL();
    return base.replace('http', 'ws');
};

export const getLangGraphBaseURL = () => {
    if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        const host = url.hostname === 'localhost' ? '127.0.0.1' : url.hostname;
        if (url.port === '3000' || url.port === '3001' || url.port === '8080' || url.port === '8089') {
            return `http://${host}:2024`;
        }
        return `http://${host}:${url.port}`;
    }
    return process.env.NEXT_PUBLIC_LANGGRAPH_URL || "http://127.0.0.1:2024";
};

export const getSystemMode = (): "LOCAL" | "REMOTE" => {
    const mode = process.env.NEXT_PUBLIC_SYSTEM_MODE;
    return (mode === "REMOTE") ? "REMOTE" : "LOCAL";
};

export * from "./types";
