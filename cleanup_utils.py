"""
Utility functions for cleaning up temporary files
"""
import os
import glob
from datetime import datetime, timedelta
from questrade_utils import log


def cleanup_temp_files(max_age_hours=24, dry_run=False):
    """
    Clean up temporary JSON files older than max_age_hours.

    Args:
        max_age_hours: Remove files older than this many hours (default: 24)
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Number of files deleted (or would be deleted if dry_run=True)
    """
    temp_patterns = [
        "temp-*.json",
        "temp-chain-*.json",
        "temp-quotes-*.json"
    ]

    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    deleted_count = 0
    total_size = 0

    for pattern in temp_patterns:
        for filepath in glob.glob(pattern):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))

                if file_mtime < cutoff_time:
                    file_size = os.path.getsize(filepath)
                    total_size += file_size

                    if dry_run:
                        log(f"Would delete: {filepath} ({file_size:,} bytes, age: {datetime.now() - file_mtime})")
                    else:
                        os.remove(filepath)
                        log(f"Deleted: {filepath} ({file_size:,} bytes)")

                    deleted_count += 1

            except Exception as e:
                log(f"[WARNING] Error processing {filepath}: {e}")

    if deleted_count > 0:
        action = "Would delete" if dry_run else "Deleted"
        log(f"[OK] {action} {deleted_count} temp file(s), freed {total_size:,} bytes")
    else:
        log(f"No temp files older than {max_age_hours} hours found")

    return deleted_count


def cleanup_all_temp_files(dry_run=False):
    """
    Clean up ALL temporary JSON files regardless of age.

    Args:
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Number of files deleted (or would be deleted if dry_run=True)
    """
    temp_patterns = [
        "temp-*.json",
        "temp-chain-*.json",
        "temp-quotes-*.json"
    ]

    deleted_count = 0
    total_size = 0

    for pattern in temp_patterns:
        for filepath in glob.glob(pattern):
            try:
                file_size = os.path.getsize(filepath)
                total_size += file_size

                if dry_run:
                    log(f"Would delete: {filepath} ({file_size:,} bytes)")
                else:
                    os.remove(filepath)
                    log(f"Deleted: {filepath} ({file_size:,} bytes)")

                deleted_count += 1

            except Exception as e:
                log(f"[WARNING] Error processing {filepath}: {e}")

    if deleted_count > 0:
        action = "Would delete" if dry_run else "Deleted"
        log(f"[OK] {action} {deleted_count} temp file(s), freed {total_size:,} bytes")
    else:
        log("No temp files found")

    return deleted_count


def list_temp_files():
    """
    List all temporary JSON files with their sizes and ages.

    Returns:
        List of tuples (filepath, size_bytes, age_hours)
    """
    temp_patterns = [
        "temp-*.json",
        "temp-chain-*.json",
        "temp-quotes-*.json"
    ]

    files_info = []

    for pattern in temp_patterns:
        for filepath in glob.glob(pattern):
            try:
                file_size = os.path.getsize(filepath)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                age_hours = (datetime.now() - file_mtime).total_seconds() / 3600

                files_info.append((filepath, file_size, age_hours))

            except Exception as e:
                log(f"[WARNING] Error reading {filepath}: {e}")

    # Sort by age (newest first)
    files_info.sort(key=lambda x: x[2])

    if files_info:
        log(f"Found {len(files_info)} temporary file(s):")
        total_size = 0
        for filepath, size, age in files_info:
            total_size += size
            log(f"  {filepath}: {size:,} bytes, {age:.1f} hours old")
        log(f"Total size: {total_size:,} bytes")
    else:
        log("No temporary files found")

    return files_info


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "list":
            list_temp_files()
        elif command == "clean":
            max_age = int(sys.argv[2]) if len(sys.argv) > 2 else 24
            cleanup_temp_files(max_age_hours=max_age)
        elif command == "clean-all":
            cleanup_all_temp_files()
        elif command == "dry-run":
            max_age = int(sys.argv[2]) if len(sys.argv) > 2 else 24
            cleanup_temp_files(max_age_hours=max_age, dry_run=True)
        else:
            print("Usage:")
            print("  python cleanup_utils.py list                  # List all temp files")
            print("  python cleanup_utils.py clean [hours]         # Clean files older than N hours (default: 24)")
            print("  python cleanup_utils.py clean-all             # Clean ALL temp files")
            print("  python cleanup_utils.py dry-run [hours]       # Show what would be deleted")
    else:
        list_temp_files()
