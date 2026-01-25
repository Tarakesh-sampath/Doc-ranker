import os
import shutil
import hashlib
import argparse
from pathlib import Path

def get_file_hash(file_path):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def copy_unique_files(source_dir, dest_dir, extensions=None):
    """Copy unique files from source to destination."""
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)

    if not source_path.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return

    # Create destination directory if it doesn't exist
    dest_path.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    copied_count = 0
    skipped_count = 0

    # First, index the destination directory to avoid duplicates
    print(f"Indexing existing files in '{dest_dir}'...")
    for root, _, files in os.walk(dest_path):
        for filename in files:
            file_path = Path(root) / filename
            try:
                file_hash = get_file_hash(file_path)
                seen_hashes.add(file_hash)
            except Exception as e:
                print(f"Warning: Could not index existing file {file_path}: {e}")

    print(f"Scanning '{source_dir}' for unique files...")
    if extensions:
        print(f"Filtering for extensions: {', '.join(extensions)}")

    for root, _, files in os.walk(source_path):
        for filename in files:
            file_path = Path(root) / filename
            
            # Extension filtering
            if extensions and file_path.suffix.lower() not in [ext.lower() if ext.startswith('.') else f".{ext.lower()}" for ext in extensions]:
                continue

            try:
                file_hash = get_file_hash(file_path)
            except Exception as e:
                print(f"Could not read {file_path}: {e}")
                continue

            if file_hash not in seen_hashes:
                seen_hashes.add(file_hash)
                
                # Determine destination filename
                target_file = dest_path / filename
                
                # If a file with same name exists, append a suffix
                counter = 1
                base_name = target_file.stem
                extension = target_file.suffix
                while target_file.exists():
                    target_file = dest_path / f"{base_name}_{counter}{extension}"
                    counter += 1
                
                try:
                    shutil.copy2(file_path, target_file)
                    copied_count += 1
                    print(f"Copied: {file_path.name} -> {target_file.name}")
                except Exception as e:
                    print(f"Error copying {file_path}: {e}")
            else:
                skipped_count += 1
                print(f"Skipped (duplicate found in source or destination): {file_path.name}")

    print("\nSummary:")
    print(f"Total unique files copied: {copied_count}")
    print(f"Total duplicate files skipped: {skipped_count}")
    print(f"Files saved in: {dest_path.absolute()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy unique files from source to destination based on content.")
    parser.add_argument("--source", help="Source directory to scan")
    parser.add_argument("--dest", help="Destination directory to copy unique files to")
    parser.add_argument("--ext", nargs="+", help="Optional: filter by extensions (e.g., .pdf .txt)")
    
    args = parser.parse_args()
    
    copy_unique_files(args.source, args.dest, args.ext)
