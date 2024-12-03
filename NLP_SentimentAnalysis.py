import pandas as pd
import re
import joblib
import nltk
from flask import Flask, request, jsonify, render_template
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords

# Ensure nltk resources are downloaded
nltk.download('stopwords')

app = Flask(__name__)

# Preprocess function
def preprocess_text(text):
    lemmatizer = WordNetLemmatizer()
    text = re.sub(r'\W', ' ', text)  # Remove non-alphanumeric characters
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
    text = text.lower().strip()
    stop_words = set(stopwords.words('english'))
    text = ' '.join([lemmatizer.lemmatize(word) for word in text.split() if word not in stop_words])
    return text

# Function to identify neutral reviews
def is_neutral(review):
    neutral_keywords = ['but', 'however', 'although', 'neither', 'nor', 'it was okay', 'average', 'decent', 'not bad']
    review = review.lower()
    if any(keyword in review for keyword in neutral_keywords):
        return True
    return False

# Train and save the model if it hasn't been trained yet
def train_model():
    # Load the dataset
    df = pd.read_csv('NLP/Combined_Reviews.csv')
    df.columns = df.columns.str.strip()

    # Apply preprocessing to the reviews
    df['Review'] = df['Review'].apply(preprocess_text)

    # Prepare the features and labels
    X = df['Review']
    y = df['Liked']

    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Create a pipeline with TfidfVectorizer and SVM classifier
    pipeline = Pipeline([
        ('vectorizer', TfidfVectorizer(max_features=5000)),
        ('classifier', SVC(kernel='linear'))
    ])

    # Train the model
    pipeline.fit(X_train, y_train)

    # Save the trained model
    joblib.dump(pipeline, 'svm_sentiment_model.pkl')

    print("SVM model training complete and saved successfully.")

# Load the trained model if available
try:
    model = joblib.load('svm_sentiment_model.pkl')
except FileNotFoundError:
    print("Model not found. Training a new model...")
    train_model()
    model = joblib.load('svm_sentiment_model.pkl')

# Function to predict sentiment for a single input
def predict_sentiment(review):
    processed_review = preprocess_text(review)
    
    # Check if the review is neutral
    if is_neutral(review):
        return "Neutral"
    
    # Predict sentiment
    prediction = model.predict([processed_review])[0]
    return "Positive" if prediction == 1 else "Negative"
