import json, sys

with open('/tmp/nm_ci_output.json') as f:
    data = json.load(f)

ctrls = ','.join(data.get('affected_controls', []))
warnings = 'true' if data.get('warnings') else 'false'
summary = data.get('summary', '')

print(f'affected-controls={ctrls}')
print(f'has-warnings={warnings}')
print(f'summary={summary}')
