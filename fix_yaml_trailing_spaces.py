#!/usr/bin/env python3
"""Fix trailing spaces in YAML files."""
from pathlib import Path

def fix_trailing_spaces(filepath):
    """Remove trailing spaces from file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified = False
        new_lines = []
        
        for line in lines:
            if line.endswith(' \n') or line.endswith('\t\n'):
                line = line.rstrip() + '\n'
                modified = True
            elif line.endswith(' ') or line.endswith('\t'):
                line = line.rstrip()
                modified = True
            new_lines.append(line)
        
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {filepath}: {e}")
        return False


def main():
    """Main function."""
    root = Path(__file__).parent
    workflows = root / '.github' / 'workflows'
    
    fixed_count = 0
    for filepath in workflows.glob('*.yml'):
        if fix_trailing_spaces(filepath):
            fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")


if __name__ == '__main__':
    main()
