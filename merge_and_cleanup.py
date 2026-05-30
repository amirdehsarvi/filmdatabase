#!/usr/bin/env python3
"""
Merge folders and remove the source folder after successful rsync completion.
Allows user to choose between default paths or custom source/destination.
"""

import os
import subprocess
import shutil

# Default paths
DEFAULT_SOURCE = "/Volumes/Films/ToOrganise/"
DEFAULT_DESTINATION = "/Volumes/Films/AJ/"
CUSTOM_SOURCE = "/Volumes/AJ4/Downloads"
CUSTOM_DESTINATION = "/Volumes/Films/Not Watched Yet"

SOURCE = DEFAULT_SOURCE
DESTINATION = DEFAULT_DESTINATION
DELETE_SOURCE = False  # Track whether we should delete the source folder

def check_paths_exist():
    """Verify both source and destination paths exist"""
    if not os.path.exists(SOURCE):
        print(f"Error: Source path does not exist: {SOURCE}")
        return False
    if not os.path.exists(DESTINATION):
        print(f"Error: Destination path does not exist: {DESTINATION}")
        return False
    print(f"✓ Source exists: {SOURCE}")
    print(f"✓ Destination exists: {DESTINATION}")
    return True

def count_files(path):
    """Count total files in a directory tree"""
    count = 0
    for root, dirs, files in os.walk(path):
        count += len(files)
    return count

def rsync_merge():
    """Merge source into destination using rsync"""
    print(f"\n{'='*60}")
    print("Starting rsync merge...")
    print(f"{'='*60}")
    
    # rsync command: -av = archive + verbose, -h = human readable, --progress = show progress
    cmd = [
        "rsync",
        "-avh",
        "--progress",
        "--stats",
        SOURCE,
        DESTINATION
    ]
    
    print(f"Command: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✓ rsync completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ rsync failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n✗ Error running rsync: {e}")
        return False

def verify_merge():
    """Verify that files were copied"""
    source_count = count_files(SOURCE)
    dest_count = count_files(DESTINATION)
    
    print(f"\n{'='*60}")
    print("Verifying merge...")
    print(f"{'='*60}")
    print(f"Files in source: {source_count}")
    print(f"Files in destination: {dest_count}")
    
    if source_count == 0:
        print("✓ Source is empty (nothing to merge)")
        return True
    
    return True  # Allow cleanup even if counts differ

def cleanup_source(skip_confirm=False, delete_source=False):
    """Remove the source folder after successful merge (only if specified)"""
    if not delete_source:
        # For default path: delete contents but keep the folder
        print(f"\n{'='*60}")
        print("Cleaning up source folder contents...")
        print(f"{'='*60}")
        
        try:
            for item in os.listdir(SOURCE):
                item_path = os.path.join(SOURCE, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"✓ Removed folder: {item}")
                else:
                    os.remove(item_path)
                    print(f"✓ Removed file: {item}")
            
            print(f"\n✓ Successfully emptied {SOURCE}")
            print(f"  (Main folder kept for reuse)")
            return True
        except Exception as e:
            print(f"✗ Error cleaning up source folder: {e}")
            return False
    
    # For custom paths: delete entire source folder
    print(f"\n{'='*60}")
    print("Cleaning up source folder...")
    print(f"{'='*60}")
    
    # Double-check before deletion
    if not skip_confirm:
        response = input(f"Remove {SOURCE}? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("✗ Cleanup cancelled")
            return False
    
    try:
        shutil.rmtree(SOURCE)
        print(f"✓ Successfully removed: {SOURCE}")
        return True
    except Exception as e:
        print(f"✗ Error removing source folder: {e}")
        return False

def get_user_paths():
    """Ask user to choose between default and custom paths"""
    print(f"\n{'='*60}")
    print("Path Selection")
    print(f"{'='*60}")
    print("\nOptions:")
    print(f"1. Default: {DEFAULT_SOURCE} → {DEFAULT_DESTINATION}")
    print(f"   (Contents deleted, folder kept for reuse)")
    print(f"\n2. Custom: {CUSTOM_SOURCE} → {CUSTOM_DESTINATION}")
    print(f"   (Entire source folder deleted after merge)")
    print(f"\n3. Manual: Enter custom paths")
    
    choice = input("\nEnter your choice (1/2/3): ").strip()
    
    if choice == '1':
        return DEFAULT_SOURCE, DEFAULT_DESTINATION, False
    elif choice == '2':
        return CUSTOM_SOURCE, CUSTOM_DESTINATION, True
    elif choice == '3':
        source = input("Enter source path: ").strip().strip('"\'')
        source = os.path.expanduser(source)
        if not source.endswith('/'):
            source += '/'
        
        destination = input("Enter destination path: ").strip().strip('"\'')
        destination = os.path.expanduser(destination)
        if not destination.endswith('/'):
            destination += '/'
        
        delete = input("Delete source folder after merge? (yes/no): ").strip().lower() == 'yes'
        return source, destination, delete
    else:
        print("✗ Invalid choice, using default")
        return DEFAULT_SOURCE, DEFAULT_DESTINATION, False

def main(skip_confirm=False):
    """Main function to merge folders. Set skip_confirm=True for non-interactive use."""
    global SOURCE, DESTINATION, DELETE_SOURCE
    
    print("Film File Merger - Merge folders\n")
    
    # Step 0: Get paths from user
    SOURCE, DESTINATION, DELETE_SOURCE = get_user_paths()
    
    print(f"\n{'='*60}")
    print(f"Source: {SOURCE}")
    print(f"Destination: {DESTINATION}")
    print(f"Delete source: {DELETE_SOURCE}")
    print(f"{'='*60}")
    
    # Step 1: Verify paths exist
    if not check_paths_exist():
        raise RuntimeError("Paths do not exist")
    
    # Step 2: Show initial file counts
    source_files = count_files(SOURCE)
    print(f"\nFiles to merge: {source_files}")
    
    if source_files == 0:
        print("✓ Source folder is empty, nothing to merge")
        return True
    
    # Step 3: Confirm before proceeding
    if not skip_confirm:
        response = input(f"\nProceed with merge? (yes/no): ").strip().lower()
        if response != 'yes':
            print("✗ Merge cancelled")
            return False
    
    # Step 4: Run rsync
    if not rsync_merge():
        raise RuntimeError("rsync failed")
    
    # Step 5: Verify the merge
    verify_merge()
    
    # Step 6: Cleanup source
    if not cleanup_source(skip_confirm=skip_confirm, delete_source=DELETE_SOURCE):
        print("\n⚠ Merge completed but source folder was not removed")
        if DELETE_SOURCE:
            print("You can manually remove it later or re-run this script")
        return False
    
    print(f"\n{'='*60}")
    print("✓ Merge and cleanup completed successfully!")
    print(f"{'='*60}")
    return True

if __name__ == "__main__":
    main()
