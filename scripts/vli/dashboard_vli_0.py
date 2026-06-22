import os
import sys
import tempfile
import webbrowser
from datetime import datetime

# Setup paths to allow importing from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

# Force Mock Broker to use the offline CSV
os.environ["MOCK_BROKER"] = "true"

from src.tools.broker import get_attribution_summary, get_personal_risk_metrics, get_daily_blotter

def generate_vli_dashboard():
    # 1. Fetch data from the DAL APIs
    print("Initiating VLI Mock Broker Session...")
    config = {"configurable": {"snaptrade_settings": {"MOCK_BROKER": "true"}}}
    
    print("Fetching Portfolio Manager data...")
    pm_data = get_attribution_summary.invoke(config)
    
    print("Fetching Risk Manager data...")
    rm_data = get_personal_risk_metrics.invoke(config)
    
    print("Fetching Journaler data...")
    jn_data = get_daily_blotter.invoke(config)

    # 2. Build the HTML Payload
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VLI Terminal | Broker DAL Dashboard</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
            
            :root {{
                --bg: #050505;
                --surface: rgba(20, 22, 28, 0.6);
                --border: rgba(60, 60, 75, 0.4);
                --glow: #00f0ff;
                --text-primary: #f0f0f0;
                --text-secondary: #8a8a93;
                --accent-pm: #ff2a6d;
                --accent-rm: #05d9e8;
                --accent-jn: #01ffc3;
            }}
            
            body {{
                background-color: var(--bg);
                color: var(--text-primary);
                font-family: 'Inter', sans-serif;
                margin: 0;
                padding: 40px;
                min-height: 100vh;
                background-image: 
                    radial-gradient(circle at 15% 50%, rgba(255, 42, 109, 0.05) 0%, transparent 50%),
                    radial-gradient(circle at 85% 30%, rgba(5, 217, 232, 0.05) 0%, transparent 50%);
                background-attachment: fixed;
            }}
            
            .header {{
                display: flex;
                flex-direction: column;
                align-items: center;
                margin-bottom: 50px;
                text-align: center;
            }}
            
            .logo {{
                font-weight: 800;
                font-size: 2.5rem;
                letter-spacing: 4px;
                text-transform: uppercase;
                background: linear-gradient(90deg, #fff, #8a8a93);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 0;
            }}
            
            .subtitle {{
                font-family: 'JetBrains Mono', monospace;
                color: var(--glow);
                font-size: 0.9rem;
                letter-spacing: 2px;
                margin-top: 10px;
                text-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
            }}
            
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 30px;
                max-width: 1400px;
                margin: 0 auto;
            }}
            
            .card {{
                background: var(--surface);
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 30px;
                position: relative;
                overflow: hidden;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
            }}
            
            .card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 20px 50px rgba(0,0,0,0.7);
            }}
            
            .card.pm:hover {{ border-color: rgba(255, 42, 109, 0.5); }}
            .card.rm:hover {{ border-color: rgba(5, 217, 232, 0.5); }}
            .card.jn:hover {{ border-color: rgba(1, 255, 195, 0.5); }}
            
            .card-header {{
                display: flex;
                align-items: center;
                margin-bottom: 25px;
            }}
            
            .icon {{
                width: 40px;
                height: 40px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.2rem;
                margin-right: 15px;
                font-weight: bold;
            }}
            
            .pm .icon {{ background: rgba(255, 42, 109, 0.1); color: var(--accent-pm); border: 1px solid rgba(255, 42, 109, 0.3); }}
            .rm .icon {{ background: rgba(5, 217, 232, 0.1); color: var(--accent-rm); border: 1px solid rgba(5, 217, 232, 0.3); }}
            .jn .icon {{ background: rgba(1, 255, 195, 0.1); color: var(--accent-jn); border: 1px solid rgba(1, 255, 195, 0.3); }}
            
            .title h2 {{
                margin: 0;
                font-weight: 600;
                font-size: 1.3rem;
            }}
            
            .title p {{
                margin: 4px 0 0 0;
                font-size: 0.8rem;
                color: var(--text-secondary);
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            
            pre {{
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                padding: 20px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.85rem;
                color: #c9d1d9;
                white-space: pre-wrap;
                line-height: 1.5;
                height: 300px;
                overflow-y: auto;
            }}
            
            pre::-webkit-scrollbar {{ width: 6px; }}
            pre::-webkit-scrollbar-track {{ background: transparent; }}
            pre::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
            pre::-webkit-scrollbar-thumb:hover {{ background: var(--text-secondary); }}
            
            .stats-bar {{
                display: flex;
                justify-content: center;
                gap: 50px;
                margin-top: 50px;
                padding-top: 30px;
                border-top: 1px solid var(--border);
                max-width: 1400px;
                margin-left: auto;
                margin-right: auto;
            }}
            
            .stat {{ text-align: center; }}
            .stat-val {{ font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: bold; color: var(--text-primary); }}
            .stat-lbl {{ font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }}
            
        </style>
    </head>
    <body>
        <div class="header">
            <h1 class="logo">Cobalt Multi-Agent</h1>
            <div class="subtitle">VLI MOCK BROKER TERMINAL • OFFLINE DAL CACHE • {timestamp}</div>
        </div>
        
        <div class="grid">
            <!-- Portfolio Manager -->
            <div class="card pm">
                <div class="card-header">
                    <div class="icon">PM</div>
                    <div class="title">
                        <h2>Portfolio Manager</h2>
                        <p>API: get_attribution_summary()</p>
                    </div>
                </div>
                <pre>{pm_data}</pre>
            </div>
            
            <!-- Risk Manager -->
            <div class="card rm">
                <div class="card-header">
                    <div class="icon">RM</div>
                    <div class="title">
                        <h2>Risk Manager</h2>
                        <p>API: get_personal_risk_metrics()</p>
                    </div>
                </div>
                <pre>{rm_data}</pre>
            </div>
            
            <!-- Journaler -->
            <div class="card jn">
                <div class="card-header">
                    <div class="icon">JN</div>
                    <div class="title">
                        <h2>Journaler</h2>
                        <p>API: get_daily_blotter()</p>
                    </div>
                </div>
                <pre>{jn_data}</pre>
            </div>
        </div>
        
        <div class="stats-bar">
            <div class="stat">
                <div class="stat-val">3</div>
                <div class="stat-lbl">Active Agent Tools</div>
            </div>
            <div class="stat">
                <div class="stat-val">0ms</div>
                <div class="stat-lbl">Cached DAL Latency</div>
            </div>
            <div class="stat">
                <div class="stat-val">ONLINE</div>
                <div class="stat-lbl">Offline CSV Parser</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 3. Write and launch
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as f:
        f.write(html)
        temp_path = f.name
        
    print(f"Opening VLI Dashboard: {temp_path}")
    webbrowser.open(f'file://{temp_path}')

if __name__ == "__main__":
    generate_vli_dashboard()
