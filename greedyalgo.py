# database_utils.py
import pymysql

# Database configuration
restaurant_db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345678',
    'database': 'restaurant_db'
}

def get_restaurant_db_connection():
    """Establish and return a connection to the restaurant database."""
    return pymysql.connect(**restaurant_db_config, cursorclass=pymysql.cursors.DictCursor)

def fetch_top_restaurants(top_n=5):
    """
    Retrieve the top-N most highly rated restaurants from the database.

    Args:
    top_n (int): Number of top restaurants to retrieve.

    Returns:
    list: List of dictionaries containing restaurant details and their average ratings.
    """
    try:
        connection = get_restaurant_db_connection()
        cursor = connection.cursor()

        # SQL query to get average ratings for each restaurant and order by average rating
        query = """
        SELECT 
            r.id AS restaurant_id,
            r.name,
            r.image_path,
            AVG(rv.rating) AS average_rating
        FROM restaurant r
        JOIN reviews rv ON r.id = rv.restaurant_id
        GROUP BY r.id, r.name, r.image_path
        ORDER BY average_rating DESC
        LIMIT %s;
        """
        cursor.execute(query, (top_n,))
        results = cursor.fetchall()

        # Debugging: Print the fetched results
        print("Top-rated restaurants fetched:", results)

        return results

    except pymysql.MySQLError as err:
        print(f"Error: {err}")
        return []

    finally:
        if connection:
            cursor.close()
            connection.close()
