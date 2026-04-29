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

    # Find the improperly formatted tags first and unify them
    def merge_vars(match):
        inner = match.group(1).replace('\n', ' ').replace('\r', '').strip()
        inner = re.sub(r'\s+', ' ', inner)
        return '{{ ' + inner + ' }}'
        
    content = re.sub(r'\{\{\s*([\w\.\:\|\'\"\s]+?)\s*\}\}', merge_vars, content)
    
    # in chat_index.html
    content = content.replace('">{{ trip.chat_messages.count }}</span>', '\">\n                            {{ trip.chat_messages.count }}\n                        </span>')
    content = content.replace('">{{ trip.updates.count }}</span>', '\">\n                            {{ trip.updates.count }}\n                        </span>')
    content = content.replace('">{{ trip.status_text }}</span>', '\">\n                        {{ trip.status_text }}\n                    </span>')
    
    # in receipt.html
    content = content.replace('<span style=\"color: #ff7e5f;\">TB-{{ booking.id|add:1000 }}</span></p>', '\n                    <span style=\"color: #ff7e5f;\">TB-{{ booking.id|add:1000 }}</span>\n                </p>')
    content = content.replace('Status: <strong style=\"{% if booking.status == \'CONFIRMED\' %}color: #28a745;{% elif booking.status == \'PENDING\' %}color: #ffc107;{% else %}color: #dc3545;{% endif %}\">{{ booking.status }}</strong></p>', 'Status: \n                    <strong style=\"{% if booking.status == \'CONFIRMED\' %}color: #28a745;{% elif booking.status == \'PENDING\' %}color: #ffc107;{% else %}color: #dc3545;{% endif %}\">\n                        {{ booking.status }}\n                    </strong>\n                </p>')
    content = content.replace('{{ booking.trip.end_date|date:\"d M Y\" }}', '\n                            {{ booking.trip.end_date|date:\"d M Y\" }}')
    
    # in profile.html
    content = content.replace('empty{% endif %}\">{{ company.', 'empty{% endif %}\">\n                                    {{ company.')
    content = content.replace('empty{% endif %}\">{{', 'empty{% endif %}\">\n                                    {{')
    content = content.replace('}}</div>', '}}\n                                </div>')
    content = content.replace('style=\"color: #1e293b;\">{{ company.', 'style=\"color: #1e293b;\">\n                        {{ company.')
    content = content.replace('}}</h4>', '}}\n                    </h4>')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed {{...}} in {filepath}')

for fp in files_to_fix:
    fix_file(fp)
