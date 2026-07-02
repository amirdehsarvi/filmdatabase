#!/usr/bin/env python3
"""
Interactive Movie Sorter — NAS Edition
---------------------------------------
Organises film files into:
  aj  → /volume1/Films/AJ/Director/Year - Title/   (watched together)
  am  → /volume1/Films/AmirWatched/Director/Year - Title/  (Amir only)
  w   → /volume1/Films/Not Watched Yet/Director/Year - Title/

Usage:
    python3 interactive_movie_sorter.py
    Enter folder path when prompted (e.g. /volume1/Films/ToOrganise)

Dependencies:
    pip install requests beautifulsoup4
"""

import os
import re
import sys
import json
import shutil
import unicodedata
import urllib.parse

import requests
from bs4 import BeautifulSoup

# ── Destination folders ───────────────────────────────────────────────────────
# Auto-detect: use /Volumes/Films on Mac, /volume1/Films on NAS
if os.path.exists("/Volumes/Films"):
    FILMS_ROOT = "/Volumes/Films"
elif os.path.exists("/volume1/Films"):
    FILMS_ROOT = "/volume1/Films"
else:
    FILMS_ROOT = input("Films root path not found. Enter it manually: ").strip()

AJ_PATH      = os.path.join(FILMS_ROOT, "AJ")
AMIR_PATH    = os.path.join(FILMS_ROOT, "AmirWatched")
WATCH_PATH   = os.path.join(FILMS_ROOT, "Not Watched Yet")
KIDS_PATH    = os.path.join(FILMS_ROOT, "Kids & Family")
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_EXTENSIONS     = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
                        '.m4v', '.mpg', '.mpeg', '.m2ts', '.ts', '.vob', '.ogv', '.3gp'}
SUBTITLE_EXTENSIONS  = {'.srt', '.sub', '.ass', '.ssa', '.vtt', '.idx'}
DVD_EXTENSIONS       = {'.ifo', '.bup', '.vob'}
AUTO_DELETE_EXTENSIONS = {'.nfo', '.jpg', '.jpeg', '.png', '.gif', '.bmp',
                           '.txt', '.xml', '.db', '.url'}
RELEASE_GROUP_PATTERNS = [
    r'-RARBG$', r'-YTS$', r'-ETRG$', r'-EVO$', r'-FGT$', r'-SPARKS$',
    r'-GECKOS$', r'-Ganool$', r'-AlphaDL$', r'-PSA$', r'-Pahe$',
    r'-MkvCage$', r'-ShAaNiG$'
]
KIDS_GENRES = {"animation", "family", "children"}


# ── Data classes ──────────────────────────────────────────────────────────────

class SimpleMovieData(dict):
    def __init__(self, imdb_id=None, title=None, year=None, directors=None, genres=None):
        super().__init__()
        self.movieID = imdb_id.replace('tt', '') if imdb_id else None
        if title:
            self['title'] = title
        if year:
            self['year'] = year
        if directors:
            self['director'] = [{'name': name} for name in directors]
        if genres:
            self['genres'] = genres


def build_movie_data(imdb_id=None, title=None, year=None, directors=None, genres=None):
    return SimpleMovieData(imdb_id=imdb_id, title=title, year=year,
                           directors=directors or ['Unknown'], genres=genres)


def has_usable_movie_metadata(movie_data):
    return bool(movie_data and movie_data.get('title') and movie_data.get('year'))


def is_kids_film(movie_data):
    genres = {g.lower() for g in (movie_data.get('genres') or [])}
    return bool(genres & KIDS_GENRES)


# ── Filename helpers ──────────────────────────────────────────────────────────

def sanitize_filename(name):
    """NFC-normalise and remove filesystem-unsafe characters."""
    name = unicodedata.normalize('NFC', name)
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.strip().strip('.')
    name = re.sub(r'\s+', ' ', name)
    return name[:120]


def clean_movie_name(file_name):
    """Extract a clean title and year from a messy torrent filename."""
    movie_name = os.path.splitext(file_name)[0]

    year_match = re.match(r'^\s*(19\d{2}|20\d{2})\s+(.+)$', movie_name)
    if year_match:
        year = year_match.group(1)
        movie_name = year_match.group(2)
    else:
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', movie_name)
        year = year_match.group(1) if year_match else None
        movie_name = re.sub(r'\s*\b(19\d{2}|20\d{2})\b\s*.*$', '', movie_name)

    patterns_to_remove = [
        r'\b\d{3,4}p\b', r'\bBluRay\b', r'\bWEB-DL\b', r'\bWEBRip\b',
        r'\bWEB\b', r'\bHD\b', r'\bSD\b', r'\bAAC[\d.]*\b', r'\bDDP[\d.]*\b',
        r'\bx264\b', r'\bx265\b', r'\bXviD\b', r'\bHDRip\b', r'\bDVDRip\b',
        r'\bBRRip\b', r'\bH\.?264\b', r'\bH\.?265\b', r'\bHEVC\b',
        r'\b10bit\b', r'\b8bit\b', r'\b@\w+\b', r'\bSoftSub\b', r'\bDream\b',
        r'\bWATCHABLE\b', r'\bMVPLUS\b', r'\bMASTER\b', r'\bREMUX\b',
        r'\bVeDeTT\b', r'\bAvaMovie\b', r'\bMalayDub\b',
    ]
    for pattern in patterns_to_remove:
        movie_name = re.sub(pattern, '', movie_name, flags=re.IGNORECASE)
    for pattern in RELEASE_GROUP_PATTERNS:
        movie_name = re.sub(pattern, '', movie_name, flags=re.IGNORECASE)

    movie_name = re.sub(r'\[[^\]]*\]', ' ', movie_name)
    movie_name = re.sub(
        r'\([^\)]*(?:rarbg|yts|x264|x265|bluray|webrip|web-dl)[^\)]*\)',
        ' ', movie_name, flags=re.IGNORECASE)
    movie_name = re.sub(r'[_\.]', ' ', movie_name)
    movie_name = re.sub(r'\s+', ' ', movie_name).strip()
    return movie_name, year


# ── IMDb / Wikidata lookups ───────────────────────────────────────────────────

def search_imdb_suggestions(movie_name, year=None):
    try:
        query = movie_name.strip().lower()
        if not query:
            return []
        first_char = next((c for c in query if c.isalnum()), 'x')
        url = f"https://v2.sg.media-imdb.com/suggestion/{first_char}/{urllib.parse.quote(query)}.json"
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        candidates = []
        for item in resp.json().get('d', []):
            if item.get('qid') != 'movie' and item.get('q') != 'feature':
                continue
            if year and item.get('y') and str(item.get('y')) != str(year):
                continue
            candidates.append(item)
        if not candidates and year:
            for item in resp.json().get('d', []):
                if item.get('qid') == 'movie' or item.get('q') == 'feature':
                    candidates.append(item)
        return candidates
    except Exception as e:
        print(f"  Search error: {e}")
        return []


def get_movie_data_from_wikidata(imdb_id, fallback_title=None, fallback_year=None):
    try:
        imdb_id = imdb_id.replace('tt', '').strip()
        query = '''
SELECT ?filmLabel ?directorLabel ?publicationDate ?genreLabel WHERE {
  ?film wdt:P345 "tt%s".
  OPTIONAL { ?film wdt:P57 ?director. }
  OPTIONAL { ?film wdt:P577 ?publicationDate. }
  OPTIONAL { ?film wdt:P136 ?genre. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}''' % imdb_id
        resp = requests.get(
            'https://query.wikidata.org/sparql',
            params={'format': 'json', 'query': query},
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'},
            timeout=8
        )
        resp.raise_for_status()
        bindings = resp.json().get('results', {}).get('bindings', [])
        if not bindings:
            return None

        title = fallback_title
        year = int(fallback_year) if fallback_year else None
        directors, genres = [], []

        for row in bindings:
            if not title and 'filmLabel' in row:
                title = row['filmLabel']['value']
            if not year and 'publicationDate' in row:
                year = int(row['publicationDate']['value'][:4])
            if 'directorLabel' in row:
                d = row['directorLabel']['value']
                if d not in directors:
                    directors.append(d)
            if 'genreLabel' in row:
                g = row['genreLabel']['value']
                if g not in genres:
                    genres.append(g)

        return build_movie_data(imdb_id=imdb_id, title=title, year=year,
                                directors=directors or ['Unknown'], genres=genres)
    except Exception as e:
        print(f"  Wikidata error: {e}")
        return None


def get_movie_data(movie_name, year=None):
    """Search IMDb suggestions, then enrich with Wikidata or IMDb scrape."""
    try:
        print(f"  → Searching IMDb...")
        suggestions = search_imdb_suggestions(movie_name, year)
        if suggestions:
            best = suggestions[0]
            imdb_id = best.get('id', '').replace('tt', '')
            suggestion_title = best.get('l')
            suggestion_year = best.get('y') or year

            movie_data = get_movie_data_from_wikidata(
                imdb_id, fallback_title=suggestion_title, fallback_year=suggestion_year)

            if has_usable_movie_metadata(movie_data):
                # Prefer IMDb suggestion title if Wikidata returned something shorter
                if suggestion_title and len(suggestion_title) > len(movie_data.get('title', '')):
                    movie_data['title'] = suggestion_title
                # Fix Unknown director via IMDb scrape
                dirs = movie_data.get('director', [])
                if not dirs or dirs[0].get('name') == 'Unknown':
                    _, _, scraped_dirs = scrape_imdb_page(imdb_id)
                    if scraped_dirs and scraped_dirs != ['Unknown']:
                        movie_data['director'] = [{'name': d} for d in scraped_dirs]
                return movie_data

            # Wikidata failed — try IMDb scrape for this ID
            title, yr, directors = scrape_imdb_page(imdb_id)
            if title:
                return build_movie_data(imdb_id=imdb_id, title=title,
                                        year=yr or (int(suggestion_year) if suggestion_year else None),
                                        directors=directors)

            if suggestion_title and suggestion_year:
                return build_movie_data(imdb_id=imdb_id, title=suggestion_title,
                                        year=int(suggestion_year))
        return None
    except Exception as e:
        print(f"  IMDb error: {e}")
        return None


def scrape_imdb_page(imdb_id):
    """Scrape title, year, directors from IMDb page JSON-LD."""
    try:
        url = f"https://www.imdb.com/title/tt{imdb_id}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        # Force UTF-8 decoding
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                raw = script.string or script.get_text()
                if not raw:
                    continue
                data = json.loads(raw)
                title = data.get('name')
                year_str = (data.get('datePublished') or '')[:4]
                year = int(year_str) if year_str.isdigit() else None
                directors = []
                for d in (data.get('director') or []):
                    if isinstance(d, dict) and d.get('name'):
                        directors.append(d['name'])
                if title:
                    return title, year, directors or ['Unknown']
            except Exception:
                continue
    except Exception as e:
        print(f"  IMDb scrape error: {e}")
    return None, None, None


def fetch_movie_by_imdb_id(imdb_id, default_title="", default_year=None):
    normalized = imdb_id.replace('tt', '').strip()

    # Try Wikidata first (don't pass noisy filename as fallback)
    movie_data = get_movie_data_from_wikidata(normalized, fallback_title=None, fallback_year=default_year)
    if has_usable_movie_metadata(movie_data):
        # Fix Unknown director via IMDb scrape
        directors = movie_data.get('director', [])
        if not directors or directors[0].get('name') == 'Unknown':
            title, year, scraped_dirs = scrape_imdb_page(normalized)
            if scraped_dirs and scraped_dirs != ['Unknown']:
                movie_data['director'] = [{'name': d} for d in scraped_dirs]
            if title and not movie_data.get('title'):
                movie_data['title'] = title
        return movie_data

    # Wikidata failed — scrape IMDb page directly for clean title + director
    title, year, directors = scrape_imdb_page(normalized)
    if title:
        return build_movie_data(imdb_id=normalized, title=title,
                                year=year or (int(default_year) if default_year else None),
                                directors=directors)

    print("  Could not fetch metadata for that ID.")
    return None


# ── File operations ───────────────────────────────────────────────────────────

def cleanup_directory(directory_path, auto_delete=True):
    """Remove junk files; skip Synology system files."""
    for root, dirs, files in os.walk(directory_path):
        # Skip Synology internal dirs
        dirs[:] = [d for d in dirs if not d.startswith('@')]
        for filename in files:
            if filename.startswith('.') or filename.startswith('@'):
                continue
            file_path = os.path.join(root, filename)
            _, ext = os.path.splitext(filename.lower())
            # Skip Synology resource fork extensions
            if '@syno' in filename.lower():
                continue
            if ext in VIDEO_EXTENSIONS or ext in SUBTITLE_EXTENSIONS or ext in DVD_EXTENSIONS:
                continue
            if auto_delete and ext in AUTO_DELETE_EXTENSIONS:
                try:
                    os.remove(file_path)
                    print(f"  → Deleted: {filename}")
                except Exception as e:
                    print(f"  → Could not delete {filename}: {e}")
    # Remove empty subdirs
    for root, dirs, files in os.walk(directory_path, topdown=False):
        dirs[:] = [d for d in dirs if not d.startswith('@')]
        for d in dirs:
            dp = os.path.join(root, d)
            try:
                if not os.listdir(dp):
                    os.rmdir(dp)
            except OSError:
                pass


def organize_movie(file, movie_data, dest_root, scan_root):
    """Move file to dest_root/Director/Year - Title/Title.ext with NFC filenames."""
    directors = movie_data.get('director', [])
    director_names = ', '.join(d['name'] for d in directors) if directors else 'Unknown'
    year = movie_data.get('year', 'Unknown')
    title = sanitize_filename(movie_data.get('title', 'Unknown'))
    director_safe = sanitize_filename(director_names)

    dest_dir = os.path.join(dest_root, director_safe, f"{year} - {title}")
    os.makedirs(dest_dir, exist_ok=True)

    ext = os.path.splitext(file)[1]
    new_name = f"{title}{ext}"
    dest_file = os.path.join(dest_dir, new_name)

    if os.path.abspath(file) != os.path.abspath(dest_file):
        shutil.move(file, dest_file)

    cleanup_directory(dest_dir, auto_delete=True)

    # Remove now-empty parent dirs up to (but not including) the scan root
    parent = os.path.dirname(file)
    while os.path.abspath(parent) != os.path.abspath(scan_root) and os.path.exists(parent):
        try:
            if not os.listdir(parent):
                os.rmdir(parent)
                parent = os.path.dirname(parent)
            else:
                break
        except OSError:
            break


def find_subtitle(folder, video_basename):
    """Find a subtitle file matching the video basename."""
    stem = os.path.splitext(video_basename)[0]
    for f in os.listdir(folder):
        if os.path.splitext(f)[0].startswith(stem) and \
                os.path.splitext(f)[1].lower() in SUBTITLE_EXTENSIONS:
            return os.path.join(folder, f)
    return None


def move_subtitle(sub_path, dest_dir, movie_title):
    """Move subtitle alongside the video file."""
    if sub_path and os.path.exists(sub_path):
        ext = os.path.splitext(sub_path)[1]
        dest = os.path.join(dest_dir, f"{sanitize_filename(movie_title)}{ext}")
        try:
            shutil.move(sub_path, dest)
            print(f"  → Subtitle moved: {os.path.basename(sub_path)}")
        except Exception as e:
            print(f"  → Could not move subtitle: {e}")


def get_all_video_files(folder_path):
    files = []
    for root, dirs, filenames in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('@')]
        for f in filenames:
            if f.startswith('.') or f.startswith('@'):
                continue
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS:
                files.append(os.path.join(root, f))
    return sorted(files)


# ── Main ──────────────────────────────────────────────────────────────────────

def prompt_destination():
    """Ask user where to route this film."""
    while True:
        choice = input(
            "  Route to: [aj]=watched together  [am]=Amir only  "
            "[w]=Not Watched Yet  [k]=Kids & Family  [s]=skip  [n]=search by IMDb ID\n"
            "  → "
        ).strip().lower()
        if choice in ('aj', 'am', 'w', 'k', 's', 'n', ''):
            return choice
        print("  Enter aj / am / w / k / s / n")


def main():
    folder_path = input("Please enter the folder path: ").strip().strip('"\'')
    folder_path = os.path.expanduser(folder_path)

    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a directory.")
        sys.exit(1)

    dest_map = {'aj': AJ_PATH, 'am': AMIR_PATH, 'w': WATCH_PATH, 'k': KIDS_PATH}
    for p in dest_map.values():
        os.makedirs(p, exist_ok=True)

    video_files = get_all_video_files(folder_path)
    print(f"\nFound {len(video_files)} video file(s) in '{folder_path}'\n")

    processed = set()

    for file in video_files:
        if file in processed or not os.path.exists(file):
            continue

        original_name = os.path.basename(file)
        print(f"\n{'='*60}")
        print(f"File: {original_name}")

        movie_name, year = clean_movie_name(original_name)
        if not movie_name or len(movie_name) < 2:
            print("✗ Could not extract title — skipping")
            continue

        print(f"Searching: {movie_name}" + (f" ({year})" if year else ""))
        movie_data = get_movie_data(movie_name, year)

        if movie_data:
            directors = movie_data.get('director', [])
            director_str = ', '.join(d['name'] for d in directors) if directors else 'Unknown'
            kids = is_kids_film(movie_data)
            print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) — {director_str}")
            print(f"IMDb: https://www.imdb.com/title/tt{movie_data.movieID}/")
            if kids:
                print("  [Auto-detected as Kids/Family film]")
        else:
            print("✗ No match found.")

        while True:
            choice = prompt_destination()

            if choice == 's' or choice == '':
                print(f"⊘ Skipped: {original_name}")
                break

            elif choice == 'n':
                imdb_id = input("  IMDb ID (e.g. tt0070016): ").strip()
                if not imdb_id:
                    print("⊘ Skipped.")
                    break
                new_data = fetch_movie_by_imdb_id(imdb_id, default_title=movie_name, default_year=year)
                if not new_data:
                    print("  Could not fetch — keeping previous match (if any). Try again or skip.")
                else:
                    movie_data = new_data
                if movie_data:
                    directors = movie_data.get('director', [])
                    director_str = ', '.join(d['name'] for d in directors) if directors else 'Unknown'
                    print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) — {director_str}")
                    if movie_data.movieID:
                        print(f"IMDb: https://www.imdb.com/title/tt{movie_data.movieID}/")
                # Loop again to ask destination

            elif choice in dest_map:
                if not movie_data:
                    print("  No film data — search by IMDb ID first (n) or skip (s).")
                    continue
                dest_root = dest_map[choice]
                title = movie_data.get('title', 'Unknown')
                year_val = movie_data.get('year', 'Unknown')
                directors = movie_data.get('director', [])
                director_str = sanitize_filename(
                    ', '.join(d['name'] for d in directors) if directors else 'Unknown')

                dest_dir = os.path.join(dest_root, director_str, f"{year_val} - {sanitize_filename(title)}")

                # Move subtitle if present
                sub = find_subtitle(os.path.dirname(file), original_name)

                organize_movie(file, movie_data, dest_root, scan_root=folder_path)
                if sub:
                    move_subtitle(sub, dest_dir, title)

                print(f"✓ → {dest_root}/{director_str}/{year_val} - {title}/")
                processed.add(file)
                break

    print("\n✓ Done.")


if __name__ == "__main__":
    main()
