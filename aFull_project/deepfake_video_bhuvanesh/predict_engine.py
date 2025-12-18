import torch
from torch import nn
from torchvision import models, transforms
import cv2
from PIL import Image
import os
from tqdm import tqdm # For a beautiful terminal progress bar

# --- Configuration ---
# This engine will exclusively use your best model.
MODEL_PATH = 'ULTIMATE_CHAMPION_model.pth'
model = None # Global variable to hold the loaded model.

def load_model():
    """Loads the ULTIMATE Champion model into memory. Called once when the server starts."""
    global model
    if model is None:
        print(f"--- Loading ULTIMATE Champion Model: '{MODEL_PATH}' ---")
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model file not found! Please ensure '{MODEL_PATH}' is in your project directory.")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        model = models.efficientnet_b0(weights=None)
        num_ftrs = model.classifier[1].in_features
        model.classifier = nn.Sequential(nn.Dropout(p=0.2, inplace=True), nn.Linear(num_ftrs, 2))
        
        # Use weights_only=True for added security, as recommended by the warning.
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device, weights_only=True))
        model = model.to(device)
        model.eval()
        print("Model loaded successfully.\n")

def analyze_video(video_path: str):
    """
    The core analysis function. Analyzes EVERY frame of a video and returns its average fake confidence.
    """
    if model is None:
        raise RuntimeError("Model has not been loaded. Call load_model() first.")

    frames, err = _extract_all_frames(video_path)
    if err:
        return None, err

    data_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    total_fake_confidence = 0.0
    device = next(model.parameters()).device
    # For your fine-tuning dataset, classes were ['fake', 'real']. 'fake' is at index 0.
    fake_class_index = 0 

    # Show a progress bar in the server terminal during analysis.
    for frame in tqdm(frames, desc=f"Analyzing '{os.path.basename(video_path)}'", unit="frame", leave=False):
        image_tensor = data_transforms(frame).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model(image_tensor)
            probs = torch.nn.functional.softmax(outputs, dim=1)
            fake_confidence = probs[0][fake_class_index].item()
            total_fake_confidence += fake_confidence
    
    # Return the simple average score.
    return total_fake_confidence / len(frames) if frames else 0, None

def _extract_all_frames(video_path):
    """Private helper function to extract every single frame from a video."""
    frames = []
    try:
        cap = cv2.VideoCapture(video_path.strip('"'))
        if not cap.isOpened(): return [], "Error: Could not open video file."
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break # Reached the end of the video
            frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        cap.release()
        return frames, None
    except Exception as e:
        return [], f"Error during frame extraction: {e}"