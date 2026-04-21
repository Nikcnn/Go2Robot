import re
import os
import sys

def refactor_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Add from __future__ import annotations if not present
    if "from __future__ import annotations" not in content:
        if content.startswith("#!"):
            lines = content.splitlines()
            if len(lines) > 1 and "from __future__ import annotations" not in lines[1]:
                lines.insert(1, "from __future__ import annotations\n")
                content = "\n".join(lines)
        else:
            content = "from __future__ import annotations\n\n" + content

    # Replace modern type hints with brackets
    content = re.sub(r'\blist\[', 'List[', content)
    content = re.sub(r'\bdict\[', 'Dict[', content)
    content = re.sub(r'\btuple\[', 'Tuple[', content)
    
    # Replace T | None with Optional[T]
    content = re.sub(r'([\w\.]+) \| None\b', r'Optional[\1]', content)
    content = re.sub(r'\bNone \| ([\w\.]+)', r'Optional[\1]', content)
    
    # Replace T | U with Union[T, U]
    prev_content = ""
    while prev_content != content:
        prev_content = content
        # Restricted character class to avoid matching set union/bitwise OR
        # Included brackets for nested types
        content = re.sub(r'([\w\.\[\]]+) \| ([\w\.\[\]]+)', r'Union[\1, \2]', content)

    # Replace bare list, dict, tuple in type hints
    # After :, ->, [, or ,
    content = re.sub(r'(?<=[:\-\>\[,])\s*list\b(?![(\w])', ' List', content)
    content = re.sub(r'(?<=[:\-\>\[,])\s*dict\b(?![(\w])', ' Dict', content)
    content = re.sub(r'(?<=[:\-\>\[,])\s*tuple\b(?![(\w])', ' Tuple', content)
    
    # Clean up any potential double spaces or weirdness from the above
    content = content.replace('Optional[ ', 'Optional[')
    content = content.replace('Union[ ', 'Union[')
    content = content.replace('List[ ', 'List[')
    content = content.replace('Dict[ ', 'Dict[')
    content = content.replace('Tuple[ ', 'Tuple[')
    content = content.replace(' ,', ',')

    # Identify needed typing imports
    typing_imports = ['List', 'Dict', 'Tuple', 'Optional', 'Union', 'Any']
    needed_imports = []
    for imp in typing_imports:
        if re.search(rf'\b{imp}\b', content):
            # Check if it's already imported from typing
            if not re.search(rf'\bfrom typing import.*\b{imp}\b', content):
                needed_imports.append(imp)
    
    if needed_imports:
        # Check if from typing already exists
        match = re.search(r'from typing import (.*)', content)
        if match:
            existing_str = match.group(1)
            existing_imports = re.findall(r'\b\w+\b', existing_str)
            all_imports = sorted(list(set(existing_imports + needed_imports)))
            new_typing = f"from typing import {', '.join(all_imports)}"
            content = content.replace(match.group(0), new_typing)
        else:
            # Add after __future__ import
            insertion_point = "from __future__ import annotations"
            content = content.replace(insertion_point, insertion_point + "\n\nfrom typing import " + ", ".join(sorted(needed_imports)))

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

if __name__ == "__main__":
    files = sys.argv[1:]
    for f in files:
        if os.path.isfile(f):
            try:
                changed = refactor_file(f)
                if changed:
                    print(f"Refactored: {f}")
                else:
                    print(f"No changes: {f}")
            except Exception as e:
                print(f"Error refactoring {f}: {e}")
