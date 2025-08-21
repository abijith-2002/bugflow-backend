#!/usr/bin/env python3
"""
Script to fix common linting issues in the codebase.
"""

import os

def fix_unused_exception_variables(file_path):
    """Fix unused exception variables in except blocks."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace 'except Exception as e:' with 'except Exception:' when 'e' is not used
    # This is a simple pattern - in practice, you'd want more sophisticated parsing
    lines = content.split('\n')
    modified_lines = []
    
    for i, line in enumerate(lines):
        # Check if this is an except line with unused variable
        if 'except Exception as e:' in line or 'except HTTPException:' in line:
            # Look ahead to see if 'e' is used in the next few lines
            used = False
            for j in range(i+1, min(i+10, len(lines))):
                if lines[j].strip().startswith('except') or lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                    break
                if ' e' in lines[j] or 'e.' in lines[j] or 'e)' in lines[j]:
                    used = True
                    break
            
            if not used and 'except Exception as e:' in line:
                line = line.replace('except Exception as e:', 'except Exception:')
        
        # Fix unused result variables
        if 'result = ' in line and 'delete()' in line:
            # Check if result is used later
            used = False
            for j in range(i+1, min(i+5, len(lines))):
                if 'result' in lines[j] and not lines[j].strip().startswith('#'):
                    used = True
                    break
            if not used:
                line = line.replace('result = ', '')
        
        modified_lines.append(line)
    
    modified_content = '\n'.join(modified_lines)
    
    with open(file_path, 'w') as f:
        f.write(modified_content)

def main():
    """Main function to fix linting issues."""
    router_files = [
        'src/routers/users.py',
        'src/routers/projects.py', 
        'src/routers/bugs.py'
    ]
    
    for file_path in router_files:
        if os.path.exists(file_path):
            print(f"Fixing {file_path}...")
            fix_unused_exception_variables(file_path)
            print(f"Fixed {file_path}")

if __name__ == "__main__":
    main()
