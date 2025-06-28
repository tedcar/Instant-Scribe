#!/usr/bin/env python3
"""Log Viewer CLI - Task 54.2

A command-line tool for viewing and filtering JSON Lines log files from Instant Scribe.
Supports time-range filtering, level filtering, and pretty-printed output.

Usage:
    python scripts/log_viewer.py [options]
    
Examples:
    # View last 100 log entries
    python scripts/log_viewer.py --tail 100
    
    # View logs from the last hour
    python scripts/log_viewer.py --since "1 hour ago"
    
    # View only ERROR and WARNING logs
    python scripts/log_viewer.py --level ERROR --level WARNING
    
    # View logs between specific times
    python scripts/log_viewer.py --from "2025-06-26 10:00" --to "2025-06-26 12:00"
    
    # Search for specific text in messages
    python scripts/log_viewer.py --search "VRAM"
    
    # Output raw JSON (for further processing)
    python scripts/log_viewer.py --json --tail 50
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import re

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from InstanceScrubber.json_logging import get_json_log_files
except ImportError:
    # Fallback for when running outside the project
    def get_json_log_files(log_dir: str = "logs") -> List[Path]:
        log_path = Path(log_dir)
        if not log_path.exists():
            return []
        
        json_files = []
        current_log = log_path / "app.jsonl"
        if current_log.exists():
            json_files.append(current_log)
        
        for file_path in log_path.glob("app.jsonl.*"):
            if file_path.is_file():
                json_files.append(file_path)
        
        json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return json_files


class LogViewer:
    """JSON log file viewer with filtering capabilities."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_files = get_json_log_files(log_dir)
    
    def parse_time(self, time_str: str) -> datetime:
        """Parse various time formats into datetime objects."""
        time_str = time_str.strip().lower()
        
        # Handle relative times
        if "ago" in time_str:
            return self._parse_relative_time(time_str)
        
        # Handle absolute times
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%H:%M:%S",
            "%H:%M",
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(time_str, fmt)
                # If no date specified, assume today
                if fmt.startswith("%H"):
                    today = datetime.now().date()
                    parsed = datetime.combine(today, parsed.time())
                return parsed
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse time: {time_str}")
    
    def _parse_relative_time(self, time_str: str) -> datetime:
        """Parse relative time expressions like '1 hour ago', '30 minutes ago'."""
        now = datetime.now()
        
        # Extract number and unit
        match = re.match(r"(\d+)\s+(second|minute|hour|day|week)s?\s+ago", time_str)
        if not match:
            raise ValueError(f"Unable to parse relative time: {time_str}")
        
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit == "second":
            delta = timedelta(seconds=amount)
        elif unit == "minute":
            delta = timedelta(minutes=amount)
        elif unit == "hour":
            delta = timedelta(hours=amount)
        elif unit == "day":
            delta = timedelta(days=amount)
        elif unit == "week":
            delta = timedelta(weeks=amount)
        else:
            raise ValueError(f"Unknown time unit: {unit}")
        
        return now - delta
    
    def read_log_entries(self, max_entries: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read log entries from all log files."""
        entries = []
        
        for log_file in self.log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            entry = json.loads(line)
                            entries.append(entry)
                        except json.JSONDecodeError as e:
                            # Skip malformed JSON lines
                            print(f"Warning: Skipping malformed JSON in {log_file}: {e}", file=sys.stderr)
                            continue
                        
                        if max_entries and len(entries) >= max_entries:
                            break
                
                if max_entries and len(entries) >= max_entries:
                    break
                    
            except IOError as e:
                print(f"Warning: Could not read {log_file}: {e}", file=sys.stderr)
                continue
        
        # Sort by timestamp (newest first)
        entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        if max_entries:
            entries = entries[:max_entries]
        
        return entries
    
    def filter_entries(
        self,
        entries: List[Dict[str, Any]],
        levels: Optional[List[str]] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        search: Optional[str] = None,
        logger_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter log entries based on various criteria."""
        filtered = []
        
        for entry in entries:
            # Level filter
            if levels and entry.get('level') not in levels:
                continue
            
            # Time range filter
            if from_time or to_time:
                try:
                    entry_time = datetime.fromisoformat(entry.get('timestamp', ''))
                    if from_time and entry_time < from_time:
                        continue
                    if to_time and entry_time > to_time:
                        continue
                except ValueError:
                    # Skip entries with invalid timestamps
                    continue
            
            # Search filter
            if search:
                search_text = search.lower()
                message = entry.get('message', '').lower()
                logger_name = entry.get('logger', '').lower()
                
                if search_text not in message and search_text not in logger_name:
                    continue
            
            # Logger filter
            if logger_filter:
                logger_name = entry.get('logger', '')
                if logger_filter.lower() not in logger_name.lower():
                    continue
            
            filtered.append(entry)
        
        return filtered
    
    def format_entry(self, entry: Dict[str, Any], show_json: bool = False) -> str:
        """Format a log entry for display."""
        if show_json:
            return json.dumps(entry, indent=2, ensure_ascii=False)
        
        # Pretty format
        timestamp = entry.get('timestamp', 'N/A')
        level = entry.get('level', 'INFO')
        logger = entry.get('logger', 'unknown')
        message = entry.get('message', '')
        
        # Color coding for levels
        level_colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
        reset_color = '\033[0m'
        
        # Use color if outputting to terminal
        if sys.stdout.isatty():
            level_color = level_colors.get(level, '')
            formatted_level = f"{level_color}{level:8s}{reset_color}"
        else:
            formatted_level = f"{level:8s}"
        
        # Format timestamp (show only time if today)
        try:
            dt = datetime.fromisoformat(timestamp)
            if dt.date() == datetime.now().date():
                time_str = dt.strftime("%H:%M:%S")
            else:
                time_str = dt.strftime("%m-%d %H:%M:%S")
        except ValueError:
            time_str = timestamp[:19] if len(timestamp) >= 19 else timestamp
        
        # Basic format
        result = f"{time_str} | {formatted_level} | {logger:20s} | {message}"
        
        # Add exception info if present
        if 'exception' in entry:
            exc_info = entry['exception']
            if exc_info.get('type') and exc_info.get('message'):
                result += f"\n    Exception: {exc_info['type']}: {exc_info['message']}"
        
        # Add duration if present
        if 'duration' in entry:
            result += f" (took {entry['duration']:.2f}ms)"
        
        return result


def main():
    """Main entry point for the log viewer CLI."""
    parser = argparse.ArgumentParser(
        description="View and filter Instant Scribe JSON log files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Examples:')[1] if 'Examples:' in __doc__ else ""
    )
    
    parser.add_argument(
        "--log-dir", "-d",
        default="logs",
        help="Directory containing log files (default: logs)"
    )
    
    parser.add_argument(
        "--tail", "-n",
        type=int,
        help="Show last N log entries"
    )
    
    parser.add_argument(
        "--level", "-l",
        action="append",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Filter by log level (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--from", "-f",
        dest="from_time",
        help="Show logs from this time (e.g., '2025-06-26 10:00', '1 hour ago')"
    )
    
    parser.add_argument(
        "--to", "-t",
        dest="to_time",
        help="Show logs until this time"
    )
    
    parser.add_argument(
        "--since", "-s",
        help="Show logs since this time (same as --from)"
    )
    
    parser.add_argument(
        "--search",
        help="Search for text in log messages"
    )
    
    parser.add_argument(
        "--logger",
        help="Filter by logger name (partial match)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of pretty format"
    )
    
    args = parser.parse_args()
    
    # Create log viewer
    viewer = LogViewer(args.log_dir)
    
    if not viewer.log_files:
        print(f"No JSON log files found in {args.log_dir}", file=sys.stderr)
        return 1
    
    # Parse time arguments
    from_time = None
    to_time = None
    
    try:
        if args.from_time:
            from_time = viewer.parse_time(args.from_time)
        elif args.since:
            from_time = viewer.parse_time(args.since)
        
        if args.to_time:
            to_time = viewer.parse_time(args.to_time)
    except ValueError as e:
        print(f"Error parsing time: {e}", file=sys.stderr)
        return 1
    
    # Read and filter log entries
    try:
        entries = viewer.read_log_entries(max_entries=args.tail)
        
        filtered_entries = viewer.filter_entries(
            entries,
            levels=args.level,
            from_time=from_time,
            to_time=to_time,
            search=args.search,
            logger_filter=args.logger,
        )
        
        # Output results
        if not filtered_entries:
            print("No log entries match the specified criteria.", file=sys.stderr)
            return 0
        
        # Reverse order for display (oldest first)
        filtered_entries.reverse()
        
        for entry in filtered_entries:
            print(viewer.format_entry(entry, show_json=args.json))
        
        return 0
        
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
