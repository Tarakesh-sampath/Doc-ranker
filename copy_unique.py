import os
import shutil
import hashlib
import argparse
import re
import json
from pathlib import Path
from pypdf import PdfReader

def clean_text(text):
    """Normalize text by removing extra whitespace and converting to lowercase."""
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()

def get_file_hash(file_path):
    """Calculate hash of a file. Uses text content for PDFs, binary for others."""
    file_path = Path(file_path)
    
    # Try text-based hashing for PDFs
    if file_path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(file_path, strict=False)
            text_content = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                except Exception:
                    pass
            
            combined_text = clean_text(" ".join(text_content))
            if combined_text:
                return hashlib.sha256(combined_text.encode("utf-8")).hexdigest()
        except Exception as e:
            print(f"Warning: Could not extract text from {file_path.name}: {e}")

    # Fallback to binary hash
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def copy_unique_files(source_dir, dest_dir, extensions=None):
    """Copy unique files from source to destination with content-based hashing and performance caching."""
    source_path = Path(source_dir).absolute()
    dest_path = Path(dest_dir).absolute()
    hash_cache_path = dest_path / ".hashes.json"

    if not source_path.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return

    # Create destination directory if it doesn't exist
    dest_path.mkdir(parents=True, exist_ok=True)

    # Load hash cache for the destination directory
    hash_cache = {}
    if hash_cache_path.exists():
        try:
            with open(hash_cache_path, "r") as f:
                hash_cache = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load hash cache: {e}")

    seen_hashes = set()
    new_hash_cache = {}
    copied_count = 0
    skipped_count = 0

    # First, index the destination directory to avoid duplicates
    print(f"Indexing existing files in '{dest_dir}'...")
    for root, _, files in os.walk(dest_path):
        for filename in files:
            if filename == ".hashes.json":
                continue
            file_path = Path(root) / filename
            rel_path = str(file_path.relative_to(dest_path))
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)

            # Check if we can use the cached hash
            if rel_path in hash_cache and hash_cache[rel_path]["mtime"] == mtime and hash_cache[rel_path]["size"] == size:
                file_hash = hash_cache[rel_path]["hash"]
            else:
                try:
                    file_hash = get_file_hash(file_path)
                except Exception as e:
                    print(f"Warning: Could not index existing file {file_path}: {e}")
                    continue
            
            if file_hash:
                seen_hashes.add(file_hash)
                new_hash_cache[rel_path] = {"mtime": mtime, "size": size, "hash": file_hash}

    print(f"Scanning '{source_dir}' for unique files...")
    if extensions:
        print(f"Filtering for extensions: {', '.join(extensions)}")

    for root, _, files in os.walk(source_path):
        for filename in files:
            file_path = Path(root) / filename
            
            # Extension filtering
            if extensions and file_path.suffix.lower() not in [ext.lower() if ext.startswith('.') else f".{ext.lower()}" for ext in extensions]:
                continue

            file_hash = get_file_hash(file_path)
            if not file_hash:
                continue

            # Case: Content is unique
            if file_hash not in seen_hashes:
                seen_hashes.add(file_hash)
                
                # Determine destination filename
                target_file = dest_path / filename
                
                # Case: Content is unique but filename already exists (different doc, same name)
                # Handle by suffixing: document.pdf -> document_1.pdf
                counter = 1
                base_name = target_file.stem
                extension = target_file.suffix
                while target_file.exists():
                    target_file = dest_path / f"{base_name}_{counter}{extension}"
                    counter += 1
                
                try:
                    shutil.copy2(file_path, target_file)
                    copied_count += 1
                    
                    # Add new file to metadata cache
                    mtime = os.path.getmtime(target_file)
                    size = os.path.getsize(target_file)
                    rel_target = str(target_file.relative_to(dest_path))
                    new_hash_cache[rel_target] = {"mtime": mtime, "size": size, "hash": file_hash}
                    
                    print(f"Copied: {file_path.name} -> {target_file.name}")
                except Exception as e:
                    print(f"Error copying {file_path}: {e}")
            else:
                skipped_count += 1
                # print(f"Skipped (duplicate content found in destination): {file_path.name}")

    # Save the updated hash cache
    try:
        with open(hash_cache_path, "w") as f:
            json.dump(new_hash_cache, f, indent=4)
    except Exception as e:
        print(f"Warning: Could not save hash cache: {e}")

    print("\nSummary:")
    print(f"Total unique files copied: {copied_count}")
    print(f"Total duplicate files skipped: {skipped_count}")
    print(f"Files saved in: {dest_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy unique files from source to destination based on content.")
    parser.add_argument("--source", help="Source directory to scan")
    parser.add_argument("--dest", default="library_pdfs", help="Destination directory to copy unique files to")
    parser.add_argument("--ext", nargs="+", help="Optional: filter by extensions (e.g., .pdf .txt)")
    
    args = parser.parse_args()
    
    copy_unique_files(args.source, args.dest, args.ext)
