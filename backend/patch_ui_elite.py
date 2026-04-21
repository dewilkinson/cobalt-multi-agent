import os

path = r'c:\github\cobalt-multi-agent\backend\public\VLI_session_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = """                res.candidates.forEach(c => {
                    const tr = document.createElement('tr');"""

new_logic = """                // ELITE GRADING LOGIC (Shield: High Yield / Low Volatility)
                const validCandidates = res.candidates.filter(c => c.beta !== undefined && c.dividend_yield !== undefined);
                if (validCandidates.length > 0) {
                    validCandidates.forEach(c => {
                        c.raw_power = c.dividend_yield / Math.max(c.beta, 0.01);
                    });
                    
                    const maxPower = Math.max(...validCandidates.map(c => c.raw_power));
                    const minPower = Math.min(...validCandidates.map(c => c.raw_power));
                    
                    res.candidates.forEach(c => {
                        if (c.raw_power === undefined) return;
                        
                        let percentile = 1.0;
                        if (maxPower > minPower) {
                            percentile = (c.raw_power - minPower) / (maxPower - minPower);
                        }
                        
                        c.heat_score = Math.floor(40 + (percentile * 60));
                        
                        if (c.heat_score >= 95) c.grade = 'S';
                        else if (c.heat_score >= 90) c.grade = 'A+';
                        else if (c.heat_score >= 82) c.grade = 'A';
                        else if (c.heat_score >= 75) c.grade = 'B+';
                        else if (c.heat_score >= 65) c.grade = 'B';
                        else if (c.heat_score >= 58) c.grade = 'C+';
                        else if (c.heat_score >= 50) c.grade = 'C';
                        else if (c.heat_score >= 35) c.grade = 'D';
                        else c.grade = 'F';
                    });
                }
                
                // Sort by elite heat_score
                res.candidates.sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));

                res.candidates.forEach(c => {
                    const tr = document.createElement('tr');"""

content = content.replace(old_logic, new_logic)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated Shield Grading Logic")
