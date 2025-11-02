#!/usr/bin/env python3
"""Auto-fix flake8 issues in the codebase."""
import re
import sys
from pathlib import Path


def fix_file(filepath):
    """Fix flake8 issues in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified = False
        new_lines = []
        
        for line in lines:
            original = line
            # Fix W293: blank line contains whitespace
            if line.strip() == '' and line != '\n':
                line = '\n'
                modified = True
            # Fix W291: trailing whitespace
            elif line.endswith(' \n') or line.endswith('\t\n'):
                line = line.rstrip() + '\n'
                modified = True
            
            new_lines.append(line)
        
        # Fix W391: blank line at end of file
        while len(new_lines) > 1 and new_lines[-1] == '\n' and new_lines[-2] == '\n':
            new_lines.pop()
            modified = True
        
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
    patterns = ['modules/**/*.py', 'secaudit/**/*.py', 'utils/**/*.py', 'tests/**/*.py']
    
    fixed_count = 0
    for pattern in patterns:
        for filepath in root.glob(pattern):
            if fix_file(filepath):
                fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")


if __name__ == '__main__':
    main()
