import os
import re

files_to_fix = [
    'c:/django/Travel Buddyy/Travel Buddy/Travel Buddy/travel_buddy/template/company/chat_index.html',
    'c:/django/Travel Buddyy/Travel Buddy/Travel Buddy/travel_buddy/template/receipt.html',
    'c:/django/Travel Buddyy/Travel Buddy/Travel Buddy/travel_buddy/template/company/profile.html'
]

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The actual issue is: {{ \n or \n }}
    # E.g. {{\n     something }}
    # Let's replace those robustly.
    def replace_newlines(match):
        # match is the whole {{ ... }} block
        inner = match.group(1).replace('\n', ' ').replace('\r', '').strip()
        inner = re.sub(r'\s+', ' ', inner)
        return '{{ ' + inner + ' }}'
        
    new_content = re.sub(r'\{\{\s*([\s\S]*?)\s*\}\}', replace_newlines, content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Fixed {{...}} in {filepath}')

for fp in files_to_fix:
    fix_file(fp)
