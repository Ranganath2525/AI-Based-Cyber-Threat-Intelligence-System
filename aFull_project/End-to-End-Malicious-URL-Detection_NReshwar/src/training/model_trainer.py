# src/training/model_trainer.py

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import LabelEncoder
import joblib # For saving models
import os
import sys

# Add the project root to the Python path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.data.feature_extractor import FeatureExtractor

class ModelTrainer:
    def __init__(self, data_path, model_dir='models/'):
        self.data_path = data_path
        self.model_dir = model_dir
        self.df = None
        self.X_train, self.X_test, self.y_train, self.y_test = None, None, None, None
        
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)

    def load_and_preprocess_data(self):
        print("Loading and preprocessing data...")
        self.df = pd.read_csv(self.data_path)

        # --- MODIFICATION START ---
        # Drop rows where 'url' or 'type' column is empty/NaN
        self.df.dropna(subset=['url', 'type'], inplace=True)
        print(f"Loaded {len(self.df)} rows after dropping empty entries.")

        # Extract features for each URL
        features_list = []
        # Keep track of the original indices that are valid
        valid_indices = [] 

        for index, row in self.df.iterrows():
            url = row['url']
            try:
                # Ensure the url is a string before processing
                if not isinstance(url, str):
                    raise ValueError("URL is not a string.")

                extractor = FeatureExtractor(url)
                features_list.append(extractor.extract_all_features())
                valid_indices.append(index) # Keep this index because it's valid
            except ValueError as e:
                # This will catch the error you saw and any other parsing errors
                print(f"Skipping invalid URL at index {index}: '{url}' | Error: {e}")

        # Create a DataFrame from the successfully extracted features
        features_df = pd.DataFrame(features_list)
        
        # VERY IMPORTANT: Filter the original DataFrame to only include the valid rows
        # This ensures that features and labels align perfectly
        self.df = self.df.loc[valid_indices].reset_index(drop=True)
        
        # Combine the aligned features with the filtered dataframe
        self.df = pd.concat([self.df, features_df], axis=1)
        # --- MODIFICATION END ---
        
        # Encode the labels ('benign' -> 0, 'malicious' -> 1)
        le = LabelEncoder()
        self.df['label_encoded'] = le.fit_transform(self.df['type']) 
        
        # Define features (X) and target (y)
        # Ensure 'url', 'type', 'label_encoded' are dropped, plus any other non-feature columns
        X = self.df.drop(columns=['url', 'type', 'label_encoded'])
        y = self.df['label_encoded']
        
        # Split data into training and testing sets
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        print("Data preprocessing complete.")

    def train_and_evaluate(self, model, model_name):
        print(f"--- Training {model_name} ---")
        model.fit(self.X_train, self.y_train)
        
        # Evaluate the model
        y_pred = model.predict(self.X_test)
        accuracy = accuracy_score(self.y_test, y_pred)
        precision = precision_score(self.y_test, y_pred)
        recall = recall_score(self.y_test, y_pred)
        f1 = f1_score(self.y_test, y_pred)
        
        print(f"Accuracy: {accuracy:.4f}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall: {recall:.4f}")
        print(f"F1-Score: {f1:.4f}\n")
        
        # Save the trained model
        model_path = os.path.join(self.model_dir, f'{model_name}.pkl')
        joblib.dump(model, model_path)
        print(f"Model saved to {model_path}")
        
        return {'accuracy': accuracy, 'precision': precision, 'recall': recall, 'f1': f1}

    def train_all_models(self):
        if self.df is None:
            self.load_and_preprocess_data()
            
        models = {
            'decision_tree': DecisionTreeClassifier(random_state=42),
            'random_forest': RandomForestClassifier(random_state=42, n_estimators=100),
            'svm': SVC(kernel='rbf', random_state=42)
        }
        
        results = {}
        for name, model in models.items():
            results[name] = self.train_and_evaluate(model, name)
            
        return results

# Example of how to run the training process
if __name__ == '__main__':
    # Make sure you have a 'data' directory at the root of your project
    # and your dataset is named 'url_dataset.csv'
    dataset_path = 'data/url_dataset.csv' 
    trainer = ModelTrainer(data_path=dataset_path)
    training_results = trainer.train_all_models()
    
    print("\n--- All Model Training Results ---")
    print(pd.DataFrame(training_results).T)