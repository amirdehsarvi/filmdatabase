import os
import re
from imdb import IMDb

# Function to clean and format movie name from the file name
def clean_movie_name(file_name):
    movie_name = os.path.splitext(file_name)[0]
    patterns_to_remove = [
        r'\b\d{3,4}p\b', r'\bBluRay\b', r'\bWEB\b', r'\bHD\b', r'\bSD\b', 
        r'\bAAC\b', r'\bx264\b', r'\bx265\b', r'\bXviD\b', r'\bHDRip\b', 
        r'\bDVDRip\b', r'\bBRRip\b', r'\bH264\b', r'\b10bit\b', r'\b8bit\b', 
        r'\bHEVC\b', r'\b@lubokvideo\b', r'\bSoftSub\b', r'\bFW\b', r'\bDream\b',
        r'\bVeDeTT\b', r'\bAvaMovie\b'
    ]
    for pattern in patterns_to_remove:
        movie_name = re.sub(pattern, '', movie_name, flags=re.IGNORECASE)
    movie_name = re.sub(r'[_\.]', ' ', movie_name)
    movie_name = re.sub(r'\s+', ' ', movie_name).strip()
    movie_name = re.sub(r'\b\d{4}\b.*$', '', movie_name).strip()
    return movie_name

# Function to get movie data from IMDb
def get_movie_data(movie_name, ia):
    try:
        search_results = ia.search_movie(movie_name)
        if search_results:
            return ia.get_movie(search_results[0].movieID)  # Return the first search result
    except Exception as e:
        print(f"IMDb lookup failed for '{movie_name}': {e}")
    return None

# Function to create directory structure and move files
def organize_movie(file, movie_data, folder_path):
    director_list = movie_data.get('director')
    director_name = "Unknown" if not director_list else director_list[0]['name']
    release_year = movie_data.get('year', 'Unknown')
    movie_name = movie_data.get('title', 'Unknown')
    dir_structure = os.path.join(folder_path, director_name, f"{release_year} - {movie_name}")
    os.makedirs(dir_structure, exist_ok=True)
    source_file_path = os.path.join(folder_path, file)
    new_file_name = f"{movie_name}{os.path.splitext(file)[1]}"
    dest_file_path = os.path.join(dir_structure, new_file_name)
    try:
        os.rename(source_file_path, dest_file_path)
    except Exception as e:
        print(f"Failed to move/rename '{file}': {e}")

# Get folder path from user
folder_path = input("Please enter the folder path: ")

# Only process common video file extensions

# Video and subtitle extensions
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.mpg', '.mpeg', '.m4v'}
SUBTITLE_EXTENSION = '.srt'

# Get list of files in the folder

# Gather all files in the folder
all_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

# Filter video files
files = [f for f in all_files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS]

# Instantiate IMDb once
ia = IMDb()

# Iterate through each file in the folder

for file in files:
    if file.startswith('.'):
        continue
    movie_name = clean_movie_name(file)
    print(f"Searching for movie: {movie_name}")

    movie_data = get_movie_data(movie_name, ia)

    if not movie_data:
        print(f"No data found for movie: {movie_name}")
        continue

    director = movie_data.get('director', [{'name': 'Unknown'}])[0]['name']
    print(f"Found: {movie_data.get('title')} ({movie_data.get('year')}) directed by {director}")
    organize_movie(file, movie_data, folder_path)
    print(f"Moved and renamed file: {file}")

    # Handle corresponding .srt subtitle file
    base_name, _ = os.path.splitext(file)
    srt_file = base_name + SUBTITLE_EXTENSION
    if srt_file in all_files:
        try:
            # Move and rename subtitle file to match new movie name
            director_list = movie_data.get('director')
            director_name = "Unknown" if not director_list else director_list[0]['name']
            release_year = movie_data.get('year', 'Unknown')
            movie_name_final = movie_data.get('title', 'Unknown')
            dir_structure = os.path.join(folder_path, director_name, f"{release_year} - {movie_name_final}")
            os.makedirs(dir_structure, exist_ok=True)
            new_srt_name = f"{movie_name_final}{SUBTITLE_EXTENSION}"
            src_srt_path = os.path.join(folder_path, srt_file)
            dst_srt_path = os.path.join(dir_structure, new_srt_name)
            os.rename(src_srt_path, dst_srt_path)
            print(f"Moved and renamed subtitle: {srt_file}")
        except Exception as e:
            print(f"Failed to move/rename subtitle '{srt_file}': {e}")

print("Organization complete.")
