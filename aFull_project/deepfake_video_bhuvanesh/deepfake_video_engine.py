import torch
from torch import nn
from torchvision import models, transforms
import cv2
from PIL import Image
import os
import numpy as np
import random
import base64
import io
import ffmpeg
import sys

sys.path.append(os.path.abspath('deepfake_audio_model_rangnath'))
from deepfake_audio_engine import analyze_audio

MODEL_PATH = os.path.join('deepfake_video_bhuvanesh', 'ULTIMATE_CHAMPION_model.pth')
PROTOTXT_PATH = os.path.join(os.path.dirname(__file__), '..', 'face_detector', 'deploy.prototxt.txt')
WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'face_detector', 'res10_300x300_ssd_iter_140000.caffemodel')

model = None
face_net = None

def load_model():
    global model, face_net
    if model is None:
        print("--- Loading Deepfake Video/Image Model ---")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = models.efficientnet_b0(weights=None)
        num_ftrs = model.classifier[1].in_features
        model.classifier = nn.Sequential(nn.Dropout(p=0.2, inplace=True), nn.Linear(num_ftrs, 2))
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        model = model.to(device)
        model.eval()
        print("Deepfake Video/Image model loaded successfully.")

    if face_net is None:
        print("--- Loading Face Detection Model ---")
        if not os.path.exists(PROTOTXT_PATH) or not os.path.exists(WEIGHTS_PATH):
            raise FileNotFoundError("Face detector model files not found!")
        face_net = cv2.dnn.readNet(PROTOTXT_PATH, WEIGHTS_PATH)
        print("Face Detection model loaded successfully.")

def _extract_audio(video_path):
    temp_audio_path = f"{video_path}.wav"
    try:
        (ffmpeg.input(video_path).output(temp_audio_path, acodec='pcm_s16le', ac=1, ar='16000').run(overwrite_output=True, quiet=True))
        return temp_audio_path
    except ffmpeg.Error as e:
        print(f"FFmpeg info: Could not extract audio. Stderr: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during audio extraction: {e}")
        return None

def analyze_image(image_path: str):
    if model is None or face_net is None:
        raise RuntimeError("Models not loaded. Call load_model() first.")
    try:
        image = Image.open(image_path).convert('RGB')
    except Exception as e:
        return None, f"Error opening image file: {e}"

    data_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    device = next(model.parameters()).device
    fake_class_index = 0

    image_tensor = data_transforms(image).unsqueeze(0).to(device)
    with torch.no_grad():
        outputs = model(image_tensor)
        probs = torch.nn.functional.softmax(outputs, dim=1)
        fake_confidence = probs[0][fake_class_index].item()
    
    result_image_b64 = _draw_bounding_box([image], fake_confidence)
    return {
        "average_confidence": fake_confidence,
        "result_image": result_image_b64
    }, None

def analyze_video(video_path: str):
    if model is None or face_net is None:
        yield {"type": "error", "message": "Video/Face models not loaded."}
        return

    yield {'type': 'progress', 'message': f"Extracting audio from {os.path.basename(video_path)}..."}
    audio_result_data = {}
    temp_audio_file = _extract_audio(video_path)
    if temp_audio_file:
        yield {'type': 'progress', 'message': 'Audio extracted successfully.'}
        try:
            audio_result, err = analyze_audio(temp_audio_file)
            if not err:
                audio_result_data = {
                    "audio_verdict": "FAKE" if audio_result['prediction'] == 0 else "REAL",
                    "audio_confidence": audio_result.get('confidence', 0.0)
                }
            else:
                audio_result_data = {"audio_verdict": "Analysis Error", "audio_confidence": 0}
        finally:
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
    else:
        yield {'type': 'progress', 'message': 'No audio track found or extraction failed.'}
        audio_result_data = {"audio_verdict": "No Audio Track", "audio_confidence": 0}

    frames, err, message = _extract_all_frames(video_path)
    if message:
        yield {'type': 'progress', 'message': message}
    if err:
        yield {"type": "error", "message": err}
        return
    total_frames = len(frames)
    if total_frames == 0:
        yield {"type": "error", "message": "No frames could be extracted from the video."}
        return

    yield {"type": "progress", "processed": 0, "total": total_frames, "message": "Detecting faces in frames..."}
    
    data_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    device = next(model.parameters()).device
    fake_class_index = 0 
    frame_by_frame_scores = []
    frames_with_faces = []

    for i, frame in enumerate(frames):
        frame_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
        (h, w) = frame_cv.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame_cv, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        face_net.setInput(blob)
        detections = face_net.forward()

        has_face = False
        for j in range(0, detections.shape[2]):
            confidence = detections[0, 0, j, 2]
            if confidence > 0.5:
                has_face = True
                break
        
        if has_face:
            frames_with_faces.append(frame)
            image_tensor = data_transforms(frame).unsqueeze(0).to(device)
            with torch.no_grad():
                outputs = model(image_tensor)
                probs = torch.nn.functional.softmax(outputs, dim=1)
                fake_confidence = probs[0][fake_class_index].item()
                frame_by_frame_scores.append(fake_confidence)

        if (i + 1) % (max(1, total_frames // 10)) == 0 or i == total_frames - 1:
            yield {"type": "progress", "processed": i + 1, "total": total_frames, "message": f"Analyzed {len(frame_by_frame_scores)} frames with faces..."}

    if not frame_by_frame_scores:
        yield {
            "type": "result",
            "verdict": "REAL",
            "average_confidence": 0.0,
            "frame_scores": [],
            "result_image": None,
            "message": "No faces were detected in the video, cannot perform deepfake analysis.",
            **audio_result_data
        }
        return

    average_confidence = sum(frame_by_frame_scores) / len(frame_by_frame_scores)
    std_dev_confidence = np.std(frame_by_frame_scores) if len(frame_by_frame_scores) > 1 else 0
    
    SUSPICIOUS_THRESHOLD = 0.75
    VERDICT_THRESHOLD_PERCENTAGE = 0.30
    suspicious_frame_count = sum(1 for score in frame_by_frame_scores if score > SUSPICIOUS_THRESHOLD)
    percentage_suspicious = suspicious_frame_count / len(frame_by_frame_scores)
    is_fake = percentage_suspicious > VERDICT_THRESHOLD_PERCENTAGE

    if not is_fake and average_confidence > 0.70:
        is_fake = True
        
    HIGH_STD_DEV_THRESHOLD = 0.30
    if is_fake and std_dev_confidence > HIGH_STD_DEV_THRESHOLD:
        if average_confidence < 0.65:
            is_fake = False

    verdict = "FAKE" if is_fake else "REAL"
    result_image_b64 = _draw_bounding_box(frames_with_faces, average_confidence)

    yield {
        "type": "result",
        "verdict": verdict,
        "average_confidence": average_confidence,
        "frame_scores": frame_by_frame_scores,
        "result_image": result_image_b64,
        **audio_result_data
    }

def _draw_bounding_box(frames, score):
    if not frames: return None
    frame_to_process = random.choice(frames[len(frames)//4 : -len(frames)//4]) if len(frames) > 10 else random.choice(frames)
    frame_cv = cv2.cvtColor(np.array(frame_to_process), cv2.COLOR_RGB2BGR)
    (h, w) = frame_cv.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame_cv, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
    face_net.setInput(blob)
    detections = face_net.forward()

    is_fake = score > 0.5
    label = f"{('FAKE' if is_fake else 'REAL')}: {score:.2%}"
    color = (0, 0, 255) if is_fake else (0, 255, 0)

    for i in range(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            
            (startX, startY) = (max(0, startX), max(0, startY))
            (endX, endY) = (min(w - 1, endX), min(h - 1, endY))

            cv2.rectangle(frame_cv, (startX, startY), (endX, endY), color, 2)
            y = startY - 10 if startY - 10 > 10 else startY + 20
            cv2.putText(frame_cv, label, (startX, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    final_image_pil = Image.fromarray(cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB))
    buffered = io.BytesIO()
    final_image_pil.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def _extract_all_frames(video_path):
    frames = []
    cap = None
    message = ""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return [], "Error: Could not open video file.", None

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames_in_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if fps == 0 or total_frames_in_video == 0:
            return [], "Error: Could not determine video FPS or frame count.", None

        duration = total_frames_in_video / fps
        
        FRAMES_PER_SECOND_TO_SAMPLE = 5
        MAX_TOTAL_FRAMES = 500

        estimated_frames_to_process = int(duration * FRAMES_PER_SECOND_TO_SAMPLE)
        num_frames_to_extract = min(MAX_TOTAL_FRAMES, estimated_frames_to_process)

        if total_frames_in_video <= num_frames_to_extract:
            indices_to_extract = list(range(total_frames_in_video))
            message = f"Video is short ({duration:.2f}s). Processing all {total_frames_in_video} frames."
        else:
            all_indices = list(range(total_frames_in_video))
            randomly_selected_indices = random.sample(all_indices, num_frames_to_extract)
            indices_to_extract = sorted(randomly_selected_indices)
            message = f"Video is {duration:.2f}s long. Subsampling {num_frames_to_extract} random frames."

        for frame_index in indices_to_extract:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = cap.read()
            if ret:
                frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            else:
                print(f"Warning: Could not read frame at index {frame_index}.")
        
        return frames, None, message

    except Exception as e:
        return [], f"Error during frame extraction: {e}", None
    finally:
        if cap is not None and cap.isOpened():
            cap.release()