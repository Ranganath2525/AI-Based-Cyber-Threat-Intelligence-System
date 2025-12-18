from flask import Flask, render_template, request, jsonify
import numpy as np
from email_engine import load_model, analyze_email # Import functions from email_engine

app = Flask(__name__)

# Load the model and tokenizer once when the app starts
load_model()

# Existing routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/predict", methods=["POST"])
def predict():
    email = request.form["email"]
    
    # Use the analyze_email function from email_engine
    result_dict, _ = analyze_email(email)
    is_phishing = result_dict["is_phishing"]

    result = "Phishing" if is_phishing else "Not Phishing"
    return render_template("result.html", prediction=result)

# New endpoint for Chrome Extension
@app.route("/ext/analyze_email_content", methods=["POST"])
def analyze_email_content():
    data = request.get_json()
    email_content = data.get('email_text') # content_scanner.js sends 'email_text'

    if not email_content:
        return jsonify({'error': 'No email content provided'}), 400

    result_dict, _ = analyze_email(email_content)
    is_phishing = result_dict["is_phishing"]

    if is_phishing:
        verdict = "Phishing Email"
        explanation = "This email is highly likely to be a phishing attempt. Please exercise extreme caution. Look for suspicious links, unusual sender addresses, and urgent requests for personal information."
    else:
        verdict = "Legitimate Email"
        explanation = "This email appears to be legitimate. However, always remain vigilant and verify the sender and content before taking any action, especially if it contains links or attachments."

    # Return in the format expected by content_scanner.js
    response_data = {
        'email_verdict': verdict,
        'email_explanation': explanation,
        'url_results': [] # Placeholder for URL analysis
    }
    return jsonify(response_data)

if __name__ == "__main__":
    app.run(debug=True, port=5000) # Ensure it runs on port 5000 as expected by the extension