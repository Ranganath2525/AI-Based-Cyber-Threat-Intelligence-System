from flask import Flask, request, render_template, jsonify
import os
from werkzeug.utils import secure_filename
import predict_engine # Import your prediction engine

# --- Flask App Configuration ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Renders the main web page."""
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def upload_and_predict():
    """Handles video upload and returns a simple, direct verdict."""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file part in the request.'}), 400
    
    file = request.files['video']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid or no file selected.'}), 400
        
    filename = secure_filename(file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        file.save(video_path)
        # Call the engine to get the raw score.
        video_score, err = predict_engine.analyze_video(video_path)
        
        if err:
            return jsonify({'error': err}), 500

        # --- Simple Verdict Logic ---
        # The exact same logic as your final CMD predict.py script.
        final_verdict = "FAKE" if video_score > 0.5 else "REAL"

        # Construct a simple report for the front-end.
        report = {
            "average_confidence": video_score,
            "final_verdict": final_verdict,
        }
        return jsonify(report)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        # Clean up the uploaded file after analysis.
        if os.path.exists(video_path):
            os.remove(video_path)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # Load the AI model into memory before starting the server.
    predict_engine.load_model()
    
    app.run(debug=False, host='0.0.0.0')