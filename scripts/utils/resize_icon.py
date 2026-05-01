from PIL import Image
import os

src = r'C:\Users\rende\.gemini\antigravity\brain\1fd896fd-85e6-4fa5-9c76-8fa9e1b1d1e9\fidelity_bridge_icon_1777434933866.png'
dest_dir = r'C:\github\cobalt-multi-agent\tools\fidelity_extension'

with Image.open(src) as img:
    for size in [16, 48, 128]:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(dest_dir, f'icon{size}.png'))
