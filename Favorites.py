import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import logging
from sqlalchemy import create_engine
import json
import mysql.connector
from mysql.connector import Error

# Create SQLAlchemy engine for fetching data
engine = create_engine('mysql+mysqlconnector://root:12345678@localhost/restaurant_db')

# Function to fetch the latest favorites data
def fetch_favorites_data():
    query = "SELECT user_id, restaurant_id FROM favorites"
    df = pd.read_sql(query, con=engine)
    return df

# Function to dynamically calculate the similarity matrix
def calculate_similarity():
    # Fetch the latest favorites data
    favorites_df = fetch_favorites_data()

    # Create a user-restaurant matrix
    user_restaurant_matrix = favorites_df.pivot_table(
        index="user_id", columns="restaurant_id", aggfunc=lambda x: 1, fill_value=0
    )

    # Compute the similarity matrix
    similarity_matrix = cosine_similarity(user_restaurant_matrix)
    similarity_df = pd.DataFrame(similarity_matrix, index=user_restaurant_matrix.index, columns=user_restaurant_matrix.index)

    return user_restaurant_matrix, similarity_df

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Function to update the recommendations cache
def update_recommendations_cache(user_id, recommendations):
    if not recommendations:
        logging.debug(f"No recommendations to update for User {user_id}.")
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

            # Upsert into the 'recommendations_cache' table
            cursor.execute(
                'INSERT INTO recommendations_cache (user_id, recommended_restaurants, last_updated) '
                'VALUES (%s, %s, CURRENT_TIMESTAMP) '
                'ON DUPLICATE KEY UPDATE recommended_restaurants = %s, last_updated = CURRENT_TIMESTAMP',
                (user_id, recommendations_json, recommendations_json)
            )
            connection.commit()

            logging.debug(f"Recommendations cache updated for User {user_id}.")
    except Error as e:
        logging.error("Error updating recommendations cache:", e)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logging.debug("MySQL connection is closed")

# Function to get recommendations for a specific user
def get_recommendations(user_id):
    logging.debug(f"Getting recommendations for user ID: {user_id}")

    # Recalculate the similarity data dynamically
    user_restaurant_matrix, similarity_df = calculate_similarity()

    # Check if user_id exists in similarity_df
    if user_id not in similarity_df.columns:
        logging.debug("User ID not found in similarity_df.")
        return {"message": "No similar users found."}

    # Get the similarity scores for the given user, excluding self-comparison
    similar_users = similarity_df[user_id].sort_values(ascending=False)

    if similar_users.empty:
        logging.debug("No similar users found.")
        return {"message": "No similar users found."}

    # Exclude the user itself
    similar_users = similar_users.drop(user_id)

    if similar_users.empty:
        logging.debug("No other users found for comparison.")
        return {"message": "No other users found for comparison."}

    # Get the most similar user
    top_similar_user = similar_users.index[0]
    logging.debug(f"Most similar user: {top_similar_user}")

    # Identify favorite restaurants for both users
    user_favorites = set(user_restaurant_matrix.loc[user_id][user_restaurant_matrix.loc[user_id] == 1].index)
    top_similar_user_favorites = set(user_restaurant_matrix.loc[top_similar_user][user_restaurant_matrix.loc[top_similar_user] == 1].index)

    logging.debug(f"User {user_id} favorites: {user_favorites}")
    logging.debug(f"Top similar user {top_similar_user} favorites: {top_similar_user_favorites}")

    # Recommend restaurants that the current user hasn't favorited but the most similar user has
    recommendations = top_similar_user_favorites - user_favorites

    if not recommendations:
        logging.debug(f"No new recommendations for you")
        return {"message": f"No new recommendations for you."}
    else:
        logging.debug(f"Recommendations for User {user_id}: {list(recommendations)}")
        return {"recommended_restaurants": list(recommendations)}
