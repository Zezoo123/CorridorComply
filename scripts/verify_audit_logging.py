#!/usr/bin/env python3
"""
Script to verify audit logging is working correctly.

This script checks:
1. If audit log directory exists
2. If audit log file exists
3. If recent logs contain required fields (request_payload, risk_score, timestamp, match summary)
4. Shows a sample of recent audit log entries
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

AUDIT_LOG_DIR = Path("logs/audit")
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "audit.log"

def read_audit_logs(limit: int = 10) -> List[Dict[str, Any]]:
    """Read recent audit log entries."""
    entries = []
    
    if not AUDIT_LOG_FILE.exists():
        return entries
    
    try:
        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            for line in lines[-limit:]:  # Get last N entries
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading audit log: {e}")
    
    return entries

def check_required_fields(entry: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Check if entry has all required fields."""
    required_fields = {
        'timestamp': 'Timestamp',
        'event_type': 'Event type',
        'risk_score': 'Risk score (in data or top level)',
    }
    
    missing = []
    for field, description in required_fields.items():
        if field not in entry and field not in entry.get('data', {}):
            missing.append(f"{description} ({field})")
    
    # Check for request_payload (new field we added)
    has_request_payload = 'request_payload' in entry
    
    # Check for match summary (varies by event type)
    has_match_summary = False
    event_type = entry.get('event_type', '')
    if event_type == 'kyc_verification':
        has_match_summary = 'verification_result' in entry or 'document_verified' in entry
    elif event_type == 'aml_screening':
        has_match_summary = 'sanctions_match' in entry or 'match_count' in entry
    elif event_type == 'combined_risk_assessment':
        has_match_summary = 'combined_risk_score' in entry
    
    return len(missing) == 0 and has_match_summary, missing + ([] if has_match_summary else ['Match summary'])

def main():
    print("=" * 60)
    print("Audit Logging Verification")
    print("=" * 60)
    print()
    
    # Check if directory exists
    if not AUDIT_LOG_DIR.exists():
        print(f"❌ Audit log directory does not exist: {AUDIT_LOG_DIR}")
        print("   The directory should be created when the API starts.")
        return 1
    
    print(f"✅ Audit log directory exists: {AUDIT_LOG_DIR}")
    
    # Check if file exists
    if not AUDIT_LOG_FILE.exists():
        print(f"⚠️  Audit log file does not exist yet: {AUDIT_LOG_FILE}")
        print("   This is normal if no API requests have been made yet.")
        print("   The file will be created when the first audit event is logged.")
        return 0
    
    print(f"✅ Audit log file exists: {AUDIT_LOG_FILE}")
    
    # Read recent entries
    entries = read_audit_logs(limit=10)
    
    if not entries:
        print("⚠️  No audit log entries found.")
        print("   Make some API requests to generate audit logs.")
        return 0
    
    print(f"✅ Found {len(entries)} recent audit log entries")
    print()
    
    # Analyze entries
    print("Analyzing recent entries...")
    print("-" * 60)
    
    entries_with_payload = 0
    entries_without_payload = 0
    
    for i, entry in enumerate(entries, 1):
        event_type = entry.get('event_type', 'unknown')
        timestamp = entry.get('timestamp', 'unknown')
        has_payload = 'request_payload' in entry
        has_all_fields, missing = check_required_fields(entry)
        
        if has_payload:
            entries_with_payload += 1
        else:
            entries_without_payload += 1
        
        status = "✅" if has_all_fields and has_payload else "⚠️ "
        print(f"{status} Entry {i}: {event_type} at {timestamp}")
        if not has_payload:
            print(f"   ⚠️  Missing request_payload field (may be from before code update)")
        if missing:
            print(f"   ⚠️  Missing fields: {', '.join(missing)}")
    
    print()
    print("-" * 60)
    print(f"Summary:")
    print(f"  Total entries: {len(entries)}")
    print(f"  With request_payload: {entries_with_payload}")
    print(f"  Without request_payload: {entries_without_payload}")
    print()
    
    if entries_without_payload > 0:
        print("⚠️  Some entries are missing request_payload.")
        print("   This is normal if:")
        print("   1. The API server hasn't been restarted since the code update")
        print("   2. The entries were created before the update")
        print()
        print("   To fix: Restart the API server and make new requests.")
        print("   New requests will include the request_payload field.")
    else:
        print("✅ All entries have request_payload field!")
    
    # Show sample entry
    if entries:
        print()
        print("Sample entry (most recent):")
        print("-" * 60)
        sample = entries[-1]
        # Pretty print with indentation
        print(json.dumps(sample, indent=2, default=str))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

