

# Film File Organizer

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

> Effortlessly organize and clean your film collection by director, year, and title using IMDb data. Includes tools for merging, quality checking, and more.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Automatic Mode](#automatic-mode)
  - [Interactive Mode](#interactive-mode)
  - [Merge and Cleanup](#merge-and-cleanup)
  - [Move and Quality Check](#move-and-quality-check)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---


## Features

- **Automatic File Sorting**: Organizes films into `/Director/ReleaseYear - Title/Film File` using IMDb data.
- **Multi-Format Support**: Handles `.mp4`, `.mkv`, `.avi`, `.mov`, and more.
- **Subtitle Handling**: Moves and renames `.srt` files alongside videos.
- **IMDb Integration**: Fetches director, title, and year for accurate sorting.
- **File Renaming**: Renames files to their official IMDb title.
- **Interactive & Automatic Modes**: Choose between full automation or manual confirmation.
- **Merge & Quality Tools**: Merge folders and compare video quality to keep the best version.


## Project Structure

- `automatic_movie_sorter.py` — Fully automatic film organizer (IMDb-based)
- `interactive_movie_sorter.py` — Interactive organizer with manual confirmation
- `merge_and_cleanup.py` — Merge folders and clean up source after transfer
- `move_qualitycheck.py` — Compare and move higher-quality video files
## Prerequisites

- Python 3.7 or higher
- [IMDbPY](https://imdbpy.github.io/)

## Installation

Install dependencies with pip:

```bash
pip install IMDbPY
```


## Usage

### Automatic Mode

Use the automatic organizer for hands-off sorting:

```bash
python automatic_movie_sorter.py
```
You will be prompted for the folder path. The script will:
- Search IMDb for each video file
- Create `/Director/Year - Title/` folders
- Move and rename both video and matching `.srt` subtitle files

### Interactive Mode

Use the interactive organizer for manual confirmation:

```bash
python interactive_movie_sorter.py
```
You can confirm or override IMDb results for each film.

### Merge and Cleanup

Merge one folder into another and optionally delete the source:

```bash
python merge_and_cleanup.py
```
Edit the script to set your source/destination paths as needed.

### Move and Quality Check

Compare video files in two locations and keep the highest quality:

```bash
python move_qualitycheck.py
```
Requires [mediainfo](https://mediaarea.net/en/MediaInfo) to be installed.


## Examples

**Before:**
```
Unsorted/
  random_website_1993_sch_list.mkv
  another_telegram_channel_munich2005.mp4
  2017_Dunkirk.avi
```

**After:**
```
Sorted/
  Steven Spielberg/
    1993 - Schindler's List/Schindler's List.mkv
    2005 - Munich/Munich.mp4
  Christopher Nolan/
    2017 - Dunkirk/Dunkirk.avi
```

**Interactive Prompt Example:**
```
Title: Schindler's List
Director: Steven Spielberg
Release Year: 1993
Is this correct? [Y/n]:
```


## Troubleshooting

- Ensure you have a stable internet connection for IMDb lookups.
- If you get errors about missing modules, re-run `pip install IMDbPY`.
- For video quality checking, install `mediainfo` (e.g., `brew install mediainfo` on macOS).
- If you encounter permission errors, run the script with appropriate access or move files to a user-writable directory.

## Contributing

Contributions, bug reports, and feature requests are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. If the LICENSE file is missing, please contact the maintainer.

## Support

For help, open an issue on GitHub or contact the repository maintainer.
