from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_cors import CORS
import os
import sys
import re
import json
import uuid
from functools import wraps
from datetime import datetime, timedelta, timezone
import google.generativeai as genai
import base64
from PIL import Image
import io
import mimetypes
from urllib.parse import urlparse
import jwt
import time
from concurrent.futures import ThreadPoolExecutor
import threading
from threading import Semaphore 
import yt_dlp 
# ...

# --- Add project subdirectories to the Python path ---
sys.path.append(os.path.abspath('deepfake_video_bhuvanesh'))
sys.path.append(os.path.abspath('deepfake_audio_model_rangnath'))
sys.path.append(os.path.abspath('email_phising_tejaswi'))
sys.path.append(os.path.abspath('End-to-End-Malicious-URL-Detection_NReshwar'))

# --- Import our engine modules ---
from deepfake_video_engine import load_model as load_video_model, analyze_video, analyze_image
from deepfake_audio_engine import load_model as load_audio_model, analyze_audio
from email_engine import load_model as load_email_model, analyze_email
from url_engine import load_model as load_url_model, analyze_url

# --- Gemini AI Configuration ---
try:
    with open("gemini_api_key.txt", "r") as f:
        GEMINI_API_KEY = f.read().strip()
    if not GEMINI_API_KEY:
        raise ValueError("API Key is empty in the file.")
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini AI configured successfully.")
except FileNotFoundError:
    GEMINI_API_KEY = None
    print("WARNING: 'gemini_api_key.txt' not found. AI explanations will be disabled.")
except Exception as e:
    GEMINI_API_KEY = None
    print(f"ERROR: Could not initialize Gemini AI. Explanations disabled. Reason: {e}")

def get_gemini_explanation(analysis_type, verdict, result_data, file_path=None, raw_text=None, context=None, source_url=None):
    if not GEMINI_API_KEY:
        return "AI explanations are unavailable. The Gemini API key is not configured."

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            # Acquire the semaphore before making an API call
            with gemini_api_semaphore:
                model = genai.GenerativeModel('models/gemini-pro-latest')
                result_data_for_prompt = result_data.copy()
                result_data_for_prompt.pop('result_image', None)
                result_data_for_prompt.pop('waveform_image', None)

                prompt_text = f"""You are an AI assistant specializing in digital media analysis. Your goal is to explain a verdict from a local model.

Your task is to generate a bullet-point list explaining the verdict.
- Base your explanation ONLY on the contents of the provided media/text.
- Reference specific, observable details (e.g., "unnatural lighting on the face," "robotic tone in the voice").
- Do not repeat the confidence scores or percentages.
- Do not add any introductory or concluding sentences.
- Your final output must be ONLY the bullet points, with each point on a new line starting with a '*' character.

--- EXAMPLES of desired output style ---
- For a FAKE image of Tom Cruise on Iron Man, you might say:
* The lighting on Tom Cruise's face does not match the metallic reflections from the suit.
* There are blurring artifacts around the jawline.
- For a FAKE audio, you might say:
* A slight metallic or robotic tone can be heard.
* The speaker's breathing patterns sound unnatural.
- For a Phishing email, you might say:
* The email creates a false sense of urgency by mentioning an "immediate suspension".
* The sender's address does not match the company's official domain.
- For a REAL video, you might say:
* The lip movements sync naturally with the audio.
* Shadows and lighting appear consistent across the scene.
--- END OF EXAMPLES ---

Now, provide your analysis for the following:

Analysis Type: {analysis_type}
Local Model Verdict: "{verdict.upper()}"
Local Model Data: {json.dumps(result_data_for_prompt)}
"""

                if context:
                    prompt_text += f"\nAdditional Context: {context}"

                if raw_text:
                    prompt_text += f"\n\nOriginal Input Text:\n---\n{raw_text}\n---"

                if source_url:
                    prompt_text += f"\nOriginal Source URL: {source_url}"

                prompt_parts = [prompt_text]
                file_size_limit = 25 * 1024 * 1024  # 25 MB

                if file_path and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    mime_type, _ = mimetypes.guess_type(file_path)

                    if not mime_type:
                        pass
                    elif ('video' in mime_type or 'audio' in mime_type) and file_size < file_size_limit:
                        print(f"Uploading media '{os.path.basename(file_path)}' to Gemini for direct analysis...")
                        media_file = genai.upload_file(path=file_path)
                        
                        # Poll for the file to become active
                        print("Waiting for Gemini file processing...")
                        while media_file.state.name == "PROCESSING":
                            time.sleep(5) # Wait 5 seconds before checking again
                            media_file = genai.get_file(media_file.name)
                        
                        if media_file.state.name != "ACTIVE":
                            raise Exception(f"Uploaded file processing failed. State: {media_file.state.name}")

                        prompt_parts.append(media_file)
                    elif 'image' in mime_type:
                        print(f"Attaching original image '{os.path.basename(file_path)}' to Gemini prompt...")
                        img = Image.open(file_path)
                        prompt_parts.append(img)

                print("Sending descriptive prompt with media to Gemini...")
                response = model.generate_content(prompt_parts)

                if 'media_file' in locals() and media_file:
                    genai.delete_file(media_file.name)
                    print(f"Cleaned up temporary Gemini file: {media_file.name}")

                return response.text
        except Exception as e:
            if "ServerNotFoundError" in str(e) and attempt < max_retries - 1:
                print(f"WARNING [Gemini]: Server not found. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            error_message = f"Could not generate AI explanation. The API call failed, likely due to a server network/DNS issue or rate limiting. (Error: {e})"
            print(f"ERROR [Gemini]: {error_message}")
            import traceback
            traceback.print_exc()
            return error_message

app = Flask(__name__)
CORS(app, resources={r"/ext/*": {"origins": "*"}})
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = 'a-very-secret-key-change-it-later'
USERS_FILE = 'users.json'
HISTORY_FILE = 'history.json'
history_lock = threading.Lock()
gemini_api_semaphore = Semaphore(5)


def download_media_from_url(url, task_type='video'):
    task_id = str(uuid.uuid4())
    output_template = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}.%(ext)s")
    
    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[ext=mp4]/best' if task_type == 'video' else 'best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'filesize_limit': 100 * 1024 * 1024, # 100MB limit
        'socket_timeout': 30, # 30-second timeout for network operations
    }

    if task_type == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }]
    elif task_type == 'image':
        ydl_opts['format'] = 'best'


    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            if task_type == 'audio':
                base, _ = os.path.splitext(downloaded_file)
                downloaded_file = base + '.wav'

            if not os.path.exists(downloaded_file):
                return None, None, f"Failed to locate downloaded file for URL: {url}"
            
            original_filename = secure_filename(info.get('title', 'downloaded_media')[:50]) + f".{info.get('ext', 'tmp')}"
            
            return downloaded_file, original_filename, None
    except Exception as e:
        return None, None, f"Failed to download or process URL. It might be unsupported, private, or timed out. Error: {e}"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {"admin": {"password": "admin", "email": "admin@example.com", "role": "admin", "active": True}}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("WARNING: history.json is corrupted. Starting with a fresh history.")
        return {}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

def add_history_entry(username, tool, verdict, details):
    with history_lock:
        history = load_history()
        if username not in history:
            history[username] = []
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tool": tool,
            "verdict": verdict,
            "details": details
        }
        history[username].insert(0, entry)
        save_history(history)

def generate_jwt(username):
    payload = {'sub': username, 'iat': datetime.now(timezone.utc), 'exp': datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def get_user_from_jwt(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['sub']
    except jwt.ExpiredSignatureError:
        print("--- JWT Token has expired. User needs to log in again. ---")
        return None
    except jwt.InvalidTokenError:
        print("--- Invalid JWT Token received. ---")
        return None

def generate_video_analysis_stream(current_user, video_path, source_identifier):
    """
    OPTIMIZED & UNIFIED video analysis stream generator.
    - Runs local analysis and Gemini upload in parallel.
    - Standardizes the event stream format for all video analyses.
    """
    final_result = None
    gemini_upload_thread = None
    gemini_media_file = None
    
    # --- Helper for threaded Gemini upload ---
    class GeminiUpload:
        def __init__(self):
            self.media_file = None
            self.error = None
        def upload(self, path):
            try:
                print(f"Starting parallel Gemini upload for {os.path.basename(path)}...")
                self.media_file = genai.upload_file(path=path)
                print(f"Parallel Gemini upload finished for {os.path.basename(path)}.")
            except Exception as e:
                self.error = e
                print(f"ERROR during parallel Gemini upload: {e}")

    try:
        print(f"--- Starting analysis for {source_identifier} ---")
        add_history_entry(current_user, "Video Analysis", "Analysis Started", source_identifier)

        # --- OPTIMIZATION: Start Gemini upload in a background thread ---
        uploader = GeminiUpload()
        gemini_upload_thread = threading.Thread(target=uploader.upload, args=(video_path,))
        gemini_upload_thread.start()

        # --- LOCAL ANALYSIS ---
        for event in analyze_video(video_path):
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "result":
                final_result = event
        
        if not final_result:
            raise ValueError("Local analysis failed to produce a result.")

        

        # --- Post-analysis: Send initial result and get explanations ---
        combined_verdict = f"Video: {final_result.get('verdict')}, Audio: {final_result.get('audio_verdict')}"
        print(f"--- Analysis Verdict for {source_identifier} ---")
        print(f"- {combined_verdict}")
        print(f"-------------------------------------")
        add_history_entry(current_user, "Video Analysis", combined_verdict, source_identifier)

        initial_data = {
            'video_prediction': final_result.get('verdict'),
            'video_confidence': final_result.get('average_confidence'),
            'audio_prediction': final_result.get('audio_verdict'),
            'audio_confidence': final_result.get('audio_confidence'),
            'video_explanation': 'Fetching AI explanation...', 
            'audio_explanation': 'Fetching AI explanation...'
        }
        yield f"data: {json.dumps({'type': 'final_result', 'data': initial_data})}\n\n"

        # --- Wait for Gemini upload to finish ---
        gemini_upload_thread.join(timeout=60) # Wait up to 60s for upload
        if gemini_upload_thread.is_alive():
            raise TimeoutError("Gemini upload timed out.")
        if uploader.error:
            raise uploader.error
        gemini_media_file = uploader.media_file

        # --- Get explanations using the now-uploaded file ---
        explanations = {}
        def get_explanation_threaded(key, *args, **kwargs):
            explanations[key] = get_gemini_explanation(*args, **kwargs)

        video_thread = threading.Thread(
            target=get_explanation_threaded,
            args=('video', "Video Analysis", final_result['verdict'], final_result),
            kwargs={'file_path': video_path, 'source_url': source_identifier if 'http' in source_identifier else None}
        )
        video_thread.start()

        audio_data = {'verdict': final_result['audio_verdict'], 'confidence': final_result['audio_confidence']}
        audio_thread = threading.Thread(
            target=get_explanation_threaded,
            args=('audio', "Audio Analysis", final_result['audio_verdict'], audio_data),
            kwargs={'file_path': video_path, 'source_url': source_identifier if 'http' in source_identifier else None}
        )
        audio_thread.start()

        video_thread.join()
        audio_thread.join()

        explanations_data = {
            'video_explanation': explanations.get('video', 'Error retrieving explanation.'),
            'audio_explanation': explanations.get('audio', 'Error retrieving explanation.')
        }
        yield f"data: {json.dumps({'type': 'explanations_ready', 'data': explanations_data})}\n\n"

    except Exception as e:
        print(f"ERROR in video analysis stream for {source_identifier}: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'A critical error occurred: ' + str(e)})}\n\n"
    finally:
        # Cleanup
        if gemini_media_file:
            try:
                genai.delete_file(gemini_media_file.name)
                print(f"Cleaned up temporary Gemini file: {gemini_media_file.name}")
            except Exception as e:
                print(f"Error cleaning up Gemini file {gemini_media_file.name}: {e}")
        if os.path.exists(video_path):
            os.remove(video_path)
            print(f"Cleaned up local media file: {video_path}")



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session.get('role') != 'admin':
            flash("You don't have permission to access this page.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

ALLOWED_MEDIA_EXTENSIONS = {'webm','mp4', 'mov', 'avi', 'mkv', 'wav', 'mp3', 'flac', 'jpg', 'jpeg', 'png', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_MEDIA_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and users[username]['password'] == password:
            if users[username]['active']:
                session['username'], session['role'] = username, users[username]['role']
                return redirect(url_for('dashboard'))
            else: flash("Your account is pending approval.", "warning")
        else: flash("Invalid username or password.", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, password, email = request.form['username'], request.form['password'], request.form['email']
        users = load_users()
        if username in users: flash("Username already exists.", "error")
        else:
            users[username] = {'password': password, 'email': email, 'role': 'user', 'active': False}
            save_users(users)
            flash("Registration successful! Please wait for admin approval.", "success")
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/ext/login', methods=['POST'])
def ext_login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required.'}), 400
    username, password = data['username'], data['password']
    users = load_users()
    user = users.get(username)
    if user and user['password'] == password and user['active']:
        return jsonify({'token': generate_jwt(username)})
    else: return jsonify({'error': 'Invalid username or password.'}), 401

# Whitelist of known-good domains that are often flagged as malicious due to URL structure
KNOWN_GOOD_DOMAINS = [
    'click.grammarly.com',
    'grammarly.com',
    'google.com',
    'youtube.com',
    'facebook.com',
    'twitter.com',
    'linkedin.com',
    'microsoft.com',
    'apple.com',
    'amazon.com',
    'netflix.com',
    'github.com',
    'accounts.google.com',
    'support.google.com',
    'drive.google.com',
    'mail.google.com',
    'reddit.com',
    'instagram.com',
    'wikipedia.org',
    'yahoo.com',
    'bing.com',
]

# Centralized whitelist and analysis logic for URLs
def analyze_url_with_whitelist(url):
    """Checks URL against a whitelist before running the ML model."""
    if len(url) > 2048: 
        return {"url": url, "verdict": "Skipped", "risk_score": 0, "explanation": "URL is too long for analysis."}

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        if domain:
            domain_parts = domain.split('.')
            for i in range(len(domain_parts) - 1):
                parent_domain = '.'.join(domain_parts[i:])
                if parent_domain in KNOWN_GOOD_DOMAINS:
                    return {"url": url, "verdict": "Safe", "risk_score": 0, "explanation": "URL is from a whitelisted domain."}
    except Exception as e:
        print(f"URL parsing failed for {url}: {e}")
        pass # Let the original analyzer handle it if parsing fails

    result, err = analyze_url(url)
    if err: return {"url": url, "verdict": "Error", "error": str(err), "explanation": f"Analysis failed due to a feature extraction error: {err}"}
    verdict = "Malicious" if result.get('is_malicious') else "Safe"
    risk_score = result.get('risk_score', 0)
    
    return {"url": url, "verdict": verdict, "risk_score": risk_score}


@app.route('/ext/analyze_email_content', methods=['POST'])
def ext_analyze_email_content():
    print("--- Email scan started ---")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Authorization token is missing or invalid.'}), 401
    token = auth_header.split(' ')[1]
    username = get_user_from_jwt(token)
    if not username: return jsonify({'error': 'Invalid or expired token.'}), 401
    
    data = request.get_json()
    email_text, urls_to_scan = data.get('email_text', ''), data.get('urls', [])
    
    email_verdict, email_explanation = "Not Scanned", "No email text was provided for analysis."
    if email_text:
        email_result, email_err = analyze_email(email_text)
        if email_err: 
            email_verdict, email_explanation = "Analysis Error", f"An error occurred: {email_err}"
        else:
            email_verdict = "Phishing" if email_result.get('is_phishing') else "Not Phishing"
            email_explanation = get_gemini_explanation("Email Phishing", email_verdict, email_result, raw_text=email_text)
        add_history_entry(username, "Email Scan (Extension)", email_verdict, f"{email_text[:50]}...")
    
    url_analysis_results = []
    if urls_to_scan:
        for url in urls_to_scan:
            # Use the centralized whitelist function
            result = analyze_url_with_whitelist(url)
            # For the extension, we add a generic explanation to avoid extra API calls
            result["explanation"] = "AI explanations for URLs are disabled in the extension for performance."
            add_history_entry(username, "URL Scan (Extension)", result["verdict"], f"{url[:50]}...")
            url_analysis_results.append(result)
            time.sleep(0.5) # Pace the requests slightly
            
    return jsonify({"email_verdict": email_verdict, "email_explanation": email_explanation, "url_results": url_analysis_results})

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html', history=load_history().get(session['username'], []))

@app.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin_panel.html', users=load_users(), history=load_history())

@app.route('/activate_user/<username>', methods=['POST'])
@admin_required
def activate_user(username):
    users = load_users()
    if username in users:
        users[username]['active'] = True
        save_users(users)
        flash(f"User {username} has been activated.", "success")
    else: flash(f"User {username} not found.", "error")
    return redirect(url_for('admin_panel'))

@app.route('/upload_video', methods=['POST'])
@login_required
def upload_video():
    file = request.files.get('file')
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file type'}), 400
    filename = secure_filename(file.filename)
    task_id = f"{uuid.uuid4()}_{filename}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
    file.save(path)
    return jsonify({'task_id': task_id, 'filename': filename})

# --- REFACTORED: Stream Video Analysis with Parallel Explanations ---
@app.route('/stream_video_analysis/<task_id>')
@login_required
def stream_video_analysis(task_id):
    username = session.get('username')
    filename = request.args.get('filename', 'video_file')
    source_url = request.args.get('url', None)
    
    path = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
    if '..' in task_id or not os.path.exists(path):
        return Response("Invalid task ID", status=404)
        
    def generate(current_user):
        final_result = None
        try:
            # 1. Perform local analysis first, streaming progress
            for data in analyze_video(path):
                if data.get("type") == "result":
                    final_result = data
                    combined_verdict = f"Video: {data['verdict']}, Audio: {data['audio_verdict']}"
                    add_history_entry(current_user, "Deepfake Video", combined_verdict, f"{filename}")
                yield f"data: {json.dumps(data)}\n\n"
            
            # 2. If local analysis succeeded, attempt to fetch explanations
            if final_result:
                try:
                    # This new 'try' block specifically handles Gemini connection issues
                    explanations = {}
                    def get_explanation_threaded(key, *args, **kwargs):
                        """Helper function to run in a thread and store the result."""
                        explanations[key] = get_gemini_explanation(*args, **kwargs)

                    # Create and start video explanation thread
                    video_thread = threading.Thread(
                        target=get_explanation_threaded,
                        args=('video', "Video Analysis", final_result['verdict'], final_result),
                        kwargs={'file_path': path, 'source_url': source_url}
                    )
                    video_thread.start()

                    audio_context = f"The visual analysis concluded: '{final_result['verdict']}'."
                    audio_data_for_explanation = {
                        'verdict': final_result['audio_verdict'],
                        'confidence': final_result['audio_confidence']
                    }
                    audio_thread = threading.Thread(
                        target=get_explanation_threaded,
                        args=('audio', "Audio Analysis", final_result['audio_verdict'], audio_data_for_explanation),
                        kwargs={'file_path': path, 'context': audio_context, 'source_url': source_url}
                    )
                    audio_thread.start()

                    # 3. Wait for each thread to finish and stream its result
                    video_thread.join()
                    yield f"data: {json.dumps({'type': 'video_explanation', 'explanation': explanations.get('video', 'Error retrieving explanation.')})}\n\n"
                    
                    audio_thread.join()
                    yield f"data: {json.dumps({'type': 'audio_explanation', 'explanation': explanations.get('audio', 'Error retrieving explanation.')})}\n\n"
                
                except Exception as e:
                    # If fetching explanations fails, send a specific error to the UI
                    print(f"ERROR [Gemini Explanation Phase]: {e}")
                    ai_error_message = (
                        "Could not generate AI explanation. This is likely due to a network issue "
                        "on the server preventing it from connecting to Google's API. "
                        "Please check the server's internet connection and firewall settings."
                    )
                    yield f"data: {json.dumps({'type': 'video_explanation', 'explanation': ai_error_message})}\n\n"
                    yield f"data: {json.dumps({'type': 'audio_explanation', 'explanation': ai_error_message})}\n\n"

        except Exception as e:
            print(f"ERROR in main analysis stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'A critical error occurred during analysis: {e}'})}\n\n"
        finally:
            if os.path.exists(path):
                os.remove(path)
            
    return Response(generate(username), mimetype='text/event-stream')

@app.route('/predict_image', methods=['POST'])
@login_required
def predict_image():
    file = request.files.get('file')
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file'}), 400
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(path)
    try:
        result, err = analyze_image(path)
        if err: return jsonify({'error': err}), 500
        verdict = "FAKE" if result['average_confidence'] > 0.5 else "REAL"
        add_history_entry(session['username'], "Deepfake Image", verdict, f"{filename} ({result['average_confidence']:.2%})")
        explanation = get_gemini_explanation("Deepfake Image", verdict, result, file_path=path)
        return jsonify({"verdict": verdict, "average_confidence": result['average_confidence'], "result_image": result['result_image'], "explanation": explanation})
    finally:
        if os.path.exists(path): os.remove(path)

@app.route('/predict_audio', methods=['POST'])
@login_required
def predict_audio():
    file = request.files.get('file')
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file'}), 400
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(path)
    try:
        result, err = analyze_audio(path)
        if err: return jsonify({'error': err}), 500
        verdict = "FAKE" if result['prediction'] == 0 else "REAL"
        add_history_entry(session['username'], "Deepfake Audio", verdict, f"{filename} ({result['confidence']:.2%})")
        explanation = get_gemini_explanation("Deepfake Audio", verdict, result, file_path=path)
        return jsonify({"verdict": verdict, "confidence": result['confidence'], "explanation": explanation, "waveform_image": result.get("waveform_image")})
    finally:
        if os.path.exists(path): os.remove(path)

@app.route('/predict_video_from_url', methods=['POST'])
@login_required
def predict_video_from_url():
    url = request.json.get('url')
    if not url: return jsonify({'error': 'URL is required'}), 400
    
    path, filename, error = download_media_from_url(url, task_type='video')
    if error: return jsonify({'error': error}), 500
        
    task_id = os.path.basename(path)
    return jsonify({'task_id': task_id, 'filename': filename})

@app.route('/predict_image_from_url', methods=['POST'])
@login_required
def predict_image_from_url():
    url = request.json.get('url')
    if not url: return jsonify({'error': 'URL is required'}), 400
    
    path, filename, error = download_media_from_url(url, task_type='image')
    if error: return jsonify({'error': error}), 500
        
    try:
        result, err = analyze_image(path)
        if err: return jsonify({'error': err}), 500
        verdict = "FAKE" if result['average_confidence'] > 0.5 else "REAL"
        add_history_entry(session['username'], "Deepfake Image (URL)", verdict, f"{filename} ({result['average_confidence']:.2%})")
        explanation = get_gemini_explanation("Deepfake Image", verdict, result, file_path=path, source_url=url)
        return jsonify({"verdict": verdict, "average_confidence": result['average_confidence'], "result_image": result['result_image'], "explanation": explanation})
    finally:
        if os.path.exists(path): os.remove(path)

@app.route('/predict_audio_from_url', methods=['POST'])
@login_required
def predict_audio_from_url():
    url = request.json.get('url')
    if not url: return jsonify({'error': 'URL is required'}), 400

    path, filename, error = download_media_from_url(url, task_type='audio')
    if error: return jsonify({'error': error}), 500
        
    try:
        result, err = analyze_audio(path)
        if err: return jsonify({'error': err}), 500
        verdict = "FAKE" if result['prediction'] == 0 else "REAL"
        add_history_entry(session['username'], "Deepfake Audio (URL)", verdict, f"{filename} ({result['confidence']:.2%})")
        explanation = get_gemini_explanation("Deepfake Audio", verdict, result, file_path=path, source_url=url)
        return jsonify({"verdict": verdict, "confidence": result['confidence'], "explanation": explanation, "waveform_image": result.get("waveform_image")})
    finally:
        if os.path.exists(path): os.remove(path)

@app.route('/predict_combined', methods=['POST'])
@login_required
def predict_combined():
    email_text = request.json.get('text', '')
    url_text = request.json.get('url', '').strip()
    if not email_text and not url_text: return jsonify({'error': 'No input provided'}), 400
    
    email_explanation = None
    email_verdict = "Not Scanned"
    if email_text:
        email_result, email_err = analyze_email(email_text)
        if email_err: return jsonify({'error': f"Email analysis failed: {email_err}"}), 500
        email_verdict = "Phishing" if email_result.get('is_phishing') else "Not Phishing"
        add_history_entry(session['username'], "Email Scan", email_verdict, f"{email_text[:30]}...")
        email_explanation = get_gemini_explanation("Email Phishing", email_verdict, email_result, raw_text=email_text)
        
    found_urls = set(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', email_text))
    if url_text:
        found_urls.add(url_text)
    
    urls_to_scan = list(found_urls)
    url_results = []
    if urls_to_scan:
        for url in urls_to_scan:
            # Use the centralized whitelist function
            result = analyze_url_with_whitelist(url)
            # Add Gemini explanation for the dashboard view
            result['explanation'] = get_gemini_explanation("Malicious URL", result['verdict'], result, raw_text=url)
            url_results.append(result)
            add_history_entry(session['username'], "URL Scan", result['verdict'], f"{url[:50]}...")
            time.sleep(0.5) # Pace API calls
                
    return jsonify({"email_verdict": email_verdict, "email_explanation": email_explanation, "urls_found": len(urls_to_scan), "url_analysis": url_results})

@app.route('/ext/predict_video_extension', methods=['POST'])
def predict_video_extension():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'URL is required'})}\n\n", mimetype='text/event-stream')

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
         return Response(f"data: {json.dumps({'type': 'error', 'message': 'Authorization token is missing or invalid.'})}\n\n", mimetype='text/event-stream')
    
    token = auth_header.split(' ')[1]
    username = get_user_from_jwt(token)
    if not username:
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'Invalid or expired token.'})}\n\n", mimetype='text/event-stream')

    def generate_stream(stream_url, current_user):
        path = None
        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Downloading video...'})}\n\n"
            path, _, error = download_media_from_url(stream_url, task_type='video')
            if error:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to download from URL: ' + str(error)})}\n\n"
                return
            
            # The download is complete, now we can pass it to the unified analysis stream
            # which will handle the rest, including cleanup.
            yield from generate_video_analysis_stream(current_user, path, stream_url)

        except Exception as e:
            print(f"ERROR in URL download phase: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'A critical error occurred during download: ' + str(e)})}\n\n"
            if path and os.path.exists(path):
                os.remove(path) # Ensure cleanup if download succeeds but stream fails

    return Response(generate_stream(url, username), mimetype='text/event-stream')


@app.route('/ext/analyze_recorded_video', methods=['POST'])
def analyze_recorded_video():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'Authorization token missing.'})}\n\n", mimetype='text/event-stream')
    
    token = auth_header.split(' ')[1]
    username = get_user_from_jwt(token)
    if not username:
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'Invalid or expired token.'})}\n\n", mimetype='text/event-stream')

    if 'video' not in request.files:
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'No video file part.'})}\n\n", mimetype='text/event-stream')
    
    file = request.files['video']
    if file.filename == '':
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'No selected file.'})}\n\n", mimetype='text/event-stream')

    filename = secure_filename(f"live_capture_{uuid.uuid4()}.webm")
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    print(f"--- Live capture received and saved to: {path} ---")
    
    # Use the unified, correctly formatted stream generator.
    return Response(generate_video_analysis_stream(username, path, "Live Recorded Video"), mimetype='text/event-stream')

def load_all_models():
    print("-- Pre-loading all AI models into memory --")
    load_video_model()
    load_audio_model()
    load_url_model()
    load_email_model()
    print("\n-- All models loaded. Server is ready. --")

@app.route('/analyze_video_stream', methods=['POST'])
@login_required
def analyze_video_stream():
    data = request.get_json()
    if not data or 'dataUrl' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    try:
        # Decode the data URL
        header, encoded = data['dataUrl'].split(',', 1)
        decoded = base64.b64decode(encoded)

        # Save the decoded data to a temporary file
        filename = f"{uuid.uuid4()}.webm"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(path, 'wb') as f:
            f.write(decoded)

        # Analyze the video
        # The analyze_video function is a generator, so we need to consume it
        result = None
        for res in analyze_video(path):
            if res.get("type") == "result":
                result = res
                break
        
        if not result:
            return jsonify({'error': 'Analysis failed'}), 500

        # Clean up the temporary file
        if os.path.exists(path):
            os.remove(path)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_audio_stream', methods=['POST'])
@login_required
def analyze_audio_stream():
    data = request.get_json()
    if not data or 'dataUrl' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    try:
        # Decode the data URL
        header, encoded = data['dataUrl'].split(',', 1)
        decoded = base64.b64decode(encoded)

        # Save the decoded data to a temporary file
        filename = f"{uuid.uuid4()}.webm"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(path, 'wb') as f:
            f.write(decoded)

        # Analyze the audio
        result, err = analyze_audio(path)
        if err:
            return jsonify({'error': err}), 500

        # Clean up the temporary file
        if os.path.exists(path):
            os.remove(path)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    load_all_models()
    app.run(host='0.0.0.0', port=5000, debug=True)