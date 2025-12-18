import joblib
import pandas as pd
import os
from src.data.feature_extractor import FeatureExtractor
import numpy as np
from urllib.parse import urlparse # <<< FIX: Import urlparse to check the URL structure

# --- Configuration ---
MODEL_PATH = os.path.join('End-to-End-Malicious-URL-Detection_NReshwar', 'models', 'random_forest.pkl')
model = None

# --- This mapping remains correct ---
FEATURE_NAME_MAPPING = {
    'qty_dot_url': 'count_dot',
    'qty_hyphen_url': 'count_hyphen',
    # ... all other feature mappings
    'server_client_domain': 'server_client'
}

def load_model():
    """Loads the Malicious URL model."""
    global model
    if model is None:
        print(f"--- Loading Malicious URL Model ---")
        model = joblib.load(MODEL_PATH)
        print("Malicious URL model loaded successfully.")

def analyze_url(url_to_check):
    """Analyzes a URL and provides a prediction and score."""
    if model is None:
        raise RuntimeError("URL model has not been loaded.")
    
    try:
        extractor = FeatureExtractor(url_to_check)
        features_dict = extractor.extract_all_features()

        # --- FIX START: Sanitize features for root-level domains ---
        parsed_url = urlparse(url_to_check)
        if parsed_url.path in ('', '/'):
            # This is a root domain URL. The feature extractor might produce anomalous values
            # (like -1) for path-related features, which the model interprets as malicious.
            # We override them to 0 to represent "not applicable" neutrally.
            path_related_features = [
                'directory_length', 'qty_dot_directory', 'qty_hyphen_directory', 'qty_underline_directory',
                'qty_slash_directory', 'qty_questionmark_directory', 'qty_equal_directory', 'qty_at_directory',
                'qty_and_directory', 'qty_exclamation_directory', 'qty_space_directory', 'qty_tilde_directory',
                'qty_comma_directory', 'qty_plus_directory', 'qty_asterisk_directory', 'qty_hashtag_directory',
                'qty_dollar_directory', 'qty_percent_directory', 'filename_length', 'qty_dot_file',
                'qty_hyphen_file', 'qty_underline_file', 'qty_slash_file', 'qty_questionmark_file',
                'qty_equal_file', 'qty_at_file', 'qty_and_file', 'qty_exclamation_file', 'qty_space_file',
                'qty_tilde_file', 'qty_comma_file', 'qty_plus_file', 'qty_asterisk_file', 'qty_hashtag_file',
                'qty_dollar_file', 'qty_percent_file', 'qty_params', 'qty_dot_params', 'qty_hyphen_params',
                'qty_underline_params', 'qty_slash_params', 'qty_questionmark_params', 'qty_equal_params',
                'qty_at_params', 'qty_and_params', 'qty_exclamation_params', 'qty_space_params',
                'qty_tilde_params', 'qty_comma_params', 'qty_plus_params', 'qty_asterisk_params',
                'qty_hashtag_params', 'qty_dollar_params', 'qty_percent_params', 'params_length',
                'email_in_url' # Often tied to params
            ]
            # Rename the features in our list to match what the extractor produces
            extractor_path_features = [k for k, v in FEATURE_NAME_MAPPING.items() if v in path_related_features]
            
            for feature in extractor_path_features:
                 features_dict[feature] = 0
        # --- FIX END ---

        features_df = pd.DataFrame([features_dict])

        # Rename the columns using the precise mapping dictionary
        features_df.rename(columns=FEATURE_NAME_MAPPING, inplace=True)

        # Ensure all columns expected by the model are present, fill missing ones with 0
        for col in model.feature_names_in_:
            if col not in features_df.columns:
                features_df[col] = 0
        
        # Ensure the columns are in the exact order the model was trained on
        final_features_df = features_df[model.feature_names_in_]
        
        prediction_encoded = model.predict(final_features_df)
        prediction_proba = model.predict_proba(final_features_df)
        risk_score = round(prediction_proba[0][1] * 100)
        is_malicious = bool(prediction_encoded[0])
        
        return {
            "is_malicious": is_malicious, 
            "risk_score": risk_score
        }, None
    except Exception as e:
        # Provide a more specific error message back to the UI
        detailed_error = f"Feature extraction error: {e}. Model expects columns like {model.feature_names_in_[:3]}..."
        return None, detailed_error