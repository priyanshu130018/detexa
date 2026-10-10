import os, re

matches = []
for root, dirs, files in os.walk('frontend/src'):
    for file in files:
        if file.endswith(('.tsx', '.ts', '.jsx', '.js')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    sline = line.strip()
                    if any(kw in sline.lower() for kw in ['amount', 'balance', 'currency', 'emi', 'formatcurrency', 'inr']):
                        matches.append((path, i, sline))

print(f"Total frontend amount/currency lines: {len(matches)}")
for m in matches[:50]:
    print(f"{m[0]}:{m[1]}: {m[2][:120]}")
