#!/usr/bin/env python3
"""
Script to parse large JSON files using jq and extract build metrics to CSV.
"""

import subprocess
import json
import csv
import sys
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional


def run_jq_command(json_file_path: str, jq_filter: str, slurp: bool=False) -> str:
    """
    Run jq command with the given filter on the JSON file.
    Handles both regular JSON and JSON Lines format.
    
    Args:
        json_file_path (str): Path to the JSON file
        jq_filter (str): jq filter expression
        slurp (bool): Whether to use -s (slurp) flag for JSON Lines format
    
    Returns:
        str: Output from jq command
    """
    try:
        # Build command arguments
        cmd_args = ['jq']
        if slurp:
            cmd_args.append('-s')
        cmd_args.extend(['-r', jq_filter, json_file_path])
        
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running jq command: {e}")
        print(f"stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: jq command not found. Please install jq first.")
        return None

def parse_json_attributes(json_file_path: str) -> Dict[str, Any]:
    """
    Parse the JSON file and extract required attributes using jq.
    
    Args:
        json_file_path (str): Path to the JSON file
    
    Returns:
        dict: Dictionary containing parsed attributes
    """
    attributes = {}
    
    # jq filters to extract the required data with id constraints
    # These filters will find objects with specific id patterns and extract the data
    filters = {
        'startTime': 'select(.id.started != null) | .started.startTime // empty',
        'startTimeMillis': 'select(.id.started != null) | .started.startTimeMillis // empty',
        'finishTime': 'select(.id.buildFinished != null) | .finished.finishTime // empty', 
        'finishTimeMillis': 'select(.id.buildFinished != null) | .finished.finishTimeMillis // empty',
        'totalRunnerCount': 'select(.id.buildMetrics != null and .lastMessage == true) | (.buildMetrics.actionSummary.runnerCount[] | select(.name == "total") | .count)',
        'internalRunnerCount': 'select(.id.buildMetrics != null and .lastMessage == true) | (.buildMetrics.actionSummary.runnerCount[] | select(.name == "internal") | .count)',
        'remoteRunnerCount': 'select(.id.buildMetrics != null and .lastMessage == true) | (.buildMetrics.actionSummary.runnerCount[] | select(.name == "remote" and .execKind == "Remote") | .count)',
        'cacheHitCount': 'select(.id.buildMetrics != null and .lastMessage == true) | (.buildMetrics.actionSummary.runnerCount[] | select(.name == "remote cache hit" and .execKind == "Remote") | .count)',
        'bytesSent': 'select(.id.buildMetrics != null and .lastMessage == true) | .buildMetrics.networkMetrics.systemNetworkStats.bytesSent',
        'bytesRecv': 'select(.id.buildMetrics != null and .lastMessage == true) | .buildMetrics.networkMetrics.systemNetworkStats.bytesRecv',
        # 'elapsedInfo': 'last(.[] | select(.id.progress != null)) | .progress.stderr // empty'
    }
    

    print(f"Parsing JSON file: {json_file_path}")
    for attr_name, jq_filter in filters.items():
        print(f"Extracting {attr_name}...")
        attributes[attr_name] = run_jq_command(json_file_path, jq_filter)
        
    # Unlike the others, the `progress` element occurs multiple times in the BEP JSON hence the use of `jq --slurp` 
    # to give us a single array so we can reliably match the last array element containing the build summary info we need.
    progress_output = run_jq_command(json_file_path, 'last(.[] | select(.id.progress != null)) | .progress.stderr // empty', True)
    
    # Extract Elapsed time and Critical Path from stderr log
    elapsed_match = re.search(r'Elapsed time: (\d+\.\d+)s, Critical Path: (\d+\.\d+)s', progress_output)

    if elapsed_match:
        attributes['elapsedTimeSeconds'] = float(elapsed_match.group(1))
        attributes['criticalPathSeconds'] = float(elapsed_match.group(2))
        
    attributes['progressOutput'] = progress_output
    
    return attributes

def write_to_csv(attributes: Dict[str, Any], csv_file_path: str, commit_hash: str, commit_message: str) -> None:
    """
    Write the parsed attributes to a CSV file.
    Appends to existing file or creates new file with headers.
    
    Args:
        attributes (dict): Dictionary containing parsed attributes
        csv_file_path (str): Path to the output CSV file
    """
    
    # Map to CSV columns
    csv_data = {
        'startTime': attributes.get('startTime', ''),
        'startTimeMillis': attributes.get('startTimeMillis', ''),
        'commit': commit_hash,
        'commitMessage': commit_message,
        'buildTimeSeconds': attributes.get('elapsedTimeSeconds', ''),
        'criticalPathTimeSeconds': attributes.get('criticalPathSeconds', ''),
        'totalRunnerCount': attributes.get('totalRunnerCount', ''),
        'internalRunnerCount': attributes.get('internalRunnerCount', ''),
        'remoteRunnerCount': attributes.get('remoteRunnerCount', ''),
        'cacheHitCount': attributes.get('cacheHitCount', ''),
        'bytesSent': attributes.get('bytesSent', ''),
        'bytesRecv': attributes.get('bytesRecv', ''),
        'annotation': ''  # Not available in provided JSON structure; manually added
    }
    
    fieldnames = [
        'startTime', 'startTimeMillis', 'commit', 'commitMessage', 'buildTimeSeconds',
        'criticalPathTimeSeconds', 'totalRunnerCount', 'internalRunnerCount', 'remoteRunnerCount',
        'cacheHitCount', 'bytesSent', 'bytesRecv', 'annotation'
    ]
    
    # Check if file exists to determine if we need to write headers
    file_exists = os.path.exists(csv_file_path)
    write_headers = not file_exists
    
    # If file exists, check if it's empty (in case it was created but no data written)
    if file_exists:
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                # Check if file is empty or only contains whitespace
                content = csvfile.read().strip()
                if not content:
                    write_headers = True
        except Exception:
            # If we can't read the file, assume we need headers
            write_headers = True
    
    # Write to CSV in append mode
    action = "Appending to" if file_exists and not write_headers else "Creating"
    print(f"{action}: {csv_file_path}")
    
    with open(csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write headers only if file is new or empty
        if write_headers:
            writer.writeheader()
        
        writer.writerow(csv_data)
    
    status = "appended to" if file_exists and not write_headers else "created"
    print(f"CSV file {status} successfully: {csv_file_path}")
    
    # Print summary
    print("\n\nParsed attributes:")
    for key, value in attributes.items():
        if key in ("bytesSent", "bytesRecv"):
            print(f"  {key}: {format_bytes(int(value))}")
        else:
            print(f"  {key}: {value}")
        
 
def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable format.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string with appropriate unit
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} TB"       

def main():
    """Main function to run the script."""
    if len(sys.argv) != 5:
        print("Usage: python csv.writer.py <json-file-path> <csv-file-path> <commit-hash> <commit-message>")
        print("Example: python csv.writer.py /path/to/file.json /path/to/file.csv <commit-hash> <commit-message>")
        sys.exit(1)
    
    json_file_path = sys.argv[1]
    csv_file_path = sys.argv[2]
    commit_hash = sys.argv[3]
    commit_message = sys.argv[4]
    
    # Check if input file exists
    if not os.path.exists(json_file_path):
        print(f"Error: Input file '{json_file_path}' does not exist.")
        sys.exit(1)
            
    # Parent doesn't exist → error and exit
    # Output file exists → continue execution
    if not os.path.exists(csv_file_path):
        parent_dir = Path(csv_file_path).parent
        if not parent_dir.exists():
            print(f"Error: Parent directory '{parent_dir}' for the output file {csv_file_path} does not exist.")
            sys.exit(1)
  
    # Check if jq is available
    try:
        subprocess.run(['jq', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: jq is not installed or not in PATH.")
        print("Please install jq first: https://jqlang.github.io/jq/download/")
        sys.exit(1)
    
    
    # Parse JSON and extract attributes
    attributes = parse_json_attributes(json_file_path)
    
    # Write to CSV
    write_to_csv(attributes, csv_file_path, commit_hash, commit_message)
     

if __name__ == "__main__":
    main()
