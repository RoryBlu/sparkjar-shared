#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Find and analyze retry loops in crew job events.
Identifies where agents are getting stuck in retry patterns.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Add parent directory to path

from dotenv import load_dotenv
load_dotenv()

class RetryLoopAnalyzer:
    """Analyze retry patterns and loops in crew job execution"""
    
    def __init__(self):
        # Database connection
        db_url = os.getenv("DATABASE_URL_POOLED", os.getenv("DATABASE_URL"))
        if not db_url:
            raise ValueError("DATABASE_URL not found")
        
        db_url = db_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
    
    def analyze_job_retries(self, job_id: str) -> Dict[str, Any]:
        """Analyze retry patterns for a specific job"""
        logger.info(f"\n🔍 Analyzing retry patterns for job: {job_id}")
        
        # Get all events for the job
        query = text("""
            SELECT id, event_time, event_type, event_data
            FROM crew_job_event
            WHERE job_id = :job_id
            ORDER BY event_time, id
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"job_id": job_id})
            events = []
            for row in result:
                events.append({
                    "id": row.id,
                    "time": row.event_time,
                    "type": row.event_type,
                    "data": row.event_data or {}
                })
        
        logger.info(f"Found {len(events)} total events")
        
        # Analyze retry patterns
        retry_sequences = self.identify_retry_sequences(events)
        agent_retries = self.count_agent_retries(events)
        retry_reasons = self.analyze_retry_reasons(events)
        stuck_tools = self.identify_stuck_tools(events)
        
        return {
            "total_events": len(events),
            "retry_sequences": retry_sequences,
            "agent_retries": agent_retries,
            "retry_reasons": retry_reasons,
            "stuck_tools": stuck_tools
        }
    
    def identify_retry_sequences(self, events: List[Dict]) -> List[Dict]:
        """Identify sequences of retry attempts"""
        sequences = []
        current_sequence = []
        last_retry_time = None
        
        for event in events:
            if event["type"] == "retry_attempt":
                if last_retry_time and (event["time"] - last_retry_time).total_seconds() > 300:
                    # Gap of more than 5 minutes, new sequence
                    if current_sequence:
                        sequences.append(self.analyze_sequence(current_sequence))
                    current_sequence = []
                
                current_sequence.append(event)
                last_retry_time = event["time"]
            
            elif event["type"] in ["task_complete", "crew_complete"] and current_sequence:
                # Task completed, end sequence
                sequences.append(self.analyze_sequence(current_sequence))
                current_sequence = []
                last_retry_time = None
        
        # Don't forget the last sequence
        if current_sequence:
            sequences.append(self.analyze_sequence(current_sequence))
        
        return sequences
    
    def analyze_sequence(self, sequence: List[Dict]) -> Dict:
        """Analyze a retry sequence"""
        return {
            "start_time": sequence[0]["time"].isoformat(),
            "end_time": sequence[-1]["time"].isoformat(),
            "duration_seconds": (sequence[-1]["time"] - sequence[0]["time"]).total_seconds(),
            "retry_count": len(sequence),
            "reasons": [event["data"].get("reason", "Unknown") for event in sequence]
        }
    
    def count_agent_retries(self, events: List[Dict]) -> Dict[str, int]:
        """Count retries per agent"""
        agent_retries = defaultdict(int)
        
        for event in events:
            if event["type"] == "retry_attempt":
                agent = event["data"].get("agent", "Unknown")
                agent_retries[agent] += 1
        
        return dict(agent_retries)
    
    def analyze_retry_reasons(self, events: List[Dict]) -> Dict[str, int]:
        """Analyze reasons for retries"""
        reasons = Counter()
        
        for event in events:
            if event["type"] == "retry_attempt":
                reason = event["data"].get("reason", "Unknown")
                reasons[reason] += 1
        
        return dict(reasons)
    
    def identify_stuck_tools(self, events: List[Dict]) -> Dict[str, Any]:
        """Identify tools that are causing retry loops"""
        tool_retries = defaultdict(list)
        
        # Look for patterns: tool execution -> error -> retry
        for i in range(len(events) - 2):
            if (events[i]["type"] == "tool_execution" and 
                events[i+1]["type"] == "error" and 
                events[i+2]["type"] == "retry_attempt"):
                
                tool_name = events[i]["data"].get("tool_name", "Unknown")
                error = events[i+1]["data"].get("error", "Unknown error")
                
                tool_retries[tool_name].append({
                    "time": events[i]["time"].isoformat(),
                    "error": error
                })
        
        # Summarize
        stuck_tools = {}
        for tool, retries in tool_retries.items():
            if len(retries) > 5:  # Tool failed more than 5 times
                stuck_tools[tool] = {
                    "failure_count": len(retries),
                    "unique_errors": len(set(r["error"] for r in retries)),
                    "sample_errors": list(set(r["error"] for r in retries))[:3]
                }
        
        return stuck_tools
    
    def find_high_retry_jobs(self, min_retries: int = 100) -> List[Tuple[str, int]]:
        """Find jobs with high retry counts"""
        query = text("""
            SELECT job_id, COUNT(*) as retry_count
            FROM crew_job_event
            WHERE event_type = 'retry_attempt'
            GROUP BY job_id
            HAVING COUNT(*) >= :min_retries
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"min_retries": min_retries})
            return [(row.job_id, row.retry_count) for row in result]
    
    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """Generate a retry analysis report"""
        report = f"""
# Retry Loop Analysis Report

Generated: {datetime.now().isoformat()}

## Summary
- Total Events: {analysis['total_events']}
- Retry Sequences Found: {len(analysis['retry_sequences'])}
- Total Retries: {sum(analysis['agent_retries'].values())}

## Agent Retry Counts
"""
        
        # Sort agents by retry count
        sorted_agents = sorted(analysis['agent_retries'].items(), key=lambda x: x[1], reverse=True)
        for agent, count in sorted_agents[:10]:
            report += f"- **{agent}**: {count} retries\n"
        
        report += "\n## Retry Reasons\n"
        sorted_reasons = sorted(analysis['retry_reasons'].items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_reasons[:10]:
            report += f"- {reason}: {count} occurrences\n"
        
        report += "\n## Longest Retry Sequences\n"
        sorted_sequences = sorted(analysis['retry_sequences'], key=lambda x: x['retry_count'], reverse=True)
        for i, seq in enumerate(sorted_sequences[:5], 1):
            report += f"""
### Sequence {i}
- Duration: {seq['duration_seconds']:.1f} seconds
- Retry Count: {seq['retry_count']}
- Time: {seq['start_time']} to {seq['end_time']}
"""
        
        if analysis['stuck_tools']:
            report += "\n## Problematic Tools\n"
            for tool, info in analysis['stuck_tools'].items():
                report += f"""
### {tool}
- Failures: {info['failure_count']}
- Unique Errors: {info['unique_errors']}
- Sample Errors:
"""
                for error in info['sample_errors']:
                    report += f"  - {error}\n"
        
        return report

def main():
    """Run retry loop analysis"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze retry loops in crew job execution")
    parser.add_argument("--job-id", help="Specific job ID to analyze")
    parser.add_argument("--find-high-retry", action="store_true", help="Find jobs with high retry counts")
    parser.add_argument("--min-retries", type=int, default=100, help="Minimum retries for high-retry search")
    
    args = parser.parse_args()
    
    analyzer = RetryLoopAnalyzer()
    
    if args.find_high_retry:
        logger.info(f"\n🔍 Finding jobs with >= {args.min_retries} retries...")
        high_retry_jobs = analyzer.find_high_retry_jobs(args.min_retries)
        
        if high_retry_jobs:
            logger.info(f"\nFound {len(high_retry_jobs)} jobs with high retry counts:\n")
            for job_id, retry_count in high_retry_jobs:
                logger.info(f"  {job_id}: {retry_count} retries")
            
            # Analyze the top one
            if not args.job_id:
                args.job_id = high_retry_jobs[0][0]
                logger.info(f"\nAnalyzing top job: {args.job_id}")
        else:
            logger.info(f"No jobs found with >= {args.min_retries} retries")
            return
    
    if args.job_id:
        analysis = analyzer.analyze_job_retries(args.job_id)
        report = analyzer.generate_report(analysis)
        
        # Save report
        job_id_str = str(args.job_id)
        report_path = f"/tmp/retry_analysis_{job_id_str[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_path, 'w') as f:
            f.write(report)
        
        logger.info(f"\n✅ Analysis complete!")
        logger.info(f"Report saved to: {report_path}")
        
        # Print summary
        logger.info(f"\n📊 Quick Summary:")
        logger.info(f"- Total retries: {sum(analysis['agent_retries'].values())}")
        logger.info(f"- Agents with most retries:")
        sorted_agents = sorted(analysis['agent_retries'].items(), key=lambda x: x[1], reverse=True)
        for agent, count in sorted_agents[:3]:
            logger.info(f"  - {agent}: {count}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()