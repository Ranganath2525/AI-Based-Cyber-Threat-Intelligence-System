import os
import sys
import librosa
import numpy as np
import pickle

# Adjust these paths to where your files are saved
MODEL_PATH = r"D:\PROJECT\CTI\deepfake_audio_model_ranga\deepfake_audio_model.pkl"
SCALER_PATH = r"D:\PROJECT\CTI\deepfake_audio_model_ranga\scaler.pkl"
AUDIO_PATH = r"D:\PROJECT\CTI\deepfake_audio_model_ranga\test01_20s.wav"  # default

SAMPLE_RATE = 16000  # must match what was used during training
N_MFCC = 13

def extract_features(audio_file_path):
    try:
        y, sr = librosa.load(audio_file_path, sr=SAMPLE_RATE)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
        mfccs_mean = np.mean(mfccs, axis=1)
        return mfccs_mean
    except Exception as e:
        print(f"Error extracting features from '{audio_file_path}': {e}")
        return None

def predict_audio(audio_file_path):
    if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
        print("Trained model or scaler not found.")
        return
    
    # Load model and scaler
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    
    # Extract features
    features = extract_features(audio_file_path)
    if features is None:
        print("Could not extract valid features. Exiting.")
        return
    features = features.reshape(1, -1)
    features_scaled = scaler.transform(features)
    
    # Make prediction
    pred = model.predict(features_scaled)[0]
    prob = model.predict_proba(features_scaled)[0]
    pred_label = "REAL" if pred == 1 else "FAKE"
    confidence = prob[pred] * 100
    
    print(f"\n--- Prediction on '{os.path.basename(audio_file_path)}' ---")
    print(f"Result: {pred_label}")
    print(f"Confidence: {confidence:.2f}%")
    print("------------------------------------")

if __name__ == "__main__":
    # Use path from command line, else default to AUDIO_PATH above
    audio_file = sys.argv[1] if len(sys.argv) > 1 else AUDIO_PATH
    if not os.path.exists(audio_file):
        print(f"Audio file '{audio_file}' not found!")
    else:
        predict_audio(audio_file)
