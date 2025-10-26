import json

with open('data/readytensor_awards.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print('Total award-tagged projects:', len(data))
print('Awards:', [p['awards'] for p in data if p['awards']][:10])