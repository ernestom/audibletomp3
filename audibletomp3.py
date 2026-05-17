#!/usr/bin/env python3
"""
Audible to MP3 Converter - Unified CLI for Audible to MP3 conversion
"""
import subprocess
import sys
import os
import json
import tempfile
import glob
import shutil
from pathlib import Path
from datetime import datetime

# Configuration
DESKTOP_DIR = Path.home() / "Desktop"
CACHE_DIR = Path(tempfile.gettempdir()) / "audible_mp3_cache"

def error(msg):
    print(f"\033[0;31mERROR: {msg}\033[0m", file=sys.stderr)

def success(msg):
    print(f"\033[0;32m{msg}\033[0m")

def info(msg):
    print(f"\033[1;33m{msg}\033[0m")

def check_dependencies():
    """Check if required tools are installed"""
    tools = ["ffmpeg", "ffprobe", "audible"]
    missing = []
    for tool in tools:
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            missing.append(tool)
    
    if missing:
        error(f"Missing required tools: {', '.join(missing)}")
        if "audible" in missing:
            info("Install audible-cli with: pip install audible-cli")
        if "ffmpeg" in missing or "ffprobe" in missing:
            info("Install ffmpeg with: brew install ffmpeg")
        sys.exit(1)
    
    # Create cache dir if it doesn't exist
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def run_command(cmd, timeout=None, stream=False):
    """Run a shell command and return output or stream it"""
    try:
        if stream:
            return subprocess.run(cmd, timeout=timeout)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors='replace',
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        error(f"Command timed out: {' '.join(cmd)}")
        return None
    except Exception as e:
        error(f"Command failed: {e}")
        return None

def update_library():
    """Update the audible library cache"""
    info("Updating Audible library cache...")
    with tempfile.NamedTemporaryFile(suffix='.json') as tmp:
        run_command(["audible", "library", "export", "-f", "json", "-o", tmp.name], timeout=60)
    success("Library updated.")

def get_library():
    """Get the library ordered by purchase date (newest first)"""
    info("Fetching library list...")
    with tempfile.NamedTemporaryFile(suffix='.json') as tmp:
        result = run_command(["audible", "library", "export", "-f", "json", "-o", tmp.name], timeout=60)
        if result and result.returncode == 0:
            with open(tmp.name, 'r') as f:
                library = json.load(f)
            
            def get_sort_key(item):
                date_str = item.get('purchase_date') or item.get('date_added') or "1970-01-01"
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    return datetime.min
            
            library.sort(key=get_sort_key, reverse=True)
            return library
    return []

def format_duration(minutes):
    """Convert minutes to H:MM format"""
    try:
        m = int(minutes)
        hours = m // 60
        mins = m % 60
        return f"{hours}h {mins}m"
    except:
        return "Unknown"

def display_table(library, title_msg="Your Library"):
    """Show the interactive table of books"""
    if not library:
        info(f"\nNo results found for {title_msg}.")
        return

    print(f"\n{title_msg}")
    print("="*140)
    header = f"{'#':<4} | {'Title':<40} | {'Author':<20} | {'Narrator':<15} | {'Dur.':<8} | {'Purchased':<12} | {'Released':<12} | {'Genre'}"
    print(header)
    print("-" * 140)
    
    for i, item in enumerate(library):
        num = i + 1
        title = item.get('title', 'Unknown')[:37] + ('...' if len(item.get('title', '')) > 37 else '')
        author = item.get('authors', 'Unknown')[:17] + ('...' if len(item.get('authors', '')) > 17 else '')
        narrator = item.get('narrators', 'Unknown')[:12] + ('...' if len(item.get('narrators', '')) > 12 else '')
        duration = format_duration(item.get('runtime_length_min', 0))
        purchased = (item.get('purchase_date') or item.get('date_added') or "N/A")[:10]
        released = (item.get('release_date') or "N/A")[:10]
        genre = item.get('genres', 'N/A').split(',')[0]
        
        row = f"{num:<4} | {title:<40} | {author:<20} | {narrator:<15} | {duration:<8} | {purchased:<12} | {released:<12} | {genre}"
        print(row)
    
    print("="*140 + "\n")

def find_cached_files(asin):
    """Check if we already have the AAX/AAXC and voucher in our cache"""
    book_cache = CACHE_DIR / asin
    if not book_cache.exists():
        return None, None
        
    aax_files = list(book_cache.glob("*.aax*")) + list(book_cache.glob("*.AAX*"))
    voucher_files = list(book_cache.glob("*.voucher"))
    
    if aax_files:
        return aax_files[0], (voucher_files[0] if voucher_files else None)
    return None, None

def download_audiobook(asin, format_type="aaxc"):
    """Download the audiobook and voucher to the cache directory"""
    book_cache = CACHE_DIR / asin
    book_cache.mkdir(parents=True, exist_ok=True)
    
    info(f"Downloading audiobook (ASIN: {asin}) to cache...")
    info("This may take a few minutes depending on your internet speed.")
    
    cmd = [
        "audible", "download",
        "--asin", asin,
        "--output-dir", str(book_cache),
        f"--{format_type}",
        "--overwrite",
        "-y"
    ]
    
    result = run_command(cmd, stream=True)
    
    if result.returncode != 0:
        if format_type == "aaxc":
            info("AAXC download failed, trying AAX format...")
            return download_audiobook(asin, "aax")
        return None, None

    return find_cached_files(asin)

def get_keys_from_voucher(voucher_path):
    """Extract keys from a voucher file"""
    try:
        with open(voucher_path, 'r') as f:
            data = json.load(f)
            lic = data.get('content_license', {})
            resp = lic.get('license_response', {})
            key = resp.get('key') or data.get('audible_key') or data.get('aaxc_key')
            iv = resp.get('iv') or data.get('audible_iv') or data.get('aaxc_iv')
            if key and iv:
                return {"type": "aaxc", "key": key, "iv": iv}
    except:
        pass
    return None

def get_activation_bytes():
    """Try to get activation bytes for AAX"""
    result = run_command(["audible", "activation-bytes"])
    if result and result.returncode == 0:
        for line in result.stdout.split('\n'):
            line = line.strip()
            if len(line) == 8 and all(c in '0123456789abcdefABCDEF' for c in line):
                return line
    return None

def convert(input_file, decrypt_info, speed, output_file):
    """Perform the conversion with speed adjustment"""
    cmd = ["ffmpeg", "-y"]
    if decrypt_info['type'] == "aaxc":
        cmd.extend(["-audible_key", decrypt_info['key'], "-audible_iv", decrypt_info['iv']])
    else:
        cmd.extend(["-activation_bytes", decrypt_info['activation_bytes']])
    
    cmd.extend(["-i", str(input_file)])
    
    if speed != 1.0:
        cmd.extend(["-filter:a", f"atempo={speed}"])
        
    cmd.extend([
        "-map_metadata", "0",
        "-id3v2_version", "3",
        "-codec:a", "libmp3lame",
        "-ab", "128k",
        "-map_chapters", "0",
        "-vn",
        str(output_file)
    ])
    
    info(f"Converting at {speed}x speed to: {output_file.name}")
    result = run_command(cmd, stream=True)
    
    if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
        success(f"\nSuccess! MP3 created on Desktop: {output_file.name}")
        return True
    else:
        error("Conversion failed.")
        return False

def main():
    check_dependencies()
    update_library()
    
    all_books = get_library()
    if not all_books:
        error("No books found in your library.")
        sys.exit(1)

    # Filtering/Searching logic
    keywords = sys.argv[1:]
    if keywords:
        search_str = " ".join(keywords).lower()
        library = []
        for book in all_books:
            searchable_fields = [
                book.get('title', ''),
                book.get('authors', ''),
                book.get('narrators', ''),
                book.get('genres', '')
            ]
            if any(search_str in field.lower() for field in searchable_fields):
                library.append(book)
        display_table(library, title_msg=f"Search matches for: '{search_str}'")
    else:
        # Default: Latest 20
        library = all_books[:20]
        display_table(library, title_msg="Latest 20 Audiobooks")

    if not library:
        sys.exit(0)
    
    # Book selection
    while True:
        try:
            choice = input(f"Select book number (1-{len(library)}) or 'q' to quit: ")
            if choice.lower() == 'q': sys.exit(0)
            idx = int(choice) - 1
            if 0 <= idx < len(library):
                selected_book = library[idx]
                break
            else:
                print("Invalid number.")
        except ValueError:
            print("Please enter a number.")
            
    # Speed selection
    speeds = [1.0, 1.2, 1.5, 1.8, 2.0]
    print("\nSelect playback speed:")
    for i, s in enumerate(speeds):
        print(f"{i+1}) {s}x")
    
    while True:
        try:
            s_choice = input(f"Choice (1-{len(speeds)}): ")
            s_idx = int(s_choice) - 1
            if 0 <= s_idx < len(speeds):
                selected_speed = speeds[s_idx]
                break
            else:
                print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")

    asin = selected_book['asin']
    title = selected_book['title']
    
    # Prepare output path
    clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
    output_file = DESKTOP_DIR / f"{clean_title}_{selected_speed}x.mp3"
    
    # Check if MP3 already exists
    if output_file.exists():
        info(f"Output file already exists: {output_file.name}")
        overwrite = input("Overwrite existing MP3? (y/N): ").lower()
        if overwrite != 'y':
            info("Skipping conversion.")
            sys.exit(0)

    # Check for existing download
    aax_file, voucher_file = find_cached_files(asin)
    if aax_file:
        info(f"Found existing download for: {title}")
        redownload = input("Redownload source file? (y/N): ").lower()
        if redownload == 'y':
            aax_file, voucher_file = download_audiobook(asin)
    else:
        aax_file, voucher_file = download_audiobook(asin)
        
    if not aax_file:
        error("Failed to obtain the audiobook file.")
        sys.exit(1)
            
    # Decryption logic
    decrypt_info = None
    if voucher_file:
        decrypt_info = get_keys_from_voucher(voucher_file)
            
    if not decrypt_info:
        info("Checking for activation bytes...")
        bytes = get_activation_bytes()
        if bytes:
            decrypt_info = {"type": "aax", "activation_bytes": bytes}
    
    if not decrypt_info:
        error("Could not find decryption keys or activation bytes for this book.")
        sys.exit(1)
            
    # Convert
    convert(aax_file, decrypt_info, selected_speed, output_file)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
