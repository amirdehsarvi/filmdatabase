import os
import re
import sys
# pip install imdbpy beautifulsoup4 requests lxml
from imdb import Cinemagoer
## readline and glob removed for compatibility with IPython and base Python
import requests
from bs4 import BeautifulSoup
import json
import time
import urllib.parse


## Tab completion removed for compatibility with IPython and base Python

# File extension categories
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.m2ts', '.ts', '.vob', '.ogv', '.3gp'}
SUBTITLE_EXTENSIONS = {'.srt', '.sub', '.ass', '.ssa', '.vtt', '.idx'}
DVD_EXTENSIONS = {'.ifo', '.bup', '.vob'}
AUTO_DELETE_EXTENSIONS = {'.nfo', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.txt', '.xml', '.db', '.url'}
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma'}
RELEASE_GROUP_PATTERNS = [
    r'-RARBG$', r'-YTS$', r'-ETRG$', r'-EVO$', r'-FGT$', r'-SPARKS$', r'-GECKOS$',
    r'-Ganool$', r'-AlphaDL$', r'-PSA$', r'-Pahe$', r'-MkvCage$', r'-ShAaNiG$'
]


class SimpleMovieData(dict):
    def __init__(self, imdb_id=None, title=None, year=None, directors=None):
        super().__init__()
        self.movieID = imdb_id.replace('tt', '') if imdb_id else None
        self.data = self
        if title:
            self['title'] = title
        if year:
            self['year'] = year
        if directors:
            self['director'] = [{'name': name} for name in directors]


def build_movie_data(imdb_id=None, title=None, year=None, directors=None):
    """Build a movie-data object compatible with the rest of the script."""
    return SimpleMovieData(imdb_id=imdb_id, title=title, year=year, directors=directors or ['Unknown'])


def has_usable_movie_metadata(movie_data):
    """Return True when movie data contains enough metadata to organize a file."""
    return bool(movie_data and movie_data.get('title') and movie_data.get('year'))


def prompt_for_manual_movie_data(imdb_id=None, default_title="", default_year=None):
    """Prompt the user for movie metadata when IMDb lookup is unavailable."""
    print("  IMDb lookup did not return usable metadata.")
    print("  Using filename metadata where available so the file can still be organized.")

    if default_title:
        title = default_title
        print(f"  Title: {title}")
    else:
        while True:
            title = input("  Title: ").strip()
            if title:
                break
            print("  Title is required.")

    if default_year:
        year = int(default_year)
        print(f"  Year: {year}")
    else:
        while True:
            year_input = input("  Year: ").strip()
            if year_input.isdigit() and len(year_input) == 4:
                year = int(year_input)
                break
            print("  Enter a 4-digit year.")

    director_input = input("  Director name(s), comma-separated [Unknown]: ").strip()
    directors = [name.strip() for name in director_input.split(',') if name.strip()] or ['Unknown']

    return SimpleMovieData(imdb_id=imdb_id, title=title, year=year, directors=directors)


def fetch_movie_by_imdb_id(imdb_id, default_title="", default_year=None):
    """Fetch movie metadata by IMDb ID, falling back to manual entry when needed."""
    normalized_imdb_id = imdb_id.replace('tt', '').strip()

    movie_data = get_movie_data_from_wikidata(normalized_imdb_id, fallback_title=default_title, fallback_year=default_year)
    if has_usable_movie_metadata(movie_data):
        return movie_data

    return prompt_for_manual_movie_data(
        imdb_id=normalized_imdb_id,
        default_title=default_title,
        default_year=default_year,
    )


def search_imdb_suggestions(movie_name, year=None):
    """Search IMDb's public suggestion endpoint for movie matches."""
    try:
        query = movie_name.strip().lower()
        if not query:
            return []

        first_char = next((char for char in query if char.isalnum()), 'x')
        encoded_query = urllib.parse.quote(query)
        url = f"https://v2.sg.media-imdb.com/suggestion/{first_char}/{encoded_query}.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
        candidates = []

        for item in payload.get('d', []):
            if item.get('qid') != 'movie' and item.get('q') != 'feature':
                continue
            item_year = item.get('y')
            if year and item_year and str(item_year) != str(year):
                continue
            candidates.append(item)

        if candidates or not year:
            return candidates

        for item in payload.get('d', []):
            if item.get('qid') == 'movie' or item.get('q') == 'feature':
                candidates.append(item)
        return candidates
    except Exception as e:
        print(f"  Error searching IMDb suggestions: {e}")
        return []


def get_movie_data_from_wikidata(imdb_id, fallback_title=None, fallback_year=None):
    """Fetch title, year, and director metadata from Wikidata using IMDb ID."""
    try:
        imdb_id = imdb_id.replace('tt', '').strip()
        query = """
SELECT ?filmLabel ?directorLabel ?publicationDate WHERE {
  ?film wdt:P345 \"tt%s\".
  OPTIONAL { ?film wdt:P57 ?director. }
  OPTIONAL { ?film wdt:P577 ?publicationDate. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". }
}
""" % imdb_id
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(
            'https://query.wikidata.org/sparql',
            params={'format': 'json', 'query': query},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        bindings = data.get('results', {}).get('bindings', [])
        if not bindings:
            return None

        title = fallback_title
        year = int(fallback_year) if fallback_year else None
        directors = []

        for row in bindings:
            if not title and 'filmLabel' in row:
                title = row['filmLabel']['value']
            if not year and 'publicationDate' in row:
                year = int(row['publicationDate']['value'][:4])
            if 'directorLabel' in row:
                director_name = row['directorLabel']['value']
                if director_name not in directors:
                    directors.append(director_name)

        return build_movie_data(imdb_id=imdb_id, title=title, year=year, directors=directors or ['Unknown'])
    except Exception as e:
        print(f"  Error fetching Wikidata metadata: {e}")
        return None

# Function to clean up extra files in a directory
def cleanup_directory(directory_path, auto_delete=True):
    """Remove unnecessary files from a movie directory, keeping only video and subtitle files"""
    deleted_files = []
    kept_files = []
    
    for root, dirs, files in os.walk(directory_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            _, ext = os.path.splitext(filename.lower())
            
            # Skip hidden files
            if filename.startswith('.'):
                continue
            
            # Keep video files and subtitles
            if ext in VIDEO_EXTENSIONS or ext in SUBTITLE_EXTENSIONS or ext in DVD_EXTENSIONS:
                kept_files.append(file_path)
                continue
            
            # Auto-delete known junk files
            if auto_delete and ext in AUTO_DELETE_EXTENSIONS:
                try:
                    os.remove(file_path)
                    deleted_files.append((file_path, 'auto'))
                    print(f"  → Deleted: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"  → Could not delete {os.path.basename(file_path)}: {e}")
                continue
            
            # Ask about unknown files
            print(f"  → Unknown file type: {filename} ({ext})")
            choice = input(f"    Delete this file? (y/n/all): ").strip().lower()
            if choice == 'y':
                try:
                    os.remove(file_path)
                    deleted_files.append((file_path, 'manual'))
                    print(f"  → Deleted: {filename}")
                except Exception as e:
                    print(f"  → Could not delete {filename}: {e}")
            elif choice == 'all':
                # Delete this and all future files with same extension
                try:
                    os.remove(file_path)
                    deleted_files.append((file_path, 'manual'))
                    AUTO_DELETE_EXTENSIONS.add(ext)
                    print(f"  → Deleted: {filename} (will auto-delete all {ext} files)")
                except Exception as e:
                    print(f"  → Could not delete {filename}: {e}")
            else:
                kept_files.append(file_path)
                print(f"  → Kept: {filename}")
    
    # Remove empty directories after cleaning up files
    for root, dirs, files in os.walk(directory_path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                # Check if directory is empty
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"  → Removed empty folder: {os.path.basename(dir_path)}")
            except OSError:
                pass
    
    return deleted_files, kept_files

# Function to clean and format movie name from the file name
def clean_movie_name(file_name):
    movie_name = os.path.splitext(file_name)[0]
    
    # Extract year if it appears BEFORE the movie name (like "2024 The Other Place")
    year_match = re.match(r'^\s*(19\d{2}|20\d{2})\s+(.+)$', movie_name)
    if year_match:
        year = year_match.group(1)
        movie_name = year_match.group(2)
    else:
        # Look for year elsewhere in the filename
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', movie_name)
        year = year_match.group(1) if year_match else None
        # Remove year and quality markers only if they're at the end
        movie_name = re.sub(r'\s*\b(19\d{2}|20\d{2})\b\s*.*$', '', movie_name)
    
    # Remove common quality patterns
    patterns_to_remove = [
        r'\b\d{3,4}p\b', r'\bBluRay\b', r'\bWEB-DL\b', r'\bWEB\b', r'\bHD\b', r'\bSD\b',
        r'\bAAC\b', r'\bx264\b', r'\bx265\b', r'\bXviD\b', r'\bHDRip\b',
        r'\bDVDRip\b', r'\bBRRip\b', r'\bH264\b', r'\b10bit\b', r'\b8bit\b',
        r'\bHEVC\b', r'\b@lubokvideo\b', r'\bSoftSub\b', r'\bFW\b', r'\bDream\b',
        r'\bVeDeTT\b', r'\bAvaMovie\b'
    ]
    for pattern in patterns_to_remove:
        movie_name = re.sub(pattern, '', movie_name, flags=re.IGNORECASE)

    for pattern in RELEASE_GROUP_PATTERNS:
        movie_name = re.sub(pattern, '', movie_name, flags=re.IGNORECASE)

    # Remove bracketed release metadata.
    movie_name = re.sub(r'\[[^\]]*\]', ' ', movie_name)
    movie_name = re.sub(r'\([^\)]*(?:rarbg|yts|x264|x265|bluray|webrip|web-dl)[^\)]*\)', ' ', movie_name, flags=re.IGNORECASE)
    
    # Replace dots and underscores with spaces
    movie_name = re.sub(r'[_\.]', ' ', movie_name)
    
    # Clean up whitespace
    movie_name = re.sub(r'\s+', ' ', movie_name).strip()
    
    return movie_name, year

# Function to scrape director from IMDb webpage
def scrape_director_from_imdb(imdb_id):
    """Scrape director information from IMDb webpage when API doesn't have it"""
    try:
        url = f"https://www.imdb.com/title/tt{imdb_id}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to find JSON-LD data
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'director' in data:
                    directors = data['director']
                    if isinstance(directors, list):
                        return [d.get('name') for d in directors if isinstance(d, dict) and 'name' in d]
                    elif isinstance(directors, dict) and 'name' in directors:
                        return [directors['name']]
            except (json.JSONDecodeError, KeyError, AttributeError):
                continue
        
        # Fallback: Try to find director in the page content
        director_section = soup.find('li', {'data-testid': 'title-pc-principal-credit'})
        if director_section:
            director_links = director_section.find_all('a', {'class': 'ipc-metadata-list-item__list-content-item'})
            if director_links:
                return [link.get_text(strip=True) for link in director_links]
        
    except Exception as e:
        print(f"  Warning: Could not scrape director info: {e}")
    
    return None

# Function to find IMDb ID by searching IMDb website
def find_imdb_id_from_web(movie_name, year=None):
    """Search IMDb website directly to find movie ID"""
    try:
        url = "https://www.imdb.com/find/"
        params = {'q': movie_name, 'exact': 'on', 'title_type': 'movie'}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find movie links
        movie_links = soup.find_all('a', href=lambda h: h and '/title/tt' in h)
        
        for link in movie_links[:10]:
            href = link.get('href')
            if '/title/tt' in href:
                imdb_id = href.split('/title/')[1].split('/')[0].replace('tt', '')
                title = link.get_text(strip=True)
                
                # If year provided, try to match
                if year:
                    year_text = soup.find(string=lambda s: s and f"({year})" in str(s))
                    if year_text:
                        return imdb_id
                else:
                    return imdb_id
        
        return None
    except Exception as e:
        print(f"  Error searching web: {e}")
        return None

# Function to get movie data from IMDb
def get_movie_data(movie_name, year=None):
    try:
        print(f"  → Searching IMDb suggestions...")
        suggestions = search_imdb_suggestions(movie_name, year)

        if suggestions:
            best_match = suggestions[0]
            imdb_id = best_match.get('id', '').replace('tt', '')
            suggestion_title = best_match.get('l')
            suggestion_year = best_match.get('y') or year

            movie_data = get_movie_data_from_wikidata(imdb_id, fallback_title=suggestion_title, fallback_year=suggestion_year)
            if has_usable_movie_metadata(movie_data):
                return movie_data

            if suggestion_title and suggestion_year:
                return build_movie_data(imdb_id=imdb_id, title=suggestion_title, year=int(suggestion_year), directors=['Unknown'])

        return None
    except Exception as e:
        print(f"  Error searching IMDb: {e}")
        return None

# Function to get movie data by IMDb ID
def get_movie_data_by_id(imdb_id):
    return fetch_movie_by_imdb_id(imdb_id)

# Function to check if a file/folder is already organized
def is_already_organized(current_path, expected_director, expected_year, expected_title, target_folder_path):
    """Check if a file or folder is already in the correct director/year/title structure"""
    expected_structure = os.path.join(target_folder_path, expected_director, f"{expected_year} - {expected_title}")
    
    # Get the parent directory of the current path
    if os.path.isfile(current_path):
        parent_path = os.path.dirname(current_path)
    else:
        parent_path = current_path
    
    # Normalize paths for comparison
    parent_normalized = os.path.normpath(parent_path)
    expected_normalized = os.path.normpath(expected_structure)
    
    return parent_normalized == expected_normalized

# Function to organize DVD folder structure
def organize_dvd_folder(dvd_folder_path, movie_data, target_folder_path):
    """Move entire DVD folder structure to organized location"""
    directors = movie_data.get('director', [])
    director_names = ', '.join(director['name'] for director in directors) if directors else "Unknown"
    release_year = movie_data.get('year', 'Unknown')
    movie_name = movie_data.get('title', 'Unknown')

    dir_structure = os.path.join(target_folder_path, director_names, f"{release_year} - {movie_name}")

    if not os.path.exists(dir_structure):
        os.makedirs(dir_structure)

    # Check if the DVD folder is already at the correct location
    if os.path.normpath(dvd_folder_path) == os.path.normpath(dir_structure):
        print(f"  → DVD folder is already organized at: {dir_structure}")
        # Still run cleanup even if already organized
        cleanup_directory(dvd_folder_path, auto_delete=True)
        return
    
    # Move the contents of the DVD folder (VIDEO_TS, AUDIO_TS, etc.) to the target
    # rather than moving the whole folder
    import shutil
    for item in os.listdir(dvd_folder_path):
        source_item = os.path.join(dvd_folder_path, item)
        dest_item = os.path.join(dir_structure, item)
        
        if os.path.exists(dest_item):
            # If destination already exists, skip or merge
            if os.path.isdir(dest_item):
                # Merge directories if needed
                shutil.copytree(source_item, dest_item, dirs_exist_ok=True)
                shutil.rmtree(source_item)
            else:
                print(f"  → Warning: {item} already exists at destination, skipping")
        else:
            shutil.move(source_item, dest_item)
    
    # Clean up unnecessary files in the DVD folder
    print(f"  → Cleaning up extra files in DVD folder...")
    cleanup_directory(dir_structure, auto_delete=True)
    
    # Delete the now empty source DVD folder
    try:
        if os.path.exists(dvd_folder_path) and not os.listdir(dvd_folder_path):
            os.rmdir(dvd_folder_path)
    except OSError:
        pass
    
    # Delete the now empty parent folders
    parent_dir = os.path.dirname(dvd_folder_path)
    while parent_dir != target_folder_path and parent_dir and os.path.exists(parent_dir):
        try:
            if not os.listdir(parent_dir):
                os.rmdir(parent_dir)
                parent_dir = os.path.dirname(parent_dir)
            else:
                break
        except OSError:
            break

# Function to create directory structure and move files
def organize_movie(file, movie_data, folder_path):
    directors = movie_data.get('director', [])
    director_names = ', '.join(director['name'] for director in directors) if directors else "Unknown"
    release_year = movie_data.get('year', 'Unknown')
    movie_name = movie_data.get('title', 'Unknown')

    dir_structure = os.path.join(folder_path, director_names, f"{release_year} - {movie_name}")

    if not os.path.exists(dir_structure):
        os.makedirs(dir_structure)

    source_file_path = file
    dest_file_path = os.path.join(dir_structure, os.path.basename(file))

    os.rename(source_file_path, dest_file_path)

    new_file_name = f"{movie_name}{os.path.splitext(file)[1]}"
    os.rename(dest_file_path, os.path.join(dir_structure, new_file_name))
    
    # Clean up unnecessary files in the movie directory
    print(f"  → Cleaning up extra files in movie folder...")
    cleanup_directory(dir_structure, auto_delete=True)

    # Delete the now empty folders
    parent_dir = os.path.dirname(source_file_path)
    while parent_dir != folder_path and not os.listdir(parent_dir):
        os.rmdir(parent_dir)
        parent_dir = os.path.dirname(parent_dir)

# Function to get the root DVD folder
def get_dvd_folder_root(file_path):
    """Get the root DVD folder (parent of VIDEO_TS/AUDIO_TS/etc)"""
    path_parts = file_path.split(os.sep)
    dvd_folder_patterns = ['VIDEO_TS', 'AUDIO_TS', 'JACKET', 'AUXDATA', 'CERTIFICATE']
    
    for i, part in enumerate(path_parts):
        if part.upper() in dvd_folder_patterns:
            # Return the parent directory of the DVD folder
            return os.sep.join(path_parts[:i])
    
    return None

# Function to check if a file is inside a DVD folder structure
def is_inside_dvd_folder(file_path):
    """Check if file is inside DVD-specific folders like VIDEO_TS, AUDIO_TS, etc."""
    return get_dvd_folder_root(file_path) is not None

# Function to get all files in the folder, including subfolders
def get_all_files(folder_path):
    all_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

# Function to detect DVD folders by checking for DVD-specific subfolders
def find_dvd_folders(folder_path):
    """Find all DVD folders by looking for VIDEO_TS, AUDIO_TS, etc. subdirectories"""
    dvd_folders = []
    dvd_folder_patterns = ['VIDEO_TS', 'AUDIO_TS', 'JACKET', 'AUXDATA', 'CERTIFICATE']
    
    for root, dirs, _ in os.walk(folder_path):
        for dir_name in dirs:
            if dir_name.upper() in dvd_folder_patterns:
                # Found a DVD-specific folder, add its parent as a DVD folder
                dvd_root = root
                if dvd_root not in dvd_folders:
                    dvd_folders.append(dvd_root)
                break  # No need to check other dirs in this root
    
    return dvd_folders


# Get folder path from user (no tab completion)
folder_path = input("Please enter the folder path: ").strip()

# Remove surrounding quotes if present (single or double)
folder_path = folder_path.strip('"\'')

# Expand ~ to home directory if present
folder_path = os.path.expanduser(folder_path)

# Check if folder exists
if not os.path.exists(folder_path):
    print(f"Error: Folder '{folder_path}' does not exist!")
    sys.exit(1)

if not os.path.isdir(folder_path):
    print(f"Error: '{folder_path}' is not a directory!")
    sys.exit(1)

# Get list of all files in the folder and subfolders
files = get_all_files(folder_path)

print(f"\nFound {len(files)} files in '{folder_path}'")

# Sort files by filename
files.sort()

# Filter out hidden files and show what we're processing
visible_files = [f for f in files if not os.path.basename(f).startswith('.')]
skipped_count = len(files) - len(visible_files)

if skipped_count > 0:
    print(f"Skipping {skipped_count} hidden file(s)")

print(f"Processing {len(visible_files)} file(s)\n")

# Track processed DVD folders to avoid duplicates
processed_dvd_folders = set()

# First, find and process all DVD folders
print("Scanning for DVD folders...")
dvd_folders = find_dvd_folders(folder_path)
if dvd_folders:
    print(f"Found {len(dvd_folders)} DVD folder(s)\n")
    
    for dvd_folder_root in dvd_folders:
        if dvd_folder_root in processed_dvd_folders:
            continue
            
        print(f"\n{'='*60}")
        print(f"DVD Folder detected: {os.path.basename(dvd_folder_root)}")
        print(f"Cleaning up extra files first...")
        cleanup_directory(dvd_folder_root, auto_delete=True)
        
        print(f"Searching for movie information...")
        
        # Try to extract movie info from the path
        path_parts = dvd_folder_root.split(os.sep)
        movie_name_and_year = path_parts[-1] if len(path_parts) > 0 else ""
        
        # Parse different folder name formats
        # Format 1: "YYYY - Movie Name"
        year_match = re.match(r'^(\d{4})\s*-\s*(.+)$', movie_name_and_year)
        if year_match:
            year = year_match.group(1)
            movie_name = year_match.group(2)
            print(f"Extracted from path: {movie_name} ({year})")
        else:
            # Format 2: "Director Name - YYYY - Movie Name" (already organized)
            director_year_match = re.match(r'^(.+?)\s*-\s*(\d{4})\s*-\s*(.+)$', movie_name_and_year)
            if director_year_match:
                director = director_year_match.group(1)
                year = director_year_match.group(2)
                movie_name = director_year_match.group(3)
                print(f"Already organized folder detected: {movie_name} ({year}) by {director}")
            else:
                # Try to parse any year from the name
                year_search = re.search(r'\b(19\d{2}|20\d{2})\b', movie_name_and_year)
                if year_search:
                    year = year_search.group(1)
                    movie_name = re.sub(r'\b(19\d{2}|20\d{2})\b', '', movie_name_and_year).strip(' -')
                    print(f"Extracted from path: {movie_name} ({year})")
                else:
                    # No year found, use whole name
                    year = None
                    movie_name = movie_name_and_year
                    print(f"Extracted from path: {movie_name} (no year found)")
        
        # Search IMDb for confirmation
        movie_data = get_movie_data(movie_name, year)
        
        if not movie_data:
            print(f"✗ Could not find automatic match for '{movie_name}'")
            movie_data = prompt_for_manual_movie_data(default_title=movie_name, default_year=year)
        
        if movie_data:
            imdb_url = f"https://www.imdb.com/title/tt{movie_data.movieID}/"
            directors = movie_data.get('director', [])
            director_str = ', '.join(director['name'] for director in directors) if directors else 'Unknown'
            print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director_str}")
            print(f"IMDb URL: {imdb_url}")
            
            # Check if already organized
            director_names = ', '.join(director['name'] for director in directors) if directors else "Unknown"
            if is_already_organized(dvd_folder_root, director_names, movie_data.get('year'), movie_data.get('title'), folder_path):
                print(f"✓ This DVD folder appears to be already organized correctly!")
                skip_choice = input("  Skip this folder? (y/n): ").strip().lower()
                if skip_choice == 'y':
                    print(f"⊘ Skipped: {os.path.basename(dvd_folder_root)}")
                    processed_dvd_folders.add(dvd_folder_root)
                    continue
            
            # Confirm with user
            while True:
                confirm = input("  Organize this DVD folder? (y/n/search): ").strip().lower()
                if confirm == 'y':
                    organize_dvd_folder(dvd_folder_root, movie_data, folder_path)
                    print(f"✓ Organized: {os.path.basename(dvd_folder_root)}")
                    processed_dvd_folders.add(dvd_folder_root)
                    break
                elif confirm == 'n' or confirm == 'search':
                    imdb_id = input("  Enter IMDb ID (e.g., tt27490099) or press Enter to edit manually: ").strip()
                    if imdb_id:
                        movie_data = fetch_movie_by_imdb_id(imdb_id, default_title=movie_name, default_year=year)
                        imdb_url = f"https://www.imdb.com/title/tt{movie_data.movieID}/"
                        directors = movie_data.get('director', [])
                        director_str = ', '.join(director['name'] for director in directors) if directors else 'Unknown'
                        print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director_str}")
                        print(f"IMDb URL: {imdb_url}")
                    else:
                        movie_data = prompt_for_manual_movie_data(default_title=movie_name, default_year=year)
                        directors = movie_data.get('director', [])
                        director_str = ', '.join(director['name'] for director in directors) if directors else 'Unknown'
                        print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director_str}")
                else:
                    print("  Please enter 'y' (yes), 'n' (no/search), or press Enter to skip")
        else:
            print(f"✗ Skipped: {os.path.basename(dvd_folder_root)}")
            processed_dvd_folders.add(dvd_folder_root)
else:
    print("No DVD folders found.\n")

# Now iterate through each file in the folder
print(f"\n{'='*60}")
print("Processing individual movie files...")
print(f"{'='*60}\n")

# Iterate through each file in the folder
for file in visible_files:
    original_file_name = os.path.basename(file)
    
    # Check if file is inside a DVD folder structure
    dvd_folder_root = get_dvd_folder_root(file) if is_inside_dvd_folder(file) else None
    
    if dvd_folder_root:
        # Skip files inside DVD folders that have already been processed
        if dvd_folder_root in processed_dvd_folders:
            continue
        # If DVD folder not yet processed, skip this file (it will be in the DVD scan)
        continue
    
    # Skip if file no longer exists (might have been deleted during cleanup)
    if not os.path.exists(file):
        continue
    
    movie_name, year = clean_movie_name(original_file_name)
    
    # Skip if movie name is empty
    if not movie_name or len(movie_name) < 2:
        print(f"\n{'='*60}")
        print(f"Original file: {original_file_name}")
        print(f"✗ Skipped: Could not extract valid movie name")
        continue
    
    # Clean up extra files in the parent directory first
    parent_dir = os.path.dirname(file)
    print(f"\n{'='*60}")
    print(f"Original file: {original_file_name}")
    print(f"Cleaning up extra files in directory...")
    cleanup_directory(parent_dir, auto_delete=True)
    
    print(f"Searching for movie: {movie_name}" + (f" ({year})" if year else ""))

    movie_data = get_movie_data(movie_name, year)

    # If not found automatically, ask user for IMDb ID
    if not movie_data:
        print(f"✗ Could not find automatic match for '{movie_name}'")
        movie_data = prompt_for_manual_movie_data(default_title=movie_name, default_year=year)

    if movie_data:
        imdb_url = f"https://www.imdb.com/title/tt{movie_data.movieID}/"
        directors = movie_data.get('director', [])
        director_str = ', '.join(director['name'] for director in directors) if directors else 'Unknown'
        print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director_str}")
        print(f"IMDb URL: {imdb_url}")
        
        # Check if already organized
        director_names = ', '.join(director['name'] for director in directors) if directors else "Unknown"
        if is_already_organized(file, director_names, movie_data.get('year'), movie_data.get('title'), folder_path):
            print(f"✓ This file appears to be already organized correctly!")
            skip_choice = input("  Skip this file? (y/n): ").strip().lower()
            if skip_choice == 'y':
                print(f"⊘ Skipped: {original_file_name}")
                continue
        
        # Confirm with user before organizing
        while True:
            confirm = input("  Organize this file? (y/n/search): ").strip().lower()
            if confirm == 'y':
                organize_movie(file, movie_data, folder_path)
                print(f"✓ Organized: {os.path.basename(file)}")
                break
            elif confirm == 'n' or confirm == 'search':
                imdb_id = input("  Enter IMDb ID (e.g., tt27490099) or press Enter to edit manually: ").strip()
                if imdb_id:
                    movie_data = fetch_movie_by_imdb_id(imdb_id, default_title=movie_name, default_year=year)
                    imdb_url = f"https://www.imdb.com/title/tt{movie_data.movieID}/"
                    directors = movie_data.get('director', [])
                    director_str = ', '.join(director['name'] for director in directors) if directors else 'Unknown'
                    print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director_str}")
                    print(f"IMDb URL: {imdb_url}")
                else:
                    movie_data = prompt_for_manual_movie_data(default_title=movie_name, default_year=year)
                    directors = movie_data.get('director', [])
                    director_str = ', '.join(director['name'] for director in directors) if directors else 'Unknown'
                    print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director_str}")
            else:
                print("  Please enter 'y' (yes), 'n' (no/search), or press Enter to skip")
    else:
        print(f"✗ Skipped: {original_file_name}")

print("\nCleaning up empty folders...")

# Remove empty directories from bottom up
for root, dirs, files in os.walk(folder_path, topdown=False):
    for dir_name in dirs:
        dir_path = os.path.join(root, dir_name)
        try:
            # Check if directory is empty
            if not os.listdir(dir_path):
                os.rmdir(dir_path)
                print(f"  Removed empty folder: {dir_path}")
        except OSError:
            pass

print("\nOrganization complete.")

# /Volumes/Films/ToOrganise/