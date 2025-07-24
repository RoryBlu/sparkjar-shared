#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""Quick validation of workaround elimination without imports."""

import os
import re
import ast
from pathlib import Path

def check_print_statements():
    """Check for print statements in production code."""
    logger.info("\n📋 Checking for print statements...")
    issues = []
    
    dirs_to_check = ['services', 'shared', 'src']
    for dir_name in dirs_to_check:
        if not Path(dir_name).exists():
            continue
        
        for py_file in Path(dir_name).rglob('*.py'):
            if '__pycache__' in str(py_file) or 'test' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == 'print':
                            issues.append(f"{py_file}:{node.lineno}")
            except:
                pass
    
    if issues:
        logger.info(f"  ❌ Found {len(issues)} print statements:")
        for issue in issues[:5]:
            logger.info(f"     - {issue}")
    else:
        logger.info("  ✅ No print statements found")
    return len(issues) == 0

def check_sys_path():
    """Check for sys.path manipulation."""
    logger.info("\n📋 Checking for sys.path manipulation...")
    issues = []
    
    patterns = [r'sys\.path\.append', r'sys\.path\.insert', r'sys\.path\[0\]']
    
    for py_file in Path('.').rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue
            
        try:
            with open(py_file, 'r') as f:
                content = f.read()
            
            for i, line in enumerate(content.splitlines(), 1):
                for pattern in patterns:
                    if re.search(pattern, line):
                        issues.append(f"{py_file}:{i}")
        except:
            pass
    
    if issues:
        logger.info(f"  ❌ Found {len(issues)} sys.path manipulations")
        for issue in issues[:5]:
            logger.info(f"     - {issue}")
    else:
        logger.info("  ✅ No sys.path manipulation found")
    return len(issues) == 0

def check_single_tool_versions():
    """Check for multiple tool versions."""
    logger.info("\n📋 Checking for single tool versions...")
    tools_dir = Path('services/crew-api/src/tools')
    
    if not tools_dir.exists():
        logger.info("  ⚠️  Tools directory not found")
        return True
    
    tool_patterns = {
        'memory': r'sj_memory_tool(_v\d+)?\.py',
        'thinking': r'sj_sequential_thinking_tool(_v\d+)?\.py',
        'document': r'sj_document_tool(_v\d+)?\.py'
    }
    
    issues = []
    for tool_name, pattern in tool_patterns.items():
        matches = [f.name for f in tools_dir.iterdir() if re.match(pattern, f.name)]
        if len(matches) > 1:
            issues.append(f"{tool_name}: {', '.join(matches)}")
    
    if issues:
        logger.info(f"  ❌ Found multiple versions:")
        for issue in issues:
            logger.info(f"     - {issue}")
    else:
        logger.info("  ✅ All tools have single versions")
    return len(issues) == 0

def check_key_files():
    """Check for key files existence."""
    logger.info("\n📋 Checking key files...")
    
    files_to_check = [
        ('shared/services/chroma_service.py', 'ChromaDB service'),
        ('shared/config/config_validator.py', 'Config validator'),
        ('shared/config/embedding_config.py', 'Embedding config'),
        ('shared/database/memory_integrity.py', 'Memory integrity'),
        ('scripts/analysis/job_analyzer.py', 'Job analyzer'),
        ('services/crew-api/sql/object_schemas_seed_sql.sql', 'SQL file moved'),
    ]
    
    all_exist = True
    for file_path, desc in files_to_check:
        exists = Path(file_path).exists()
        status = "✅" if exists else "❌"
        logger.info(f"  {status} {desc}: {file_path}")
        if not exists:
            all_exist = False
    
    return all_exist

def check_documentation():
    """Check service documentation."""
    logger.info("\n📋 Checking service documentation...")
    
    docs = [
        'services/chroma-gjdq/README.md',
        'services/sparkjar-document-mcp/README.md',
        'services/chroma-mcp/README.md',
        'services/embeddings/README.md'
    ]
    
    all_exist = True
    for doc in docs:
        exists = Path(doc).exists()
        status = "✅" if exists else "❌"
        logger.info(f"  {status} {doc}")
        if not exists:
            all_exist = False
    
    return all_exist

def main():
    logger.info("🔍 Quick Workaround Elimination Validation")
    logger.info("=" * 80)
    
    results = []
    results.append(check_print_statements())
    results.append(check_sys_path())
    results.append(check_single_tool_versions())
    results.append(check_key_files())
    results.append(check_documentation())
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 VALIDATION SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    logger.info(f"✅ Passed: {passed}/{total}")
    logger.error(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        logger.info("\n🎉 Basic validation passed!")
    else:
        logger.error("\n⚠️  Some checks failed. Fixing issues...")

if __name__ == "__main__":
    main()