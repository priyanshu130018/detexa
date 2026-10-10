import os, re

matches = []
for root, dirs, files in os.walk('frontend/src'):
    for file in files:
        if file.endswith(('.tsx', '.ts', '.jsx', '.js', '.css', '.html')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    sline = line.strip()
                    if sline.startswith('//') or sline.startswith('/*'):
                        continue
                    # Check for standalone dollar or currency USD or country US
                    has_dollar = bool(re.search(r'\$(?!\{)', sline))
                    has_usd = 'USD' in sline
                    has_us = bool(re.search(r"['\"]US['\"]", sline))
                    if has_dollar or has_usd or has_us:
                        matches.append((path, i, sline))

print(f"Total frontend matches: {len(matches)}")
for m in matches:
    print(f"{m[0]}:{m[1]}: {m[2][:120]}")
