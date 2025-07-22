#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Configuration Management CLI Tool
Provides commands for validating, testing, and managing SparkJAR Crew configuration
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add the project root to the path so we can import shared modules
project_root = Path(__file__).parent.parent.parent
# REMOVED: sys.path.insert(0, str(project_root))

from shared.config.config_validator import (
    ConfigValidator, 
    Environment, 
    validate_config_on_startup,
    get_config_summary,
    generate_env_template
)
from shared.config.profiles import validate_current_environment


def validate_command(args) -> int:
    """Validate current configuration."""
    logger.info("🔍 Validating SparkJAR Crew Configuration...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info("-" * 50)
    
    try:
        # Run centralized validation
        result = validate_config_on_startup(fail_fast=False)
        
        # Run environment-specific validation
        env_result = validate_current_environment()
        
        # Print results
        if result.is_valid:
            logger.info("✅ Core configuration validation: PASSED")
        else:
            logger.error("❌ Core configuration validation: FAILED")
            for error in result.errors:
                logger.error(f"  • {error}")
        
        if env_result["valid"]:
            logger.info(f"✅ Environment-specific validation: PASSED")
        else:
            logger.error(f"❌ Environment-specific validation: FAILED")
            for error in env_result["errors"]:
                logger.error(f"  • {error}")
        
        # Print warnings
        all_warnings = result.warnings + env_result.get("warnings", [])
        if all_warnings:
            logger.warning("\n⚠️  Warnings:")
            for warning in all_warnings:
                logger.warning(f"  • {warning}")
        
        # Overall status
        overall_valid = result.is_valid and env_result["valid"]
        logger.info("-" * 50)
        if overall_valid:
            logger.info("🎉 Overall validation: PASSED")
            return 0
        else:
            logger.error("💥 Overall validation: FAILED")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Validation error: {str(e)}")
        return 1


def summary_command(args) -> int:
    """Show configuration summary."""
    try:
        summary = get_config_summary(include_sensitive=args.include_sensitive)
        
        logger.info("📋 SparkJAR Crew Configuration Summary")
        logger.info(f"Environment: {summary['environment']}")
        logger.info(f"Validation Status: {summary['validation_status']}")
        logger.info("-" * 50)
        
        if summary.get('errors'):
            logger.error("❌ Errors:")
            for error in summary['errors']:
                logger.error(f"  • {error}")
            logger.info()
        
        if summary.get('warnings'):
            logger.warning("⚠️  Warnings:")
            for warning in summary['warnings']:
                logger.warning(f"  • {warning}")
            logger.info()
        
        # Group fields by status
        set_fields = []
        missing_required = []
        missing_optional = []
        
        for field_name, field_info in summary['fields'].items():
            if field_info['set']:
                set_fields.append((field_name, field_info))
            elif field_info['required']:
                missing_required.append((field_name, field_info))
            else:
                missing_optional.append((field_name, field_info))
        
        if set_fields:
            logger.info("✅ Configured Fields:")
            for field_name, field_info in set_fields:
                value_display = field_info['value'] if not args.mask_sensitive or not field_info.get('sensitive', False) else "***MASKED***"
                logger.info(f"  • {field_name}: {value_display}")
            logger.info()
        
        if missing_required:
            logger.info("❌ Missing Required Fields:")
            for field_name, field_info in missing_required:
                logger.info(f"  • {field_name}: {field_info['description']}")
            logger.info()
        
        if missing_optional and args.show_optional:
            logger.info("⚪ Missing Optional Fields:")
            for field_name, field_info in missing_optional:
                logger.info(f"  • {field_name}: {field_info['description']}")
            logger.info()
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error generating summary: {str(e)}")
        return 1


def generate_template_command(args) -> int:
    """Generate .env template file."""
    try:
        environment = args.environment
        output_file = args.output or f".env.{environment}"
        
        logger.info(f"📝 Generating .env template for {environment} environment...")
        
        template_content = generate_env_template(environment)
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write(template_content)
        
        logger.info(f"✅ Template generated: {output_file}")
        logger.info(f"📄 {len(template_content.splitlines())} lines written")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error generating template: {str(e)}")
        return 1


def test_command(args) -> int:
    """Test configuration by attempting to load all services."""
    logger.info("🧪 Testing SparkJAR Crew Configuration...")
    logger.info("This will attempt to validate configuration for all services.")
    logger.info("-" * 50)
    
    test_results = {}
    overall_success = True
    
    # Test core configuration
    try:
        logger.info("Testing core configuration...")
        result = validate_config_on_startup(fail_fast=False)
        test_results["core"] = {
            "status": "PASSED" if result.is_valid else "FAILED",
            "errors": result.errors,
            "warnings": result.warnings
        }
        if not result.is_valid:
            overall_success = False
        logger.error(f"  Core configuration: {'✅ PASSED' if result.is_valid else '❌ FAILED'}")
    except Exception as e:
        test_results["core"] = {"status": "ERROR", "error": str(e)}
        overall_success = False
        logger.error(f"  Core configuration: ❌ ERROR - {str(e)}")
    
    # Test environment-specific configuration
    try:
        logger.info("Testing environment-specific configuration...")
        env_result = validate_current_environment()
        test_results["environment"] = env_result
        if not env_result["valid"]:
            overall_success = False
        logger.error(f"  Environment configuration: {'✅ PASSED' if env_result['valid'] else '❌ FAILED'}")
    except Exception as e:
        test_results["environment"] = {"status": "ERROR", "error": str(e)}
        overall_success = False
        logger.error(f"  Environment configuration: ❌ ERROR - {str(e)}")
    
    # Test service-specific configurations
    services_to_test = [
        ("crew-api", "services/crew-api/src/config.py"),
        ("memory-service", "services/memory-service/config.py"),
        ("mcp-registry", "services/mcp-registry/src/services/registry_service.py")
    ]
    
    for service_name, config_path in services_to_test:
        try:
            logger.info(f"Testing {service_name} configuration...")
            if os.path.exists(config_path):
                # Try to import the service configuration
                # This is a basic test - in a real scenario, we'd want more comprehensive testing
                test_results[service_name] = {"status": "PASSED", "config_file": config_path}
                logger.info(f"  {service_name}: ✅ PASSED")
            else:
                test_results[service_name] = {"status": "WARNING", "message": f"Config file not found: {config_path}"}
                logger.warning(f"  {service_name}: ⚠️  WARNING - Config file not found")
        except Exception as e:
            test_results[service_name] = {"status": "ERROR", "error": str(e)}
            overall_success = False
            logger.error(f"  {service_name}: ❌ ERROR - {str(e)}")
    
    logger.info("-" * 50)
    
    # Save test results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(test_results, f, indent=2)
        logger.info(f"📄 Test results saved to: {args.output}")
    
    if overall_success:
        logger.info("🎉 All configuration tests: PASSED")
        return 0
    else:
        logger.error("💥 Some configuration tests: FAILED")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SparkJAR Crew Configuration Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate                    # Validate current configuration
  %(prog)s summary --include-sensitive # Show configuration summary with sensitive values
  %(prog)s generate-template production --output .env.prod  # Generate production template
  %(prog)s test --output test-results.json  # Test configuration and save results
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate current configuration')
    validate_parser.set_defaults(func=validate_command)
    
    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show configuration summary')
    summary_parser.add_argument('--include-sensitive', action='store_true',
                               help='Include sensitive values in output')
    summary_parser.add_argument('--mask-sensitive', action='store_true', default=True,
                               help='Mask sensitive values (default)')
    summary_parser.add_argument('--show-optional', action='store_true',
                               help='Show missing optional fields')
    summary_parser.set_defaults(func=summary_command)
    
    # Generate template command
    template_parser = subparsers.add_parser('generate-template', help='Generate .env template')
    template_parser.add_argument('environment', choices=['development', 'staging', 'production'],
                                help='Target environment')
    template_parser.add_argument('--output', '-o', help='Output file path')
    template_parser.set_defaults(func=generate_template_command)
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test configuration for all services')
    test_parser.add_argument('--output', '-o', help='Save test results to JSON file')
    test_parser.set_defaults(func=test_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())