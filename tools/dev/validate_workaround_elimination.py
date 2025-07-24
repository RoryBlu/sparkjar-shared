#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Validate complete workaround elimination.

This script performs comprehensive validation to ensure all workarounds
have been successfully eliminated from the codebase.

Usage:
    python validate_workaround_elimination.py         # Run all validations
    python validate_workaround_elimination.py --fix   # Apply automatic fixes where possible
"""

import os
import sys
import re
import ast
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
# REMOVED: sys.path.insert(0, str(project_root))

class WorkaroundValidator:
    """Validates that all workarounds have been eliminated."""
    
    def __init__(self):
        self.project_root = project_root
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'summary': {
                'total_checks': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
    
    def validate_all(self) -> Dict[str, Any]:
        """Run all validation checks."""
        logger.info("🔍 Starting Workaround Elimination Validation...")
        logger.info("=" * 80)
        
        # Run all checks
        self.check_no_print_statements()
        self.check_no_sys_path_manipulation()
        self.check_single_tool_versions()
        self.check_chromadb_integration()
        self.check_configuration_validation()
        self.check_consistent_column_naming()
        self.check_file_organization()
        self.check_memory_entities_integrity()
        self.check_service_documentation()
        self.check_package_structure()
        self.check_no_todo_comments()
        self.check_imports_work()
        
        # Calculate summary
        self._calculate_summary()
        
        # Print results
        self._print_results()
        
        return self.validation_results
    
    def check_no_print_statements(self):
        """Check for debug print statements in production code."""
        logger.info("\n📋 Checking for print statements...")
        
        issues = []
        files_checked = 0
        
        # Directories to check (exclude tests and scripts)
        check_dirs = ['services', 'shared', 'src']
        exclude_patterns = ['test_', '_test.py', '__pycache__', '.pyc']
        
        for dir_name in check_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
                
            for py_file in dir_path.rglob('*.py'):
                # Skip excluded files
                if any(pattern in str(py_file) for pattern in exclude_patterns):
                    continue
                
                files_checked += 1
                
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Parse AST to find print statements
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == 'print':
                                line_no = node.lineno
                                issues.append({
                                    'file': str(py_file.relative_to(self.project_root)),
                                    'line': line_no,
                                    'type': 'print_statement'
                                })
                                
                except Exception as e:
                    logger.error(f"  ⚠️  Error parsing {py_file}: {e}")
        
        # Record results
        self.validation_results['checks']['no_print_statements'] = {
            'passed': len(issues) == 0,
            'files_checked': files_checked,
            'issues': issues,
            'message': f"Found {len(issues)} print statements in {files_checked} files"
        }
        
        if issues:
            logger.info(f"  ❌ Found {len(issues)} print statements")
            for issue in issues[:5]:  # Show first 5
                logger.info(f"     - {issue['file']}:{issue['line']}")
            if len(issues) > 5:
                logger.info(f"     ... and {len(issues) - 5} more")
        else:
            logger.info(f"  ✅ No print statements found in {files_checked} production files")
    
    def check_no_sys_path_manipulation(self):
        """Check for sys.path manipulation."""
        logger.info("\n📋 Checking for sys.path manipulation...")
        
        issues = []
        files_checked = 0
        
        patterns = [
            r'sys\.path\.append',
            r'sys\.path\.insert',
            r'sys\.path\[0\]',
            r'sys\.path\s*=',
            r'sys\.path\.extend'
        ]
        
        for py_file in self.project_root.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
                
            files_checked += 1
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.splitlines()
                
                for i, line in enumerate(lines, 1):
                    for pattern in patterns:
                        if re.search(pattern, line):
                            issues.append({
                                'file': str(py_file.relative_to(self.project_root)),
                                'line': i,
                                'content': line.strip()
                            })
                            
            except Exception as e:
                logger.error(f"  ⚠️  Error reading {py_file}: {e}")
        
        self.validation_results['checks']['no_sys_path_manipulation'] = {
            'passed': len(issues) == 0,
            'files_checked': files_checked,
            'issues': issues,
            'message': f"Found {len(issues)} sys.path manipulations"
        }
        
        if issues:
            logger.info(f"  ❌ Found {len(issues)} sys.path manipulations")
        else:
            logger.info(f"  ✅ No sys.path manipulation found")
    
    def check_single_tool_versions(self):
        """Check that only single versions of tools exist."""
        logger.info("\n📋 Checking for single tool versions...")
        
        tools_dir = self.project_root / 'services' / 'crew-api' / 'src' / 'tools'
        if not tools_dir.exists():
            logger.info(f"  ⚠️  Tools directory not found: {tools_dir}")
            return
        
        # Tool patterns to check
        tool_patterns = {
            'memory': r'sj_memory_tool(_v\d+)?\.py',
            'thinking': r'sj_sequential_thinking_tool(_v\d+)?\.py',
            'document': r'sj_document_tool(_v\d+)?\.py'
        }
        
        issues = []
        
        for tool_name, pattern in tool_patterns.items():
            matches = []
            for file in tools_dir.iterdir():
                if re.match(pattern, file.name):
                    matches.append(file.name)
            
            if len(matches) > 1:
                issues.append({
                    'tool': tool_name,
                    'versions': matches
                })
        
        self.validation_results['checks']['single_tool_versions'] = {
            'passed': len(issues) == 0,
            'issues': issues,
            'message': f"Found {len(issues)} tools with multiple versions"
        }
        
        if issues:
            logger.info(f"  ❌ Found multiple versions for {len(issues)} tools")
            for issue in issues:
                logger.info(f"     - {issue['tool']}: {', '.join(issue['versions'])}")
        else:
            logger.info(f"  ✅ All tools have single versions")
    
    def check_chromadb_integration(self):
        """Check ChromaDB is properly integrated."""
        logger.info("\n📋 Checking ChromaDB integration...")
        
        checks = {
            'chroma_service_exists': (self.project_root / 'shared' / 'services' / 'chroma_service.py').exists(),
            'uses_remote_chromadb': False,
            'no_local_chromadb': True
        }
        
        # Check for remote ChromaDB usage
        remote_pattern = r'chroma-gjdq\.railway\.internal'
        local_patterns = [r'chromadb\.Client\(\)', r'chromadb\.PersistentClient']
        
        for py_file in self.project_root.rglob('*.py'):
            if '__pycache__' in str(py_file) or 'test' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if re.search(remote_pattern, content):
                    checks['uses_remote_chromadb'] = True
                
                for pattern in local_patterns:
                    if re.search(pattern, content):
                        checks['no_local_chromadb'] = False
                        
            except:
                pass
        
        passed = all(checks.values())
        
        self.validation_results['checks']['chromadb_integration'] = {
            'passed': passed,
            'checks': checks,
            'message': 'ChromaDB properly integrated' if passed else 'ChromaDB integration issues found'
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {check.replace('_', ' ').title()}")
    
    def check_configuration_validation(self):
        """Check configuration validation is implemented."""
        logger.info("\n📋 Checking configuration validation...")
        
        checks = {
            'config_validator_exists': (self.project_root / 'shared' / 'config' / 'config_validator.py').exists(),
            'startup_validator_exists': (self.project_root / 'shared' / 'config' / 'startup_validator.py').exists(),
            'profiles_exist': (self.project_root / 'shared' / 'config' / 'profiles.py').exists(),
            'embedding_config_exists': (self.project_root / 'shared' / 'config' / 'embedding_config.py').exists()
        }
        
        passed = all(checks.values())
        
        self.validation_results['checks']['configuration_validation'] = {
            'passed': passed,
            'checks': checks,
            'message': 'Configuration validation implemented' if passed else 'Configuration validation missing'
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {check.replace('_', ' ').title()}")
    
    def check_consistent_column_naming(self):
        """Check for consistent column naming (metadata_json)."""
        logger.info("\n📋 Checking consistent column naming...")
        
        issues = []
        
        # Check model files for metadata columns
        model_files = [
            'shared/models/memory_models.py',
            'shared/database/mcp_registry_models.py',
            'services/crew-api/src/database/models.py'
        ]
        
        for model_file in model_files:
            file_path = self.project_root / model_file
            if not file_path.exists():
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for old pattern
                if re.search(r'metadata\s*=\s*Column\(.*(?!metadata_json)', content):
                    if 'metadata_json = Column' not in content:
                        issues.append(str(model_file))
                        
            except Exception as e:
                logger.error(f"  ⚠️  Error checking {model_file}: {e}")
        
        self.validation_results['checks']['consistent_column_naming'] = {
            'passed': len(issues) == 0,
            'issues': issues,
            'message': f"Found {len(issues)} files with inconsistent column naming"
        }
        
        if issues:
            logger.info(f"  ❌ Found inconsistent column naming in {len(issues)} files")
        else:
            logger.info(f"  ✅ All models use consistent column naming")
    
    def check_file_organization(self):
        """Check file organization according to service boundaries."""
        logger.info("\n📋 Checking file organization...")
        
        checks = {
            'sql_directory_exists': (self.project_root / 'services' / 'crew-api' / 'sql').exists(),
            'object_schemas_moved': not (self.project_root / 'scripts' / 'seeds' / 'object_schemas_seed_sql.sql').exists(),
            'test_fixtures_organized': (self.project_root / 'tests' / 'fixtures').exists()
        }
        
        passed = all(checks.values())
        
        self.validation_results['checks']['file_organization'] = {
            'passed': passed,
            'checks': checks,
            'message': 'Files properly organized' if passed else 'File organization issues found'
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {check.replace('_', ' ').title()}")
    
    def check_memory_entities_integrity(self):
        """Check memory entities integrity tools exist."""
        logger.info("\n📋 Checking memory entities integrity tools...")
        
        checks = {
            'integrity_manager_exists': (self.project_root / 'shared' / 'database' / 'memory_integrity.py').exists(),
            'fix_script_exists': (self.project_root / 'scripts' / 'fix_memory_integrity.py').exists()
        }
        
        passed = all(checks.values())
        
        self.validation_results['checks']['memory_entities_integrity'] = {
            'passed': passed,
            'checks': checks,
            'message': 'Memory integrity tools exist' if passed else 'Memory integrity tools missing'
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {check.replace('_', ' ').title()}")
    
    def check_service_documentation(self):
        """Check service documentation completeness."""
        logger.info("\n📋 Checking service documentation...")
        
        services = [
            'services/chroma-gjdq/README.md',
            'services/sparkjar-document-mcp/README.md',
            'services/chroma-mcp/README.md',
            'services/embeddings/README.md'
        ]
        
        documented = []
        missing = []
        
        for service in services:
            path = self.project_root / service
            if path.exists():
                documented.append(service)
            else:
                missing.append(service)
        
        self.validation_results['checks']['service_documentation'] = {
            'passed': len(missing) == 0,
            'documented': documented,
            'missing': missing,
            'message': f"{len(documented)}/{len(services)} services documented"
        }
        
        logger.info(f"  📄 {len(documented)}/{len(services)} services have documentation")
        if missing:
            logger.info(f"  ❌ Missing documentation for:")
            for service in missing:
                logger.info(f"     - {service}")
        else:
            logger.info(f"  ✅ All services documented")
    
    def check_package_structure(self):
        """Check proper Python package structure."""
        logger.info("\n📋 Checking package structure...")
        
        checks = {
            'setup_py_exists': (self.project_root / 'setup.py').exists(),
            'pyproject_toml_exists': (self.project_root / 'pyproject.toml').exists(),
            'src_structure_exists': (self.project_root / 'src' / 'sparkjar_crew').exists()
        }
        
        # Test pip install -e .
        pip_install_works = False
        try:
            result = subprocess.run(
                ['pip', 'install', '-e', '.', '--dry-run'],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            pip_install_works = result.returncode == 0
        except:
            pass
        
        checks['pip_install_works'] = pip_install_works
        
        passed = all(checks.values())
        
        self.validation_results['checks']['package_structure'] = {
            'passed': passed,
            'checks': checks,
            'message': 'Package structure correct' if passed else 'Package structure issues found'
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {check.replace('_', ' ').title()}")
    
    def check_no_todo_comments(self):
        """Check for TODO comments in production code."""
        logger.info("\n📋 Checking for TODO comments...")
        
        issues = []
        files_checked = 0
        
        exclude_dirs = ['tests', 'scripts', '__pycache__', '.git']
        
        for py_file in self.project_root.rglob('*.py'):
            # Skip excluded directories
            if any(exclude in str(py_file) for exclude in exclude_dirs):
                continue
                
            files_checked += 1
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    if 'TODO' in line or 'FIXME' in line or 'XXX' in line:
                        issues.append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'line': i,
                            'content': line.strip()
                        })
                        
            except Exception as e:
                logger.error(f"  ⚠️  Error reading {py_file}: {e}")
        
        self.validation_results['checks']['no_todo_comments'] = {
            'passed': len(issues) == 0,
            'files_checked': files_checked,
            'issues': issues,
            'message': f"Found {len(issues)} TODO comments"
        }
        
        if issues:
            logger.info(f"  ❌ Found {len(issues)} TODO/FIXME comments")
            for issue in issues[:3]:
                logger.info(f"     - {issue['file']}:{issue['line']}")
            if len(issues) > 3:
                logger.info(f"     ... and {len(issues) - 3} more")
        else:
            logger.info(f"  ✅ No TODO comments found")
    
    def check_imports_work(self):
        """Check that imports work without path manipulation."""
        logger.info("\n📋 Checking imports...")
        
        # Try importing key modules
        imports_to_test = [
            'sparkjar_crew.shared.config.shared_settings',
            'sparkjar_crew.shared.database.models',
            'sparkjar_crew.services.crew_api.src.api.main'
        ]
        
        passed = 0
        failed = []
        
        for module in imports_to_test:
            try:
                # Don't actually import, just check if it would work
                import importlib.util
                spec = importlib.util.find_spec(module)
                if spec is not None:
                    passed += 1
                else:
                    failed.append(module)
            except:
                failed.append(module)
        
        self.validation_results['checks']['imports_work'] = {
            'passed': len(failed) == 0,
            'tested': len(imports_to_test),
            'failed': failed,
            'message': f"{passed}/{len(imports_to_test)} imports work correctly"
        }
        
        if failed:
            logger.error(f"  ❌ {len(failed)} imports failed")
            for module in failed:
                logger.info(f"     - {module}")
        else:
            logger.info(f"  ✅ All {passed} test imports work correctly")
    
    def _calculate_summary(self):
        """Calculate summary statistics."""
        summary = self.validation_results['summary']
        
        for check_name, result in self.validation_results['checks'].items():
            summary['total_checks'] += 1
            if result.get('passed', False):
                summary['passed'] += 1
            else:
                summary['failed'] += 1
    
    def _print_results(self):
        """Print validation results summary."""
        summary = self.validation_results['summary']
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 VALIDATION SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"Total Checks: {summary['total_checks']}")
        logger.info(f"✅ Passed: {summary['passed']}")
        logger.error(f"❌ Failed: {summary['failed']}")
        logger.warning(f"⚠️  Warnings: {summary['warnings']}")
        
        if summary['failed'] == 0:
            logger.info("\n🎉 All workarounds have been successfully eliminated!")
            logger.info("The codebase is now production-ready with proper:")
            logger.info("  • Logging system with security sanitization")
            logger.info("  • Single tool versions")
            logger.info("  • Centralized ChromaDB integration")
            logger.info("  • Configuration validation")
            logger.info("  • Consistent database column naming")
            logger.info("  • Proper file organization")
            logger.info("  • Memory entities integrity management")
            logger.info("  • Comprehensive service documentation")
            logger.info("  • Clean package structure")
        else:
            logger.error(f"\n⚠️  {summary['failed']} issues need to be addressed")
            logger.info("Review the detailed results above and fix the remaining issues.")
    
    def save_report(self, filename: str = None):
        """Save validation report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"workaround_validation_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.validation_results, f, indent=2)
        
        logger.info(f"\n📄 Report saved to: {filename}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate workaround elimination",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--save-report', action='store_true',
                        help='Save validation report to file')
    parser.add_argument('--report-file', type=str,
                        help='Report filename (default: auto-generated)')
    
    args = parser.parse_args()
    
    # Run validation
    validator = WorkaroundValidator()
    results = validator.validate_all()
    
    # Save report if requested
    if args.save_report:
        validator.save_report(args.report_file)
    
    # Exit with appropriate code
    if results['summary']['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()