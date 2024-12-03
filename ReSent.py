import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import create_engine
import json
import mysql.connector
from mysql.connector import Error

# Create SQLAlchemy engine for fetching data
engine = create_engine('mysql+mysqlconnector://root:12345678@localhost/restaurant_db')

# Function to fetch the latest reviews data, including ratings and sentiment
def fetch_reviews_data():
    query = """
    SELECT user_id, restaurant_id, rating, sentiment_id
    FROM reviews
    """
    df = pd.read_sql(query, con=engine)
    return df

# Function to preprocess the data and create a user-restaurant matrix
def preprocess_data(reviews_df):
    # Assign weights based on sentiment_id
    sentiment_weights = {
        1: 0.1,  # Negative sentiment, lower weight
        2: 0.5,    # Neutral sentiment, neutral weight
        3: 1   # Positive sentiment, higher weight
    }
    
    # Apply sentiment weight to ratings to create a weighted rating
    reviews_df['weighted_rating'] = reviews_df.apply(
        lambda row: row['rating'] * sentiment_weights.get(row['sentiment_id'], 1),
        axis=1
    )

    # Create a user-restaurant matrix using the weighted ratings as a feature
    user_restaurant_matrix = reviews_df.pivot_table(
        index="user_id", columns="restaurant_id", values="weighted_rating", aggfunc='mean', fill_value=0
    )
    return user_restaurant_matrix

# Function to dynamically calculate the similarity matrix with ratings and sentiment
# Function to dynamically calculate the similarity matrix with ratings and sentiment
def calculate_similarity():
    # Fetch the latest reviews data
    reviews_df = fetch_reviews_data()
    user_restaurant_matrix = preprocess_data(reviews_df)

    # Compute the similarity matrix
    similarity_matrix = cosine_similarity(user_restaurant_matrix)
    similarity_df = pd.DataFrame(similarity_matrix, index=user_restaurant_matrix.index, columns=user_restaurant_matrix.index)

    return user_restaurant_matrix, similarity_df, reviews_df  # Return reviews_df so it can be used later

# Function to update the review recommendations cache
def update_review_recommendations_cache(user_id, recommendations):
    if not recommendations:
        return

    try:
        # Connect to the database
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="12345678",
            database="restaurant_db"
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Convert the list of recommendations to JSON format
            recommendations_json = json.dumps(recommendations)

            # Upsert into the 'review_recommendations_cache' table
            cursor.execute(
                'INSERT INTO review_recommendations_cache (user_id, recommended_restaurants, last_updated) '
                'VALUES (%s, %s, CURRENT_TIMESTAMP) '
                'ON DUPLICATE KEY UPDATE recommended_restaurants = %s, last_updated = CURRENT_TIMESTAMP',
                (user_id, recommendations_json, recommendations_json)
            )
            connection.commit()
    except Error as e:
        print("Error updating review recommendations cache:", e)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_review_recommendations(user_id):
    # Recalculate the similarity data dynamically
    user_restaurant_matrix, similarity_df, reviews_df = calculate_similarity()

    # Check if user_id exists in similarity_df
    if user_id not in similarity_df.index:
        return {"message": "No similar users found."}

    # Get the similarity scores for the given user, excluding self-comparison
    similar_users = similarity_df[user_id].sort_values(ascending=False)

    if similar_users.empty:
        return {"message": "No similar users found."}

    # Exclude the user itself
    similar_users = similar_users.drop(user_id)

    if similar_users.empty:
        return {"message": "No other users found for comparison."}

    # Select the most similar user (the one with the highest similarity score)
    top_similar_user = similar_users.index[0]

    # Identify restaurant preferences for both users
    user_favorites = set(user_restaurant_matrix.loc[user_id][user_restaurant_matrix.loc[user_id] > 0].index)
    top_similar_user_favorites = set(user_restaurant_matrix.loc[top_similar_user][user_restaurant_matrix.loc[top_similar_user] > 0].index)

    # Recommend restaurants that the current user hasn't rated but the most similar user has
    recommendations = top_similar_user_favorites - user_favorites

    # Filter recommendations to include only those with positive ratings from the most similar user
    positive_recommendations = [
        restaurant for restaurant in recommendations
        if user_restaurant_matrix.loc[top_similar_user, restaurant] >= 3 and
        ((reviews_df['user_id'] == top_similar_user) & 
         (reviews_df['restaurant_id'] == restaurant) & 
         (reviews_df['sentiment_id'] == 3)).any()
    ]

    if not positive_recommendations:
        return {"message": "No new positive recommendations for you."}
    else:
        # Update the cache with the new recommendations
        update_review_recommendations_cache(user_id, positive_recommendations)
        return {"recommended_restaurants": positive_recommendations}
