import tensorflow as tf
from transformers import BertTokenizer
import os

# --- Configuration ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
TOKENIZER_PATH = os.path.join(project_root, "local_bert_tokenizer")
MODEL_PATH = os.path.join('email_phising_tejaswi', 'saved_model')
tokenizer = None
model = None

def load_model():
    """Loads the Email Phishing model and tokenizer into memory."""
    global tokenizer, model
    if model is None:
        print(f"--- Loading Email Phishing Model from: '{MODEL_PATH}' ---")
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError("Email phishing saved_model folder not found!")
        print(f"Loading tokenizer from absolute path: {TOKENIZER_PATH}")
        tokenizer = BertTokenizer.from_pretrained(TOKENIZER_PATH)
        model = tf.saved_model.load(MODEL_PATH)
        print("Email Phishing model loaded successfully.")

def analyze_email(email_text):
    """Analyzes a block of text to determine if it is phishing."""
    if model is None or tokenizer is None:
        raise RuntimeError("Email model has not been loaded. Call load_model() first.")
    
    encoded = tokenizer(email_text, truncation=True, padding="max_length", max_length=128, return_tensors="tf")
    inputs = {
        "input_ids": encoded["input_ids"],
        "attention_mask": encoded["attention_mask"]
    }
    input_keys = model.signatures["serving_default"].structured_input_signature[1].keys()
    if "token_type_ids" in input_keys:
        inputs["token_type_ids"] = encoded["token_type_ids"]
    output = model.signatures["serving_default"](**inputs)
    prediction = tf.argmax(output["logits"], axis=1).numpy()[0]
    is_phishing = bool(prediction)

    return {"is_phishing": is_phishing}, None