// FILE REMOVED: No longer needed as per user workflow.
import os
import subprocess

def get_video_info(filepath):
    """Gets video quality (height) and file size from a file using mediainfo."""
    info = {"resolution": 0, "size": 0}
    try:
        result = subprocess.run(
            ["mediainfo", "--Inform=Video;%Height%", filepath],
            capture_output=True,
            text=True,
            check=True,
        )
        info["resolution"] = int(result.stdout.strip())
        result = subprocess.run(
            ["mediainfo", "--Inform=General;%FileSize%", filepath],
            capture_output=True,
            text=True,
            check=True,
        )
        info["size"] = int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        print(f"Error reading metadata from {filepath}. Skipping.")
    return info

def find_srt_files(directory, base_filename):
    """Finds SRT subtitle files in a directory."""
    srt_files = []
    for filename in os.listdir(directory):
        if filename.lower().endswith(".srt") and filename.lower().startswith(base_filename.lower()):
            srt_files.append(os.path.join(directory, filename))
    return srt_files

def process_folders(source_folder, destination_root):
    """Processes video files and subtitles between source and destination, searching in subfolders."""

    for filename in os.listdir(source_folder):
        if filename.lower().endswith((".mkv", ".mp4", ".avi")):
            source_filepath = os.path.join(source_folder, filename)

            # Extract director and film folder name from source path
            director_folder = os.path.basename(os.path.dirname(source_folder))
            film_folder = os.path.basename(source_folder)

            # Construct the potential destination folder path
            dest_folder = os.path.join(destination_root, director_folder, film_folder)

            if os.path.exists(dest_folder):
                dest_filepath = os.path.join(dest_folder, filename)

                if os.path.exists(dest_filepath):
                    source_info = get_video_info(source_filepath)
                    dest_info = get_video_info(dest_filepath)

                    print(f"Comparing {filename}:")
                    print(f"  Source: {source_info['resolution']}p, {source_info['size']} bytes")
                    print(f"  Destination: {dest_info['resolution']}p, {dest_info['size']} bytes")

                    if source_info["resolution"] > dest_info["resolution"] or (source_info["resolution"] == dest_info["resolution"] and source_info["size"] > dest_info["size"]):
                        try:
                            subprocess.run(
                                ["rsync", "-av", "--remove-source-files", source_filepath, dest_filepath],
                                check=True,
                            )
                            print(f"Replaced {filename} in {dest_folder} with higher quality/size version.")

                            base_filename = os.path.splitext(filename)[0]
                            source_srt_files = find_srt_files(source_folder, base_filename)
                            dest_srt_files = find_srt_files(dest_folder, base_filename)

                            for srt_file in source_srt_files:
                                dest_srt_filename = os.path.join(dest_folder, os.path.basename(srt_file))
                                if os.path.exists(dest_srt_filename):
                                    os.remove(dest_srt_filename)
                                subprocess.run(
                                    ["rsync", "-av", "--remove-source-files", srt_file, dest_folder],
                                    check=True,
                                )
                                print(f"Moved SRT file for {filename}.")

                        except subprocess.CalledProcessError as e:
                            print(f"Error moving {filename} or SRT files: {e}")

                    else:
                        print(f"{filename} in {dest_folder} is already higher or equal quality/size. Skipping.")
                else:
                    try:
                        subprocess.run(
                            ["rsync", "-av", "--remove-source-files", source_filepath, dest_filepath],
                            check=True,
                        )
                        print(f"Moved {filename} to {dest_folder}.")

                        base_filename = os.path.splitext(filename)[0]
                        source_srt_files = find_srt_files(source_folder, base_filename)

                        for srt_file in source_srt_files:
                            subprocess.run(
                                ["rsync", "-av", "--remove-source-files", srt_file, dest_folder],
                                check=True,
                            )
                            print(f"Moved SRT file for {filename}.")
                    except subprocess.CalledProcessError as e:
                        print(f"Error moving {filename} or SRT files: {e}")
            else:
                # Destination folder doesn't exist - create it and move the file
                print(f"Creating new destination folder: {dest_folder}")
                try:
                    os.makedirs(dest_folder, exist_ok=True)
                    dest_filepath = os.path.join(dest_folder, filename)
                    
                    subprocess.run(
                        ["rsync", "-av", "--remove-source-files", source_filepath, dest_filepath],
                        check=True,
                    )
                    print(f"Moved {filename} to new folder {dest_folder}.")

                    base_filename = os.path.splitext(filename)[0]
                    source_srt_files = find_srt_files(source_folder, base_filename)

                    for srt_file in source_srt_files:
                        subprocess.run(
                            ["rsync", "-av", "--remove-source-files", srt_file, dest_folder],
                            check=True,
                        )
                        print(f"Moved SRT file for {filename}.")
                except (subprocess.CalledProcessError, OSError) as e:
                    print(f"Error creating folder or moving {filename}: {e}")

def main():
    source_root = input("Enter the source root folder: ")
    destination_root = input("Enter the destination root folder: ")

    for director_folder in os.listdir(source_root):
        director_path = os.path.join(source_root, director_folder)

        if os.path.isdir(director_path):
            for film_folder in os.listdir(director_path):
                film_path = os.path.join(director_path, film_folder)

                if os.path.isdir(film_path):
                    process_folders(film_path, destination_root)

    # Delete empty folders in source
    for director_folder in os.listdir(source_root):
        director_path = os.path.join(source_root, director_folder)
        if os.path.isdir(director_path):
            for film_folder in os.listdir(director_path):
                film_path = os.path.join(director_path, film_folder)
                if os.path.isdir(film_path) and not os.listdir(film_path):
                    try:
                        os.rmdir(film_path)
                        print(f"Deleted empty folder: {film_path}")
                    except Exception as e:
                        print(f"Could not delete empty folder: {film_path}. Error: {e}")
            if not os.listdir(director_path):
                try:
                    os.rmdir(director_path)
                    print(f"Deleted empty folder: {director_path}")
                except Exception as e:
                    print(f"Could not delete empty folder: {director_path}. Error: {e}")
if __name__ == "__main__":
    main()

# /Volumes/Films/watchedorganise/
# /Volumes/Films/AJ/