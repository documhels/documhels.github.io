from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from DivideandConquer import merge_sort
from NLP_SentimentAnalysis import preprocess_text, is_neutral, predict_sentiment
from NER import search_restaurants
from Favorites import get_recommendations, update_recommendations_cache
from ReSent import get_review_recommendations, update_review_recommendations_cache
from greedyalgo import fetch_top_restaurants, get_restaurant_db_connection 




app = Flask(__name__)


# Database Configuration for Restaurants
restaurant_db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345678',  
    'database': 'restaurant_db'  
}

app.secret_key = 'your_secret_key'

def get_restaurant_db_connection():
    connection = pymysql.connect(**restaurant_db_config)
    return connection

@app.route('/RL_page', methods=['GET', 'POST'])
def RL_page():
    email_error = None
    login_error = None

    if request.method == 'POST':
        action = request.form['action']

        if action == 'register':
            # Handle registration
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']

            # Check if the email already exists
            connection = get_restaurant_db_connection()
            cursor = connection.cursor()
            cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                email_error = 'Email is already registered.'
                connection.close()
                return render_template('RL_page.html', email_error=email_error, login_error=login_error)

            # Insert the new user with plaintext password (not recommended in production)
            cursor.execute('INSERT INTO users (name, email, password) VALUES (%s, %s, %s)', (name, email, password))
            connection.commit()
            connection.close()

            flash('Account created successfully. Please login!', 'success')
            return redirect(url_for('RL_page'))

        elif action == 'login':
            # Handle login
            email = request.form['email']
            password = request.form['password']

            connection = get_restaurant_db_connection()
            cursor = connection.cursor()
            cursor.execute('SELECT id, name, password FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            connection.close()

            if user and user[2] == password:  # Check plaintext password (for demo purposes)
                # Store user session data
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                login_error = 'Wrong password.'
                return render_template('RL_page.html', email_error=email_error, login_error=login_error)

    return render_template('RL_page.html', email_error=email_error, login_error=login_error)


@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('RL_page'))

    # Check if the user is logged in
    if 'user_id' in session:
        connection = get_restaurant_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT name FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        user_name = user[0] if user else None
        connection.close()
    else:
        user_name = None

    # Fetch the top-rated restaurants
    top_restaurants = fetch_top_restaurants(top_n=5)

    return render_template('home.html', user_name=user_name, top_restaurants=top_restaurants)

@app.route('/restaurants', methods=['GET', 'POST', 'DELETE'])
def restaurant():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'Guest')
    sort_choice = request.args.get('sort', 'none')  # Default to 'none' if no sort option is selected

    if request.method == 'POST':  # Add to favorites
        restaurant_id = request.json.get('restaurant_id')
        if user_id:
            connection = get_restaurant_db_connection()
            cursor = connection.cursor()
            query_check = '''
                SELECT 1 
                FROM favorites 
                WHERE user_id = %s AND restaurant_id = %s
            '''
            cursor.execute(query_check, (user_id, restaurant_id))
            already_favorite = cursor.fetchone()

            if not already_favorite:
                query_insert = '''
                    INSERT INTO favorites (user_id, restaurant_id)
                    VALUES (%s, %s)
                '''
                cursor.execute(query_insert, (user_id, restaurant_id))
                connection.commit()
                return jsonify({'message': 'Added to favorites'}), 200
            else:
                return jsonify({'message': 'Already a favorite'}), 400
        return jsonify({'error': 'User not logged in'}), 401

    elif request.method == 'DELETE':  # Remove from favorites
        restaurant_id = request.json.get('restaurant_id')
        if user_id:
            connection = get_restaurant_db_connection()
            cursor = connection.cursor()
            query = '''
                DELETE FROM favorites 
                WHERE user_id = %s AND restaurant_id = %s
            '''
            cursor.execute(query, (user_id, restaurant_id))
            connection.commit()
            return jsonify({'message': 'Removed from favorites'}), 200
        return jsonify({'error': 'User not logged in'}), 401

    else:  # GET request: Fetch restaurants, their favorite status, and sorted by average price
        query = '''
            SELECT 
                r.id, 
                r.name, 
                r.image_path, 
                EXISTS (
                    SELECT 1 
                    FROM favorites f 
                    WHERE f.user_id = %s AND f.restaurant_id = r.id
                ) AS is_favorite, 
                COALESCE(ra.avg_price, 0) AS avg_price
            FROM restaurant r
            LEFT JOIN restaurant_avg_prices ra ON r.id = ra.restaurant_id
        '''

        connection = get_restaurant_db_connection()
        cursor = connection.cursor()

        try:
            if user_id:
                cursor.execute(query, (user_id,))
            else:
                query_no_user = query.replace(
                    "EXISTS (SELECT 1 FROM favorites f WHERE f.user_id = %s AND f.restaurant_id = r.id)", 
                    "FALSE AS is_favorite"
                )
                cursor.execute(query_no_user)

            restaurants = cursor.fetchall()
        except Exception as e:
            print(f"Error fetching restaurants: {e}")
            restaurants = []

        connection.close()

        # Sort the fetched data based on avg_price if the sort choice is valid
        if sort_choice in ['asc', 'desc']:
            reverse = True if sort_choice == 'desc' else False
            # Sorting the data using the merge_sort utility function
            restaurants = merge_sort(restaurants, key=4, reverse=reverse)

        return render_template(
            'restaurants.html',
            user_name=user_name,
            restaurants=restaurants,
            sort_choice=sort_choice  # Pass the selected sort choice to the template
        )

@app.route('/menu/<int:restaurant_id>')
def menu(restaurant_id):
    # Check if the user is logged in
    if 'user_id' in session:
        user_name = session['user_name']
    else:
        user_name = None
        
    connection = get_restaurant_db_connection()
    cursor = connection.cursor()

    # Fetch restaurant name
    cursor.execute('SELECT name FROM restaurant WHERE id = %s', (restaurant_id,))
    restaurant = cursor.fetchone()
    
    if not restaurant:
        return "Restaurant not found", 404

    # Fetch menu items with their category names
    cursor.execute('''
        SELECT m.id, m.name, m.price, m.category_id, c.name
        FROM menu m
        JOIN category c ON m.category_id = c.id
        WHERE m.restaurant_id = %s
        ORDER BY c.name, m.price
    ''', (restaurant_id,))
    menu_items = cursor.fetchall()

    # Group menu items by category
    categories = {}
    for item in menu_items:
        category_name = item[4]  # category name from the 'category' table
        if category_name not in categories:
            categories[category_name] = []
        categories[category_name].append(item)

    connection.close()
    
    return render_template('menu.html', restaurant=restaurant, categories=categories, user_name=user_name, restaurant_id=restaurant_id)


@app.route('/review/<int:restaurant_id>', methods=['GET', 'POST'])
def review(restaurant_id):
    # Check if the user is logged in
    user_name = session.get('user_name')
    user_id = session.get('user_id')

    connection = get_restaurant_db_connection()
    if not connection:
        return "Error connecting to the database", 500

    cursor = connection.cursor()

    # Fetch the restaurant name using restaurant_id
    cursor.execute('SELECT name FROM restaurant WHERE id = %s', (restaurant_id,))
    restaurant = cursor.fetchone()

    if not restaurant:
        connection.close()
        return "Restaurant not found", 404

    restaurant_name = restaurant[0]

    # Handle review submission
    if request.method == 'POST':
        rating = request.form.get('rating')
        review_text = request.form.get('review_text')

        if not rating or not review_text:
            connection.close()
            return "Rating and review text are required", 400

        # Predict the sentiment of the review
        sentiment = predict_sentiment(review_text)

        # Get the sentiment ID from the sentiments table
        cursor.execute('SELECT id FROM sentiments WHERE sentiment = %s', (sentiment,))
        sentiment_id = cursor.fetchone()

        if not sentiment_id:
            connection.close()
            return "Sentiment not found", 404

        # Check if the user has already reviewed this restaurant
        cursor.execute('SELECT id FROM reviews WHERE user_id = %s AND restaurant_id = %s', (user_id, restaurant_id))
        existing_review = cursor.fetchone()

        if existing_review:
            # Update the existing review
            cursor.execute('''
                UPDATE reviews
                SET rating = %s, review_text = %s, sentiment_id = %s, updated_at = NOW()
                WHERE id = %s
            ''', (rating, review_text, sentiment_id[0], existing_review[0]))
        else:
            # Insert a new review
            cursor.execute('''
                INSERT INTO reviews (user_id, restaurant_id, rating, review_text, sentiment_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ''', (user_id, restaurant_id, rating, review_text, sentiment_id[0]))

        connection.commit()

    # Handle sorting
    sort_type = request.args.get('sort', 'all').lower()
    if sort_type == 'positive':
        sentiment_condition = "s.sentiment = 'Positive'"
    elif sort_type == 'neutral':
        sentiment_condition = "s.sentiment = 'Neutral'"
    elif sort_type == 'negative':
        sentiment_condition = "s.sentiment = 'Negative'"
    else:
        sentiment_condition = "1=1"  # No filter, show all reviews

    # Fetch existing reviews for display based on sentiment filter
    cursor.execute(f'''
        SELECT r.name AS user_name, rr.rating, rr.review_text, s.sentiment
        FROM reviews rr
        JOIN users r ON rr.user_id = r.id
        JOIN sentiments s ON rr.sentiment_id = s.id
        WHERE rr.restaurant_id = %s AND {sentiment_condition}
    ''', (restaurant_id,))
    reviews = cursor.fetchall()

    connection.close()

    # Pass restaurant_name, restaurant_id, user_name, and reviews to the template
    return render_template('review.html', restaurant_name=restaurant_name, user_name=user_name, restaurant_id=restaurant_id, reviews=reviews, sort_type=sort_type)

@app.route('/favorites', methods=['GET', 'DELETE'])
def favorites():
    # Get the user ID from the session
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'Guest')

    # If the user is not logged in, redirect to login page
    if not user_id:
        return redirect(url_for('login'))  # Assuming you have a login route

    if request.method == 'DELETE':  # Handle DELETE request to remove from favorites
        # Get the restaurant ID from the request JSON
        restaurant_id = request.json.get('restaurant_id')
        
        if user_id and restaurant_id:
            # Connect to the database
            connection = get_restaurant_db_connection()
            cursor = connection.cursor()

            try:
                # Delete the restaurant from the user's favorites
                query = '''
                    DELETE FROM favorites 
                    WHERE user_id = %s AND restaurant_id = %s
                '''
                cursor.execute(query, (user_id, restaurant_id))
                connection.commit()
                response = {'message': 'Removed from favorites'}
            except Exception as e:
                print(f"Error removing favorite: {e}")
                response = {'error': 'Failed to remove favorite'}
            finally:
                connection.close()

            return jsonify(response)

    # If GET request, fetch the user's favorite restaurants
    query = '''
        SELECT 
            r.id, 
            r.name, 
            r.image_path
        FROM restaurant r
        JOIN favorites f ON f.restaurant_id = r.id
        WHERE f.user_id = %s
    '''

    # Connect to the database and fetch the data
    connection = get_restaurant_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(query, (user_id,))
        favorites = cursor.fetchall()
    except Exception as e:
        # Handle database connection or query errors
        print(f"Error fetching favorites: {e}")
        favorites = []
    finally:
        connection.close()

    # If no favorites are found, you can return a message or an empty list
    if not favorites:
        flash('You have no favorite restaurants.', 'info')

    # Render the favorites page and pass the user and favorite restaurants data
    return render_template('favorites.html', user_name=user_name, favorites=favorites)

@app.route('/recommendation')
def recommendation():
    if 'user_id' not in session:
        return redirect(url_for('RL_page'))  # Redirect to login if not logged in

    # Fetch user data
    connection = get_restaurant_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT name FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()
    user_name = user[0] if user else None

    if not user_name:
        return render_template('recommendation.html', user_name=None, message="User not found.")

    # Fetch recommendations from favorites
    favorites_recommendations = get_recommendations(session['user_id'])
    if 'recommended_restaurants' in favorites_recommendations:
        restaurant_ids = favorites_recommendations['recommended_restaurants']
        update_recommendations_cache(session['user_id'], restaurant_ids)

        # Fetch restaurant details for recommended restaurants from favorites
        cursor.execute(
            'SELECT id, name, image_path FROM restaurant WHERE id IN (%s)' % ','.join(['%s'] * len(restaurant_ids)),
            tuple(restaurant_ids)
        )
        recommended_favorites_restaurants = cursor.fetchall()
        favorites_message = None if recommended_favorites_restaurants else "No recommended restaurants available from favorites."
    else:
        recommended_favorites_restaurants = []
        favorites_message = favorites_recommendations.get("message", "No recommendations available from favorites.")

    # Fetch recommendations from reviews
    reviews_recommendations = get_review_recommendations(session['user_id'])
    if 'recommended_restaurants' in reviews_recommendations:
        restaurant_ids = reviews_recommendations['recommended_restaurants']
        update_review_recommendations_cache(session['user_id'], restaurant_ids)

        # Fetch restaurant details for recommended restaurants from reviews
        cursor.execute(
            'SELECT id, name, image_path FROM restaurant WHERE id IN (%s)' % ','.join(['%s'] * len(restaurant_ids)),
            tuple(restaurant_ids)
        )
        recommended_reviews_restaurants = cursor.fetchall()
        reviews_message = None if recommended_reviews_restaurants else "No recommended restaurants available from reviews."
    else:
        recommended_reviews_restaurants = []
        reviews_message = reviews_recommendations.get("message", "No recommendations available from reviews.")

    connection.close()

    return render_template(
        'recommendation.html',
        user_name=user_name,
        recommended_favorites_restaurants=recommended_favorites_restaurants,
        recommended_reviews_restaurants=recommended_reviews_restaurants,
        favorites_message=favorites_message,
        reviews_message=reviews_message
    )



@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('RL_page'))

    # Check if the user is logged in
    if 'user_id' in session:
        connection = get_restaurant_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT name FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        user_name = user[0] if user else None
        connection.close()
    else:
        user_name = None

    # If the request method is POST, search for restaurants based on input
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            # Call the search function to get results
            restaurants = search_restaurants(query)
            return jsonify(restaurants)

    # If the request method is GET or no search input, display the search page without results
    # Fetch the search results if any query parameter is passed
    query = request.args.get('query', '').strip()
    restaurants = []
    if query:
        restaurants = search_restaurants(query)

    return render_template('search.html', user_name=user_name, restaurants=restaurants, query=query)




@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user session data
    session.pop('user_name', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('RL_page'))  # Redirect to the RL_page (login/logout page)


if __name__ == '__main__':
    app.run(debug=True)