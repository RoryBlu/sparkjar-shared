#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Security validation script for SparkJAR Crew
Scans for common security vulnerabilities and misconfigurations
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple

class SecurityValidator:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.issues = []
        
    def add_issue(self, severity: str, category: str, file_path: str, line_num: int, description: str, evidence: str = ""):
        """Add a security issue to the report"""
        self.issues.append({
            "severity": severity,
            "category": category,
            "file": str(file_path),
            "line": line_num,
            "description": description,
            "evidence": evidence
        })
    
    def scan_hardcoded_secrets(self):
        """Scan for hardcoded secrets, API keys, passwords, and tokens"""
        logger.info("🔍 Scanning for hardcoded secrets...")
        
        # Patterns to look for
        patterns = [
            (r'(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*["\'][^"\']{10,}["\']', "Potential hardcoded secret"),
            (r'postgresql://[^"\'\\s]+:[^"\'\\s]+@[^"\'\\s]+', "Hardcoded database URL with credentials"),
            (r'eyJ[A-Za-z0-9+/=]+\.[A-Za-z0-9+/=]+\.[A-Za-z0-9+/=]+', "JWT token"),
            (r'sk-[A-Za-z0-9]{48}', "OpenAI API key"),
            (r'xoxb-[0-9]+-[0-9]+-[A-Za-z0-9]+', "Slack bot token"),
            (r'ghp_[A-Za-z0-9]{36}', "GitHub personal access token"),
            (r'AKIA[0-9A-Z]{16}', "AWS access key"),
        ]
        
        # Files to exclude from scanning
        exclude_patterns = [
            r'\.git/',
            r'__pycache__/',
            r'\.venv/',
            r'venv/',
            r'node_modules/',
            r'\.log$',
            r'\.pyc$',
            r'SECURITY_AUDIT_REPORT\.md$',
            r'security_validation\.py$'
        ]
        
        for file_path in self.root_path.rglob("*"):
            if file_path.is_file():
                # Skip excluded files
                if any(re.search(pattern, str(file_path)) for pattern in exclude_patterns):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        
                    for line_num, line in enumerate(lines, 1):
                        for pattern, description in patterns:
                            matches = re.finditer(pattern, line)
                            for match in matches:
                                # Skip documentation examples
                                if any(keyword in line.lower() for keyword in ['example', 'placeholder', 'your-', 'dummy', 'test-']):
                                    continue
                                
                                severity = "CRITICAL" if "postgresql://" in match.group() or "eyJ" in match.group() else "HIGH"
                                self.add_issue(
                                    severity=severity,
                                    category="Hardcoded Secrets",
                                    file_path=file_path,
                                    line_num=line_num,
                                    description=description,
                                    evidence=match.group()[:50] + "..." if len(match.group()) > 50 else match.group()
                                )
                                
                except Exception as e:
                    continue
    
    def scan_sql_injection_risks(self):
        """Scan for potential SQL injection vulnerabilities"""
        logger.info("🔍 Scanning for SQL injection risks...")
        
        patterns = [
            (r'execute\s*\(\s*["\'].*%.*["\']', "String formatting in SQL execute"),
            (r'execute\s*\(\s*f["\'].*{.*}.*["\']', "F-string in SQL execute"),
            (r'query\s*\(\s*["\'].*%.*["\']', "String formatting in SQL query"),
            (r'query\s*\(\s*f["\'].*{.*}.*["\']', "F-string in SQL query"),
        ]
        
        for file_path in self.root_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    for pattern, description in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            self.add_issue(
                                severity="HIGH",
                                category="SQL Injection Risk",
                                file_path=file_path,
                                line_num=line_num,
                                description=description,
                                evidence=line.strip()
                            )
            except Exception:
                continue
    
    def scan_authentication_issues(self):
        """Scan for authentication and authorization issues"""
        logger.info("🔍 Scanning for authentication issues...")
        
        # Look for endpoints without authentication
        for file_path in self.root_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                # Look for FastAPI routes without dependencies
                for line_num, line in enumerate(lines, 1):
                    if re.search(r'@app\.(get|post|put|delete|patch)', line, re.IGNORECASE):
                        # Check if the next few lines have authentication
                        auth_found = False
                        for i in range(max(0, line_num-3), min(len(lines), line_num+5)):
                            if 'Depends' in lines[i] and ('auth' in lines[i].lower() or 'token' in lines[i].lower()):
                                auth_found = True
                                break
                        
                        if not auth_found and 'health' not in line.lower():
                            self.add_issue(
                                severity="MEDIUM",
                                category="Authentication",
                                file_path=file_path,
                                line_num=line_num,
                                description="API endpoint without authentication",
                                evidence=line.strip()
                            )
            except Exception:
                continue
    
    def scan_environment_variables(self):
        """Check for proper environment variable usage"""
        logger.info("🔍 Scanning environment variable usage...")
        
        # Look for missing environment variable validation
        for file_path in self.root_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    # Look for os.getenv without default or validation
                    if re.search(r'os\.getenv\s*\(\s*["\'][^"\']+["\'](?:\s*,\s*None)?\s*\)', line):
                        # Check if there's validation in the next few lines
                        validation_found = False
                        for i in range(line_num, min(len(lines), line_num+3)):
                            if 'if not' in lines[i] or 'raise' in lines[i] or 'sys.exit' in lines[i]:
                                validation_found = True
                                break
                        
                        if not validation_found:
                            self.add_issue(
                                severity="LOW",
                                category="Configuration",
                                file_path=file_path,
                                line_num=line_num,
                                description="Environment variable without validation",
                                evidence=line.strip()
                            )
            except Exception:
                continue
    
    def scan_logging_security(self):
        """Check for security issues in logging"""
        logger.info("🔍 Scanning logging security...")
        
        patterns = [
            (r'log.*password', "Password in log statement"),
            (r'log.*token', "Token in log statement"),
            (r'log.*secret', "Secret in log statement"),
            (r'log.*key', "Key in log statement"),
            (r'print\s*\(.*password', "Password in print statement"),
            (r'print\s*\(.*token', "Token in print statement"),
        ]
        
        for file_path in self.root_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    for pattern, description in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            self.add_issue(
                                severity="MEDIUM",
                                category="Information Disclosure",
                                file_path=file_path,
                                line_num=line_num,
                                description=description,
                                evidence=line.strip()
                            )
            except Exception:
                continue
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive security report"""
        # Group issues by severity
        critical = [issue for issue in self.issues if issue["severity"] == "CRITICAL"]
        high = [issue for issue in self.issues if issue["severity"] == "HIGH"]
        medium = [issue for issue in self.issues if issue["severity"] == "MEDIUM"]
        low = [issue for issue in self.issues if issue["severity"] == "LOW"]
        
        report = {
            "summary": {
                "total_issues": len(self.issues),
                "critical": len(critical),
                "high": len(high),
                "medium": len(medium),
                "low": len(low)
            },
            "issues": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low
            }
        }
        
        return report
    
    def run_all_scans(self):
        """Run all security scans"""
        logger.info("🚀 Starting comprehensive security scan...")
        
        self.scan_hardcoded_secrets()
        self.scan_sql_injection_risks()
        self.scan_authentication_issues()
        self.scan_environment_variables()
        self.scan_logging_security()
        
        return self.generate_report()

def main():
    validator = SecurityValidator()
    report = validator.run_all_scans()
    
    logger.info("\n" + "="*60)
    logger.info("🔒 SECURITY SCAN RESULTS")
    logger.info("="*60)
    
    logger.info(f"\n📊 SUMMARY:")
    logger.info(f"   Total Issues: {report['summary']['total_issues']}")
    logger.info(f"   Critical: {report['summary']['critical']}")
    logger.info(f"   High: {report['summary']['high']}")
    logger.info(f"   Medium: {report['summary']['medium']}")
    logger.info(f"   Low: {report['summary']['low']}")
    
    # Print critical and high issues
    for severity in ["critical", "high"]:
        issues = report["issues"][severity]
        if issues:
            logger.info(f"\n🚨 {severity.upper()} ISSUES:")
            for issue in issues:
                logger.info(f"   📁 {issue['file']}:{issue['line']}")
                logger.info(f"   📝 {issue['description']}")
                logger.info(f"   🔍 {issue['evidence']}")
                logger.info()
    
    # Save detailed report
    with open("security_scan_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"📄 Detailed report saved to: security_scan_report.json")
    
    # Exit with error code if critical or high issues found
    if report['summary']['critical'] > 0 or report['summary']['high'] > 0:
        logger.error("\n❌ SECURITY SCAN FAILED - Critical or High severity issues found!")
        sys.exit(1)
    else:
        logger.info("\n✅ SECURITY SCAN PASSED - No critical or high severity issues found!")
        sys.exit(0)

if __name__ == "__main__":
    main()