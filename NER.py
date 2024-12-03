from flask import Flask, render_template, request, jsonify
import spacy
import mysql.connector
from mysql.connector import Error

# Initialize Flask app
app = Flask(__name__)

# Load the pre-trained spaCy model
nlp = spacy.load('en_core_web_sm')

# Function to connect to your database
def get_restaurant_db_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='12345678',
            database='restaurant_db'
        )
        return connection
    except Error as e:
        print("Error connecting to the database:", e)
        return None

# Function to fetch CUISINE, CATEGORY, and MENU data
def fetch_cuisine_category_and_menu():
    connection = get_restaurant_db_connection()
    if not connection:
        return [], [], []

    cursor = connection.cursor()

    try:
        # Fetch cuisine names
        cursor.execute("SELECT cuisinename FROM cuisine")
        cuisines = [row[0].lower() for row in cursor.fetchall()]

        # Fetch category names
        cursor.execute("SELECT name FROM category")
        categories = [row[0].lower() for row in cursor.fetchall()]

        # Fetch menu item names
        cursor.execute("SELECT name FROM menu")
        menu_items = [row[0].lower() for row in cursor.fetchall()]

    except Error as e:
        print("Error fetching data:", e)
        cuisines, categories, menu_items = [], [], []

    finally:
        cursor.close()
        connection.close()

    return cuisines, categories, menu_items

# Function to extract food and cuisine entities from input text
def extract_food_entities(input_text):
    cuisines, categories, menu_items = fetch_cuisine_category_and_menu()
    doc = nlp(input_text.lower())

    food_entities = []
    cuisine_entities = []
    menu_entities = []
    for token in doc:
        if token.text in cuisines:
            cuisine_entities.append(token.text)
        if token.text in categories:
            food_entities.append(token.text)
        if token.text in menu_items:
            menu_entities.append(token.text)

    return {
        "food_items": food_entities,
        "cuisine_items": cuisine_entities,
        "menu_items": menu_entities
    }

# Function to search for restaurants based on extracted entities
def search_restaurants(input_text):
    extracted_data = extract_food_entities(input_text)
    food_items = extracted_data["food_items"]
    cuisine_items = extracted_data["cuisine_items"]
    menu_items = extracted_data["menu_items"]

    connection = get_restaurant_db_connection()
    if not connection:
        return []

    cursor = connection.cursor()

    query = '''
        SELECT DISTINCT r.id, r.name, r.image_path
        FROM restaurant r
        JOIN cuisine c ON r.cuisine_id = c.id
        JOIN menu m ON r.id = m.restaurant_id
        JOIN category cat ON m.category_id = cat.id
        WHERE 
    '''

    conditions = []
    if cuisine_items:
        placeholders = ', '.join(['%s'] * len(cuisine_items))
        conditions.append(f"LOWER(c.cuisinename) IN ({placeholders})")
    if food_items:
        placeholders = ', '.join(['%s'] * len(food_items))
        conditions.append(f"LOWER(cat.name) IN ({placeholders})")
    if menu_items:
        placeholders = ', '.join(['%s'] * len(menu_items))
        conditions.append(f"LOWER(m.name) IN ({placeholders})")

    if conditions:
        query += " AND ".join(conditions)
    else:
        query += "1"  # No specific criteria, fetch all restaurants

    values = cuisine_items + food_items + menu_items

    try:
        cursor.execute(query, values)
        results = cursor.fetchall()
    except Error as e:
        print("Error executing query:", e)
        results = []

    finally:
        cursor.close()
        connection.close()

    return [{"id": result[0], "name": result[1], "image_path": result[2]} for result in results]


