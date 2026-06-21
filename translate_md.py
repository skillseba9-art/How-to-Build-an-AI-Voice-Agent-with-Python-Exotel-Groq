import os
import re
from deep_translator import GoogleTranslator

bengali_regex = re.compile(r'[\u0980-\u09FF]')
translator = GoogleTranslator(source='bn', target='en')

def translate_line(line):
    # Only translate if line contains Bengali
    if not bengali_regex.search(line):
        return line
    try:
        # We translate the whole line because translating word by word might mess up grammar.
        # But for markdown lines (like headers, bullets), we should keep the formatting.
        
        # Check if line has a markdown prefix like "# " or "- [ ] "
        prefix = ""
        content = line
        
        # Try to extract bullet points or headers
        match = re.match(r'^([\s#*\->\[\]]+)(.*)', line)
        if match:
            prefix = match.group(1)
            content = match.group(2)
            
        if not content.strip():
            return line
            
        translated = translator.translate(content)
        return prefix + translated + "\n" if line.endswith("\n") else prefix + translated
        
    except Exception as e:
        print(f"Error translating line -> {e}")
        return line

files_to_translate = [
    'Student_Supervise_Roadmap.md',
    'task_plan.md'
]

for file_path in files_to_translate:
    if not os.path.exists(file_path):
        continue
        
    print(f"Processing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    for i, line in enumerate(lines):
        if bengali_regex.search(line):
            new_lines.append(translate_line(line))
        else:
            new_lines.append(line)
            
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    print(f"Finished {file_path}")
