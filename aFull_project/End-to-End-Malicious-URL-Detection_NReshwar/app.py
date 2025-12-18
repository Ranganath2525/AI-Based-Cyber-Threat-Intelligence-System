# backend/app.py

# We need render_template to serve the HTML file
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import joblib
import pandas as pd
import os

# This import might cause issues if your src folder isn't set up as a package.
# If this line causes an error, we may need to adjust the project structure,
# but let's assume it works for now.
from src.data.feature_extractor import FeatureExtractor

app = Flask(__name__)
# Enable CORS, which is still good practice for APIs.
CORS(app)

# --- Load the Trained Model ---
MODEL_DIR = 'models'
MODEL_FILE = 'random_forest.pkl'
model_path = os.path.join(MODEL_DIR, MODEL_FILE)

try:
    model = joblib.load(model_path)
    print(f"Model {MODEL_FILE} loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

# --- Main Route to Serve the Webpage ---
# This is the BIG CHANGE. Instead of sending a JSON message, it sends your webpage.
@app.route('/', methods=['GET'])
def home():
    # Flask will automatically look for 'index.html' in the 'templates' folder.
    return render_template('index.html')

# --- API Endpoint for Analysis ---
# This part remains the same.
@app.route('/api/analyze', methods=['POST'])
def analyze():
    if model is None:
        return jsonify({'error': 'Model is not available. Please check server logs.'}), 500

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL not provided in JSON body.'}), 400

    url_to_check = data['url']

    try:
        extractor = FeatureExtractor(url_to_check)
        features_dict = extractor.extract_all_features()
        features_df = pd.DataFrame([features_dict])

        prediction_encoded = model.predict(features_df)
        prediction_proba = model.predict_proba(features_df)

        prediction_status = 'malicious' if prediction_encoded[0] == 1 else 'safe'
        risk_score = round(prediction_proba[0][1] * 100)

        response = {
            'url': url_to_check,
            'status': prediction_status,
            'riskScore': risk_score,
            'is_malicious': bool(prediction_encoded[0]),
            'features': features_dict
        }
        return jsonify(response)
    except Exception as e:
        print(f"Prediction Error: {e}")
        return jsonify({'error': f'An error occurred during prediction: {str(e)}'}), 500

if __name__ == '__main__':
    # debug=True is great for development, causing auto-restarts
    app.run(host='0.0.0.0', port=5000, debug=True)