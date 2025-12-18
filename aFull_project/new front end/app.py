from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import os
import sys

# --- Add project subdirectories to the Python path ---
sys.path.append(os.path.abspath('deepfake_video_bhuvanesh'))
sys.path.append(os.path.abspath('deepfake_audio_model_rangnath'))
sys.path.append(os.path.abspath('email_phising_tejaswi'))
sys.path.append(os.path.abspath('End-to-End-Malicious-URL-Detection_NReshwar'))

# --- Import the new, consistently named engine modules ---
from deepfake_video_engine import load_model as load_video_model, analyze_video
from deepfake_audio_engine import load_model as load_audio_model, analyze_audio
from email_engine import load_model as load_email_model, analyze_email
from url_engine import load_model as load_url_model, analyze_url

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
# A secret key is required for Flask sessions to work
app.config['SECRET_KEY'] = 'a-very-secret-and-secure-key-change-it' 
ALLOWED_MEDIA_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'wav', 'mp3', 'flac'}

# --- UPDATED User "Database" ---
# We now use a more structured dictionary to hold user info, including roles and activation status.
USERS = {
    "admin": {
        "password": "admin123", 
        "role": "admin", 
        "active": True
    },
    "ranganath": {
        "password": "ranganath@123", 
        "role": "user", 
        "active": True
    }
}

def allowed_file(filename):
    """Checks if an uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_MEDIA_EXTENSIONS

# --- Page Routing ---
@app.route('/', methods=['GET', 'POST'])
def login():
    """Serves the login page and handles user authentication."""
    # --- THIS IS THE FIX ---
    # If a user is already logged in, redirect them straight to the dashboard.
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = USERS.get(username)

        if user and user["password"] == password:
            if user["active"]:
                session['username'] = username
                session['role'] = user['role']
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Your account is pending approval from an administrator.', 'warning')
        else:
            flash('Invalid username or password. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Serves the registration page and SAVES new users."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # --- UPDATED REGISTRATION LOGIC ---
        if username in USERS:
            flash('Username already exists. Please choose another one.', 'error')
        elif not username or not password:
            flash('Username and password are required.', 'error')
        else:
            # Add the new user to our USERS dictionary with 'user' role and 'inactive' status
            USERS[username] = {"password": password, "role": "user", "active": False}
            flash('Registration successful! Your account is now pending admin approval.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logs the user out by clearing the session."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    """Serves the main CTI dashboard page. Protects the route."""
    # If 'username' is not in session, the user is not logged in.
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

# --- NEW: Admin Panel Routes ---

@app.route('/admin')
def admin_panel():
    """Serves the admin panel for user management."""
    # Protect this route: only logged-in admins can access it.
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('dashboard'))
    
    # Pass the entire USERS dictionary to the template
    return render_template('admin_panel.html', users=USERS)

@app.route('/activate_user/<username>', methods=['POST'])
def activate_user(username):
    """Endpoint for the admin to activate a user's account."""
    # Protect this route as well
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    if username in USERS:
        USERS[username]['active'] = True
        flash(f'User "{username}" has been activated.', 'success')
    else:
        flash(f'User "{username}" not found.', 'error')
        
    return redirect(url_for('admin_panel'))


# --- API Endpoints for Tools (No changes below this line) ---
# ... (Your /predict_video, /predict_audio, etc. routes remain exactly the same) ...
@app.route('/predict_video', methods=['POST'])
def predict_video():
    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file or file type for video analysis.'}), 400
    
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    
    score, err = analyze_video(path)
    os.remove(path)
    
    if err: return jsonify({'error': err}), 500
    
    verdict = "FAKE" if score > 0.5 else "REAL"
    return jsonify({"verdict": verdict, "fake_confidence": score})

@app.route('/predict_audio', methods=['POST'])
def predict_audio():
    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file or file type for audio analysis.'}), 400
    
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    
    result, err = analyze_audio(path)
    os.remove(path)
    
    if err: return jsonify({'error': err}), 500
    
    verdict = "FAKE" if result['prediction'] == 0 else "REAL"
    return jsonify({"verdict": verdict, "confidence": result['confidence']})

@app.route('/predict_url', methods=['POST'])
def predict_url():
    url = request.form.get('text')
    if not url: return jsonify({'error': 'No URL was provided in the request.'}), 400
    
    result, err = analyze_url(url)
    if err: return jsonify({'error': err}), 500

    verdict = "Malicious" if result['is_malicious'] else "Safe"
    return jsonify({"verdict": verdict, "risk_score": result['risk_score']})

@app.route('/predict_email', methods=['POST'])
def predict_email():
    email = request.form.get('text')
    if not email: return jsonify({'error': 'No email text was provided in the request.'}), 400
    
    result, err = analyze_email(email)
    if err: return jsonify({'error': err}), 500

    verdict = "Phishing" if result['is_phishing'] else "Not Phishing"
    return jsonify({"verdict": verdict})

def load_all_models():
    """A function to pre-load all AI models into memory when the server starts."""
    print("--- Pre-loading all AI models into memory ---")
    load_video_model()
    load_audio_model()
    load_url_model()
    load_email_model()
    print("\n--- All models loaded. Server is ready. ---")

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    load_all_models()
    
    app.run(host='0.0.0.0', port=5000)