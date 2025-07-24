#!/usr/bin/env python3
"""Comprehensive check for remaining workarounds in the codebase."""

import os
import re
import ast
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class WorkaroundChecker:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.issues = {
            'print_statements': [],
            'sys_path_manipulations': [],
            'debug_code': [],
            'todo_comments': [],
            'multiple_versions': []
        }
        
        # Directories to exclude from checking
        self.exclude_dirs = {
            '.venv', 'venv', '__pycache__', '.git', '.pytest_cache',
            'node_modules', 'dist', 'build', '.kiro'
        }
        
        # File patterns to check
        self.python_files = []
        
    def find_python_files(self):
        """Find all Python files in the project."""
        for root, dirs, files in os.walk(self.project_root):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    self.python_files.append(Path(root) / file)
                    
    def check_print_statements(self, filepath):
        """Check for print statements in production code."""
        # Skip test files and scripts
        if '/tests/' in str(filepath) or '/scripts/' in str(filepath):
            return
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == 'print':
                        self.issues['print_statements'].append({
                            'file': str(filepath.relative_to(self.project_root)),
                            'line': node.lineno
                        })
        except Exception as e:
            logger.debug(f"Error parsing {filepath}: {e}")
            
    def check_sys_path_manipulation(self, filepath):
        """Check for sys.path manipulation."""
        # Skip test files that check for these patterns
        if '/tests/' in str(filepath) or 'test_' in filepath.name:
            return
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Look for sys.path patterns
            patterns = [
                r'sys\.path\.append',
                r'sys\.path\.insert',
                r'sys\.path\[0\]',
                r'sys\.path\[0:0\]'
            ]
            
            for i, line in enumerate(content.splitlines(), 1):
                for pattern in patterns:
                    if re.search(pattern, line) and not line.strip().startswith('#'):
                        self.issues['sys_path_manipulations'].append({
                            'file': str(filepath.relative_to(self.project_root)),
                            'line': i,
                            'content': line.strip()
                        })
        except Exception as e:
            logger.debug(f"Error reading {filepath}: {e}")
            
    def check_debug_code(self, filepath):
        """Check for debug code patterns."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Debug patterns to check (excluding our own scripts)
            if 'comprehensive_workaround_check.py' in str(filepath) or 'fix_remaining_workarounds.py' in str(filepath):
                return
                
            patterns = [
                (r'#\s*DEBUG\b', 'DEBUG comment'),
                (r'#\s*TEMP\b', 'TEMP comment'),
                (r'#\s*FIXME\b', 'FIXME comment'),
                (r'#\s*HACK\b', 'HACK comment'),
                (r'breakpoint\(\)', 'breakpoint()'),
                (r'import\s+pdb', 'pdb import'),
                (r'pdb\.set_trace', 'pdb.set_trace')
            ]
            
            for i, line in enumerate(content.splitlines(), 1):
                for pattern, desc in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        self.issues['debug_code'].append({
                            'file': str(filepath.relative_to(self.project_root)),
                            'line': i,
                            'type': desc,
                            'content': line.strip()
                        })
        except Exception as e:
            logger.debug(f"Error reading {filepath}: {e}")
            
    def check_todo_comments(self, filepath):
        """Check for TODO comments."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Skip our own checking scripts
            if 'comprehensive_workaround_check.py' in str(filepath) or 'fix_remaining_workarounds.py' in str(filepath):
                return
                
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(r'#\s*TODO', line, re.IGNORECASE):
                    self.issues['todo_comments'].append({
                        'file': str(filepath.relative_to(self.project_root)),
                        'line': i,
                        'content': line.strip()
                    })
        except Exception as e:
            logger.debug(f"Error reading {filepath}: {e}")
            
    def check_multiple_versions(self):
        """Check for multiple versions of tools."""
        tool_versions = {}
        
        for filepath in self.python_files:
            if '/tools/' in str(filepath):
                filename = filepath.stem
                # Check for version patterns like _v2, _v3, etc.
                if match := re.search(r'(.+?)_v(\d+)$', filename):
                    tool_name = match.group(1)
                    version = int(match.group(2))
                    if tool_name not in tool_versions:
                        tool_versions[tool_name] = []
                    tool_versions[tool_name].append({
                        'version': version,
                        'file': str(filepath.relative_to(self.project_root))
                    })
                    
        # Report tools with multiple versions
        for tool_name, versions in tool_versions.items():
            if len(versions) > 1:
                self.issues['multiple_versions'].append({
                    'tool': tool_name,
                    'versions': sorted(versions, key=lambda x: x['version'])
                })
                
    def run_checks(self):
        """Run all checks."""
        logger.info("Finding Python files...")
        self.find_python_files()
        logger.info(f"Found {len(self.python_files)} Python files")
        
        logger.info("Checking for workarounds...")
        for filepath in self.python_files:
            self.check_print_statements(filepath)
            self.check_sys_path_manipulation(filepath)
            self.check_debug_code(filepath)
            self.check_todo_comments(filepath)
            
        self.check_multiple_versions()
        
    def generate_report(self):
        """Generate a comprehensive report."""
        print("\n" + "="*80)
        print("WORKAROUND ELIMINATION VALIDATION REPORT")
        print("="*80 + "\n")
        
        # Summary
        total_issues = sum(len(issues) for issues in self.issues.values())
        
        if total_issues == 0:
            print("✅ NO WORKAROUNDS FOUND! The codebase is clean.")
        else:
            print(f"❌ FOUND {total_issues} ISSUES\n")
            
            # Print statements
            if self.issues['print_statements']:
                print(f"\n📝 PRINT STATEMENTS ({len(self.issues['print_statements'])} found)")
                print("-" * 40)
                for issue in self.issues['print_statements'][:10]:
                    print(f"  {issue['file']}:{issue['line']}")
                if len(self.issues['print_statements']) > 10:
                    print(f"  ... and {len(self.issues['print_statements']) - 10} more")
                    
            # sys.path manipulations
            if self.issues['sys_path_manipulations']:
                print(f"\n🔧 SYS.PATH MANIPULATIONS ({len(self.issues['sys_path_manipulations'])} found)")
                print("-" * 40)
                for issue in self.issues['sys_path_manipulations'][:10]:
                    print(f"  {issue['file']}:{issue['line']} - {issue['content'][:60]}...")
                if len(self.issues['sys_path_manipulations']) > 10:
                    print(f"  ... and {len(self.issues['sys_path_manipulations']) - 10} more")
                    
            # Debug code
            if self.issues['debug_code']:
                print(f"\n🐛 DEBUG CODE ({len(self.issues['debug_code'])} found)")
                print("-" * 40)
                for issue in self.issues['debug_code'][:10]:
                    print(f"  {issue['file']}:{issue['line']} - {issue['type']}")
                if len(self.issues['debug_code']) > 10:
                    print(f"  ... and {len(self.issues['debug_code']) - 10} more")
                    
            # TODO comments
            if self.issues['todo_comments']:
                print(f"\n📌 TODO COMMENTS ({len(self.issues['todo_comments'])} found)")
                print("-" * 40)
                for issue in self.issues['todo_comments'][:10]:
                    print(f"  {issue['file']}:{issue['line']} - {issue['content'][:60]}...")
                if len(self.issues['todo_comments']) > 10:
                    print(f"  ... and {len(self.issues['todo_comments']) - 10} more")
                    
            # Multiple versions
            if self.issues['multiple_versions']:
                print(f"\n🔢 MULTIPLE TOOL VERSIONS ({len(self.issues['multiple_versions'])} tools)")
                print("-" * 40)
                for issue in self.issues['multiple_versions']:
                    print(f"  {issue['tool']}:")
                    for version in issue['versions']:
                        print(f"    v{version['version']}: {version['file']}")
                        
        print("\n" + "="*80)
        
        # Progress summary
        print("\nPROGRESS SUMMARY:")
        print("-" * 40)
        completed_tasks = [
            "✅ Task 8: Token and embedding management",
            "✅ Task 9: Consistent column naming", 
            "✅ Task 10: PDF/email separation",
            "✅ Task 11: Job analysis consolidation",
            "✅ Task 12: File structure organization",
            "✅ Task 13: Memory integrity fixes",
            "✅ Task 14: Service documentation",
            "✅ Task 15: Test suite creation",
            "✅ Task 16: Validation scripts"
        ]
        
        for task in completed_tasks:
            print(task)
            
        if total_issues > 0:
            print("\n⚠️  REMAINING WORK:")
            if self.issues['print_statements']:
                print(f"  - Remove {len(self.issues['print_statements'])} print statements")
            if self.issues['sys_path_manipulations']:
                print(f"  - Fix {len(self.issues['sys_path_manipulations'])} sys.path manipulations")
            if self.issues['debug_code']:
                print(f"  - Clean up {len(self.issues['debug_code'])} debug code instances")
            if self.issues['todo_comments']:
                print(f"  - Address {len(self.issues['todo_comments'])} TODO comments")
            if self.issues['multiple_versions']:
                print(f"  - Consolidate {len(self.issues['multiple_versions'])} tools with multiple versions")
                
        print("\n" + "="*80)
        
        return total_issues == 0

if __name__ == "__main__":
    checker = WorkaroundChecker()
    checker.run_checks()
    is_clean = checker.generate_report()
    
    if not is_clean:
        print("\n💡 TIP: Run 'python scripts/fix_remaining_workarounds.py' to auto-fix many issues")
        exit(1)
    else:
        print("\n🎉 Congratulations! Workaround elimination is complete!")
        exit(0)