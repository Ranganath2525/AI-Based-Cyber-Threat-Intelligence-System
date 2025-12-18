import os
from datetime import datetime

def compile_project_files(file_paths, output_file):
    """
    Reads a list of specified files and writes their paths and contents
    into a single output text file, filtering by allowed extensions.

    Args:
        file_paths (list): A list of absolute paths to the files.
        output_file (str): The full path of the text file to save the output.
    """
    # --- MODIFIED LINE ---
    # Added '.css' and '.txt' to ensure all your files are included
    allowed_extensions = ('.py', '.html', '.js', '.json', '.css', '.txt')

    # Open the output file in write mode with UTF-8 encoding
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            print(f"Successfully created output file: {output_file}\n")
            
            # Loop through each file path provided in the list
            for file_path in file_paths:
                # Check if the file has one of the allowed extensions
                if file_path.endswith(allowed_extensions):
                    try:
                        # Open and read the content of the source file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                            content = infile.read()
                            
                            # Write a header with the file path to the output file
                            outfile.write("=" * 80 + "\n")
                            outfile.write(f"--- FILE: {file_path} ---\n")
                            outfile.write("=" * 80 + "\n\n")
                            
                            # Write the content of the file
                            outfile.write(content)
                            
                            # Write a footer to clearly separate files
                            outfile.write("\n\n" + "-" * 80 + "\n")
                            outfile.write(f"--- END OF FILE: {os.path.basename(file_path)} ---\n")
                            outfile.write("-" * 80 + "\n\n\n")
                            
                            print(f"[SUCCESS] Read and wrote: {file_path}")

                    except FileNotFoundError:
                        print(f"[ERROR] File not found: {file_path}")
                    except Exception as e:
                        print(f"[ERROR] Could not read file {file_path}: {e}")
                else:
                    # This message will no longer appear for your .css and .txt files
                    print(f"[SKIPPED] File does not have an allowed extension: {file_path}")

    except IOError as e:
        print(f"Fatal error: Could not write to output file {output_file}. Reason: {e}")

if __name__ == "__main__":
    # --- List of all file paths you provided ---
    # --- All files listed here will now be included ---
    files_to_read = [
        r"D:\PROJECT\CTI\aFull_project\cti-url-scanner-extension\popup.js",
        r"D:\PROJECT\CTI\aFull_project\cti-url-scanner-extension\background.js",
        r"D:\PROJECT\CTI\aFull_project\cti-url-scanner-extension\content_scanner.js",
        r"D:\PROJECT\CTI\aFull_project\cti-url-scanner-extension\find_video.js",
        r"D:\PROJECT\CTI\aFull_project\cti-url-scanner-extension\manifest.json",
        r"D:\PROJECT\CTI\aFull_project\cti-url-scanner-extension\popup.html",
        r"D:\PROJECT\CTI\aFull_project\deepfake-video-scanner-extension\manifest.json",
        r"D:\PROJECT\CTI\aFull_project\deepfake-video-scanner-extension\popup.html",
        r"D:\PROJECT\CTI\aFull_project\deepfake-video-scanner-extension\popup.js",
        r"D:\PROJECT\CTI\aFull_project\deepfake-video-scanner-extension\background.js",
        r"D:\PROJECT\CTI\aFull_project\real-time-deepfake-capture-scan\manifest.json",
        r"D:\PROJECT\CTI\aFull_project\real-time-deepfake-capture-scan\offscreen.html",
        r"D:\PROJECT\CTI\aFull_project\real-time-deepfake-capture-scan\offscreen.js",
        r"D:\PROJECT\CTI\aFull_project\real-time-deepfake-capture-scan\popup.html",
        r"D:\PROJECT\CTI\aFull_project\real-time-deepfake-capture-scan\popup.js",
        r"D:\PROJECT\CTI\aFull_project\real-time-deepfake-capture-scan\background.js",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\download_tokenizer.py",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\app.py",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\templates\admin_panel.html",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\templates\dashboard.html",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\templates\index.html",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\templates\login.html",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\templates\register.html",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\static\login_script.js",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\static\script.js",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\static\style.css",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\local_bert_tokenizer\special_tokens_map.json",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\local_bert_tokenizer\tokenizer_config.json",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\local_bert_tokenizer\vocab.txt",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\End-to-End-Malicious-URL-Detection_NReshwar\url_engine.py",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\email_phising_tejaswi\email_engine.py",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\deepfake_video_bhuvanesh\deepfake_video_engine.py",
        r"D:\PROJECT\CTI\aFull_project\aFull_project\deepfake_audio_model_rangnath\deepfake_audio_engine.py"
    ]

    # Define the directory to save the backup files
    save_directory = r"D:\PROJECT\CTI\aFull_project\aFull_project\.saves_backup_codes"
    
    # Create the directory if it doesn't exist
    os.makedirs(save_directory, exist_ok=True)
    
    # Generate a filename with the current date and time
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_filename = f"file_{timestamp_str}.txt"
    
    # Create the full path for the output file
    full_output_path = os.path.join(save_directory, output_filename)
    
    # Run the compilation function with the full path
    compile_project_files(files_to_read, full_output_path)
    
    print(f"\nProcess finished. All specified code has been compiled into '{full_output_path}'")