import os
import glob
import shutil

print("--- Starting Dataset Organization ---")

# --- Define Paths ---
# The main path of your project
BASE_PATH = r"C:\Users\Rakshitha\OneDrive\Desktop\deep fake audio detection"

# The source folder containing the unorganized SceneFake dataset
SOURCE_DATABASE_PATH = os.path.join(BASE_PATH, "SceneFake")

# The final destination folders for your training data
DEST_REAL_PATH = os.path.join(BASE_PATH, "data", "Real")
DEST_FAKE_PATH = os.path.join(BASE_PATH, "data", "Fake")

# --- Ensure Destination Folders Exist ---
os.makedirs(DEST_REAL_PATH, exist_ok=True)
os.makedirs(DEST_FAKE_PATH, exist_ok=True)

# --- Function to Move Files ---
def move_files(source_dir, dest_dir, file_type):
    """
    Finds all .wav files in a source directory and moves them to a destination directory.
    """
    files_to_move = glob.glob(os.path.join(source_dir, "*.wav"))
    
    if not files_to_move:
        print(f"No '.wav' files found in {source_dir}")
        return 0

    print(f"Moving {len(files_to_move)} '{file_type}' files from '{os.path.basename(source_dir)}'...")
    
    moved_count = 0
    for file_path in files_to_move:
        # Construct the destination path
        file_name = os.path.basename(file_path)
        destination_file = os.path.join(dest_dir, file_name)
        
        # Move the file
        shutil.move(file_path, destination_file)
        moved_count += 1
        
    return moved_count

# --- Main Logic ---
total_real_moved = 0
total_fake_moved = 0

# Check if the source database path exists
if not os.path.isdir(SOURCE_DATABASE_PATH):
    print(f"\nERROR: The source folder was not found at: {SOURCE_DATABASE_PATH}")
    print("Please make sure you have downloaded and unzipped the 'SceneFake' folder into your project directory.")
else:
    print(f"\nFound source dataset folder: {SOURCE_DATABASE_PATH}")
    # Iterate through 'train', 'dev', and 'eval' folders
    for data_split in ["train", "dev", "eval"]:
        split_path = os.path.join(SOURCE_DATABASE_PATH, data_split)
        
        if os.path.isdir(split_path):
            print(f"\nProcessing folder: '{data_split}'")
            
            # Move REAL files
            real_source_path = os.path.join(split_path, "real")
            if os.path.isdir(real_source_path):
                total_real_moved += move_files(real_source_path, DEST_REAL_PATH, "Real")
            
            # Move FAKE files
            fake_source_path = os.path.join(split_path, "fake")
            if os.path.isdir(fake_source_path):
                total_fake_moved += move_files(fake_source_path, DEST_FAKE_PATH, "Fake")
        else:
            print(f"\nWarning: Subfolder '{data_split}' not found in SceneFake directory.")

    print("\n--- Organization Complete! ---")
    print(f"Total REAL files moved: {total_real_moved}")
    print(f"Total FAKE files moved: {total_fake_moved}")
    print(f"Your files are now ready in the '{os.path.join('data', 'Real')}' and '{os.path.join('data', 'Fake')}' folders.")