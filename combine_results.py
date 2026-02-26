import os
import shutil
import hashlib
import argparse
import re
from pathlib import Path
from pypdf import PdfReader

# ----------------- Utilities -----------------
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

def strip_numbering(filename):
    """Remove leading XX_ from filename."""
    return re.sub(r"^\d+_", "", filename)

def combine_folders(source_folders, dest_dir):
    """Combine unique files from multiple folders after stripping numbering."""
    dest_path = Path(dest_dir).absolute()
    dest_path.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    copied_count = 0
    skipped_count = 0

    print(f"Combining folders into '{dest_dir}'...")

    for folder in source_folders:
        folder_path = Path(folder).absolute()
        if not folder_path.exists():
            print(f"Warning: Folder '{folder}' does not exist. Skipping.")
            continue

        print(f"  Processing '{folder}'...")
        for filename in os.listdir(folder_path):
            file_path = folder_path / filename
            if not file_path.is_file() or filename.startswith("."):
                continue

            # Calculate hash for uniqueness
            file_hash = get_file_hash(file_path)
            if not file_hash:
                continue

            if file_hash in seen_hashes:
                skipped_count += 1
                continue

            seen_hashes.add(file_hash)

            # Strip numbering for the target filename
            clean_name = strip_numbering(filename)
            target_file = dest_path / clean_name

            # Absolute safety: handle name collisions even with unique content
            if target_file.exists():
                stem = target_file.stem
                suffix = target_file.suffix
                counter = 1
                while target_file.exists():
                    target_file = dest_path / f"{stem}_{counter}{suffix}"
                    counter += 1

            try:
                shutil.copy2(file_path, target_file)
                copied_count += 1
                print(f"    Copied: {filename} → {target_file.name}")
            except Exception as e:
                print(f"    Error copying {filename}: {e}")

    print("\nSummary:")
    print(f"Total unique files combined: {copied_count}")
    print(f"Total duplicate files skipped: {skipped_count}")
    print(f"Results saved in: {dest_path}")

# ----------------- CLI -----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine multiple ranked output folders into a single unique set."
    )
    parser.add_argument(
        "--folders",
        nargs="+",
        required=True,
        help="List of folders to combine",
    )
    parser.add_argument(
        "--dest",
        default="combined_ranked_output",
        help="Destination directory (default: combined_ranked_output)",
    )

    args = parser.parse_args()

    combine_folders(args.folders, args.dest)
