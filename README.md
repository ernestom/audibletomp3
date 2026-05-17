# Audible to MP3 Converter

A self-contained script to sync your Audible library, select a book, and convert it to MP3 at a custom playback speed.

## Prerequisites

1. **FFmpeg**: Required for audio conversion.
   ```bash
   brew install ffmpeg
   ```

2. **audible-cli**: Required to interface with Audible.
   ```bash
   pip install audible-cli
   ```

3. **Setup Audible CLI**: You must be logged in for the script to work.
   ```bash
   audible quickstart
   ```

## Usage

Run the script and follow the interactive prompts.

### Default View
Show only the **latest 20** audiobooks added to your library:
```bash
./audibletomp3.py
```

### Search Mode
Search your **entire library** by title, author, narrator, or genre:
```bash
./audibletomp3.py <keyword>
# Example: ./audibletomp3.py history
```

## Features

- **Automatic Library Sync**: Fetches your latest purchases and metadata automatically.
- **Smart Views**:
    - **Default**: Shows newest 20 books for quick access.
    - **Search**: Grep your entire library using one or more keywords.
- **Interactive Selection**: Pick a book from the displayed table by its number.
- **Playback Speed Options**: Choose between `1.0x`, `1.2x`, `1.5x`, `1.8x`, or `2.0x` speeds.
- **Smart Caching**:
    - Downloaded source files (`.aax`/`.aaxc`) are saved in the system's temporary directory.
    - The script detects existing downloads and asks if you want to reuse them to save time and bandwidth.
- **Overwrite Protection**: Prompts before overwriting existing MP3 files on your Desktop.
- **Automatic Speed Tagging**: Resulting filenames include the chosen speed (e.g., `BookTitle_1.5x.mp3`).
- **Direct to Desktop**: All converted MP3s are saved directly to your Desktop.
- **Universal Decryption**: Automatically handles both standard AAX and modern AAXC encryption keys.
