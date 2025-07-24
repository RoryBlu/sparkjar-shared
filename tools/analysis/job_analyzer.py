#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Consolidated job analysis tool that combines functionality from analyze_job_completion.py and analyze_job_summary.py.

Usage:
    python job_analyzer.py --job-id <job-id> [--mode summary|completion|full]
    python job_analyzer.py --job-id <job-id> --search <pattern>
    python job_analyzer.py --job-id <job-id> --event-types
"""

import os
import sys
import json
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class JobAnalyzer:
    """Consolidated job analysis tool."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        # Database connection
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable not set")
        self.db_url = db_url.replace("+asyncpg", "")
        self.conn = None
        
    def __enter__(self):
        self.conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_job_status(self) -> Optional[Dict[str, Any]]:
        """Get basic job information and status."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, job_key, status, created_at, started_at, completed_at, client_id
                FROM crew_jobs 
                WHERE id = %s
            """, (self.job_id,))
            return cur.fetchone()
    
    def get_event_counts(self) -> List[Dict[str, Any]]:
        """Get counts of different event types."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT event_type, COUNT(*) as count 
                FROM crew_job_event 
                WHERE job_id = %s 
                GROUP BY event_type 
                ORDER BY count DESC
            """, (self.job_id,))
            return cur.fetchall()
    
    def search_events(self, pattern: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for events containing a specific pattern."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT event_time, event_type, event_data
                FROM crew_job_event 
                WHERE job_id = %s 
                AND event_data::text ILIKE %s
                ORDER BY event_time DESC
                LIMIT %s
            """, (self.job_id, f'%{pattern}%', limit))
            return cur.fetchall()
    
    def get_report_events(self) -> List[Dict[str, Any]]:
        """Get events related to report generation."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT event_time, event_type, event_data
                FROM crew_job_event 
                WHERE job_id = %s 
                AND event_type IN ('task_complete', 'agent_thought')
                AND event_data::text ILIKE '%report%'
                ORDER BY event_time DESC
                LIMIT 10
            """, (self.job_id,))
            return cur.fetchall()
    
    def get_tool_usage(self) -> List[Dict[str, Any]]:
        """Get tool usage statistics."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    event_data->>'tool_name' as tool_name,
                    COUNT(*) as usage_count
                FROM crew_job_event 
                WHERE job_id = %s 
                AND event_type = 'tool_use'
                AND event_data->>'tool_name' IS NOT NULL
                GROUP BY event_data->>'tool_name'
                ORDER BY usage_count DESC
            """, (self.job_id,))
            return cur.fetchall()
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """Get error events."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT event_time, event_type, event_data
                FROM crew_job_event 
                WHERE job_id = %s 
                AND (
                    event_type = 'error' 
                    OR event_data::text ILIKE '%error%'
                    OR event_data::text ILIKE '%failed%'
                )
                ORDER BY event_time DESC
                LIMIT 20
            """, (self.job_id,))
            return cur.fetchall()
    
    def get_completion_events(self) -> List[Dict[str, Any]]:
        """Get job completion events."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT event_time, event_type, event_data
                FROM crew_job_event 
                WHERE job_id = %s 
                AND event_type IN ('crew_complete', 'crew_execution_end', 'job_completed', 'task_complete')
                ORDER BY event_time DESC
                LIMIT 10
            """, (self.job_id,))
            return cur.fetchall()
    
    def print_summary(self):
        """Print a comprehensive job summary."""
        logger.info(f"📊 JOB EXECUTION SUMMARY: {self.job_id}")
        logger.info("=" * 80)
        
        # Job status
        job = self.get_job_status()
        if not job:
            logger.info("❌ Job not found!")
            return
            
        logger.info(f"\n✅ Job Status: {job['status'].upper()}")
        logger.info(f"   Job Key: {job['job_key']}")
        logger.info(f"   Client ID: {job['client_id']}")
        logger.info(f"   Created: {job['created_at']}")
        if job['started_at']:
            logger.info(f"   Started: {job['started_at']}")
        if job['completed_at']:
            logger.info(f"   Completed: {job['completed_at']}")
            if job['started_at']:
                duration = (job['completed_at'] - job['started_at']).total_seconds()
                logger.info(f"   Duration: {duration:.1f} seconds")
        
        # Event counts
        logger.info("\n📈 Event Summary:")
        event_counts = self.get_event_counts()
        for event in event_counts:
            logger.info(f"   {event['event_type']}: {event['count']}")
        
        # Tool usage
        logger.info("\n🔧 Tool Usage:")
        tools = self.get_tool_usage()
        if tools:
            for tool in tools:
                logger.info(f"   {tool['tool_name']}: {tool['usage_count']} times")
        else:
            logger.info("   No tool usage recorded")
        
        # Reports
        logger.info("\n📄 Report Generation:")
        report_events = self.get_report_events()
        if report_events:
            logger.info(f"   Found {len(report_events)} report-related events")
            # Check for final report
            for event in report_events:
                if isinstance(event['event_data'], dict) and 'output' in event['event_data']:
                    output = str(event['event_data']['output'])
                    if '# Executive Intelligence Report' in output or '# ' in output:
                        logger.info("   ✅ Report successfully generated")
                        break
        else:
            logger.info("   No report generation events found")
        
        # Errors
        logger.error("\n⚠️  Errors:")
        errors = self.get_errors()
        if errors:
            logger.error(f"   Found {len(errors)} error-related events")
            # Show first few errors
            for i, error in enumerate(errors[:3]):
                logger.error(f"   Error {i+1} at {error['event_time']}: {error['event_type']}")
        else:
            logger.error("   No errors found")
        
        logger.info("\n" + "=" * 80)
        logger.info("📌 SUMMARY COMPLETE")
    
    def print_completion_details(self):
        """Print detailed completion analysis."""
        logger.info(f"🔍 JOB COMPLETION ANALYSIS: {self.job_id}")
        logger.info("=" * 80)
        
        # Check job exists
        job = self.get_job_status()
        if not job:
            logger.info("❌ Job not found!")
            return
        
        # Report generation details
        logger.info("\n📄 REPORT GENERATION:")
        report_events = self.get_report_events()
        for event in report_events[:5]:
            logger.info(f"\n  Time: {event['event_time']}")
            logger.info(f"  Type: {event['event_type']}")
            if isinstance(event['event_data'], dict):
                if 'output' in event['event_data']:
                    output = str(event['event_data']['output'])[:500]
                    logger.info(f"  Output: {output}...")
                elif 'task_name' in event['event_data']:
                    logger.info(f"  Task: {event['event_data']['task_name']}")
        
        # Document operations
        logger.info("\n💾 DOCUMENT OPERATIONS:")
        doc_events = self.search_events('document', 5)
        if doc_events:
            for event in doc_events:
                logger.info(f"\n  Time: {event['event_time']}")
                logger.info(f"  Type: {event['event_type']}")
                if isinstance(event['event_data'], dict) and 'tool_name' in event['event_data']:
                    logger.info(f"  Tool: {event['event_data']['tool_name']}")
        else:
            logger.info("  No document operations found")
        
        # Email operations
        logger.info("\n📧 EMAIL OPERATIONS:")
        email_events = self.search_events('email', 5)
        if email_events:
            for event in email_events:
                logger.info(f"\n  Time: {event['event_time']}")
                logger.info(f"  Type: {event['event_type']}")
                if isinstance(event['event_data'], dict):
                    if 'message' in event['event_data']:
                        logger.info(f"  Message: {event['event_data']['message']}")
        else:
            logger.info("  No email operations found")
        
        # Final completion
        logger.info("\n✅ COMPLETION EVENTS:")
        completion_events = self.get_completion_events()
        for event in completion_events[:5]:
            logger.info(f"\n  Time: {event['event_time']}")
            logger.info(f"  Type: {event['event_type']}")
            if isinstance(event['event_data'], dict):
                if 'status' in event['event_data']:
                    logger.info(f"  Status: {event['event_data']['status']}")
                if 'message' in event['event_data']:
                    logger.info(f"  Message: {event['event_data']['message']}")
        
        logger.info("\n" + "=" * 80)
        logger.info("📌 COMPLETION ANALYSIS COMPLETE")
    
    def print_event_types(self):
        """Print all unique event types."""
        event_counts = self.get_event_counts()
        logger.info(f"\n📋 EVENT TYPES FOR JOB {self.job_id}:")
        logger.info("=" * 80)
        for event in event_counts:
            logger.info(f"  {event['event_type']:<30} {event['count']:>10} events")
        logger.info("=" * 80)
        logger.info(f"Total event types: {len(event_counts)}")

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Analyze CrewAI job execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get summary of a job
  python job_analyzer.py --job-id d3034f03-581f-455e-9bc1-78e075ae2749 --mode summary
  
  # Get detailed completion analysis
  python job_analyzer.py --job-id d3034f03-581f-455e-9bc1-78e075ae2749 --mode completion
  
  # Search for specific patterns
  python job_analyzer.py --job-id d3034f03-581f-455e-9bc1-78e075ae2749 --search "google drive"
  
  # List all event types
  python job_analyzer.py --job-id d3034f03-581f-455e-9bc1-78e075ae2749 --event-types
        """
    )
    
    parser.add_argument('--job-id', required=True, help='Job ID to analyze')
    parser.add_argument('--mode', choices=['summary', 'completion', 'full'], 
                        default='summary', help='Analysis mode')
    parser.add_argument('--search', help='Search for specific pattern in events')
    parser.add_argument('--event-types', action='store_true', 
                        help='List all event types for the job')
    
    args = parser.parse_args()
    
    try:
        with JobAnalyzer(args.job_id) as analyzer:
            if args.search:
                logger.info(f"\n🔍 SEARCHING FOR: '{args.search}'")
                logger.info("=" * 80)
                events = analyzer.search_events(args.search)
                if events:
                    for i, event in enumerate(events):
                        logger.info(f"\nResult {i+1}:")
                        logger.info(f"  Time: {event['event_time']}")
                        logger.info(f"  Type: {event['event_type']}")
                        # Truncate large event data
                        data_str = str(event['event_data'])
                        if len(data_str) > 500:
                            data_str = data_str[:500] + "..."
                        logger.info(f"  Data: {data_str}")
                else:
                    logger.info("No matching events found.")
            
            elif args.event_types:
                analyzer.print_event_types()
            
            else:
                if args.mode == 'summary':
                    analyzer.print_summary()
                elif args.mode == 'completion':
                    analyzer.print_completion_details()
                elif args.mode == 'full':
                    analyzer.print_summary()
                    logger.info("\n")
                    analyzer.print_completion_details()
                    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()