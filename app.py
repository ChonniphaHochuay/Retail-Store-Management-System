from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from werkzeug.utils import secure_filename
from datetime import datetime as dt

app = Flask(__name__, static_folder='static')
app.secret_key = 'supersecretkey'  # Needed to use sessions securely

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path,'static/uploads')


# Function to connect to MySQL
def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="chonnipha2546",
        database="retail_db",
        port=3306
    )
    return connection


@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Employees WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user:
            flash("Email already registered!")
            return redirect(url_for('register'))

        # Insert new user
        cursor.execute(
            "INSERT INTO Employees (name, email, role, password) VALUES (%s, %s, %s, %s)",
            (name, email, 'staff', password)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registered successfully! Please login.")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Employees WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            # Save user info in session
            session['user_id'] = user['employee_id']
            session['user_name'] = user['name']
            session['role'] = user['role']
            flash("Login successful!")
            return redirect(url_for('home'))  # or your dashboard
        else:
            flash("Invalid email or password.")

    return render_template('auth.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login'))

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Admin access required.")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def home():
    return render_template('index.html', user_name=session.get('user_name'))

@app.route('/products')
def view_products():
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if search_query:
        cursor.execute("SELECT * FROM Products WHERE name LIKE %s", ('%' + search_query + '%',))
    else:
        cursor.execute("SELECT * FROM Products")

    products = cursor.fetchall()
    cursor.close()
    conn.close()

    # Debugging: print the image paths
    for product in products:
        print(f"Product: {product['name']} - Image Path: {product['image_path']}")

    return render_template('products.html', products=products)

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product_page(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get product details
    cursor.execute("SELECT * FROM Products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found.")
        return redirect(url_for('view_products'))

    # Get reviews for the product
    cursor.execute("SELECT * FROM ProductReviews WHERE product_id = %s", (product_id,))
    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('product_page.html', product=product, reviews=reviews)

@app.route('/product/review/<int:product_id>', methods=['GET', 'POST'])
def product_review(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch product and reviews
    cursor.execute("SELECT * FROM Products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    cursor.execute("SELECT * FROM ProductReviews WHERE product_id = %s", (product_id,))
    reviews = cursor.fetchall()  # Ensure reviews is a list, even if empty

    conn.close()

    if request.method == 'POST':
        # Handle review submission
        rating = request.form['rating']
        review_text = request.form['review_text']
        customer_id = session.get('user_id')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ProductReviews (product_id, customer_id, rating, review_text) 
            VALUES (%s, %s, %s, %s)
        """, (product_id, customer_id, rating, review_text))
        conn.commit()
        conn.close()

        flash('Review submitted successfully!')
        return redirect(url_for('product_review', product_id=product_id))

    return render_template('product_reviews.html', product=product, reviews=reviews)


@app.route('/product/review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    if request.method == 'POST':
        rating = request.form['rating']
        review_text = request.form['review_text']
        customer_id = session.get('user_id')

        if not rating or not review_text:
            flash('Please provide a rating and review text.')
            return redirect(url_for('product_page', product_id=product_id))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ProductReviews (product_id, customer_id, rating, review_text)
            VALUES (%s, %s, %s, %s)
        """, (product_id, customer_id, rating, review_text))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Review added successfully!")
        return redirect(url_for('product_page', product_id=product_id))

@app.route('/product/review/<int:product_id>', methods=['GET', 'POST'])
def view_product_reviews(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch product details
    cursor.execute("SELECT * FROM Products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    # Fetch reviews for the product
    cursor.execute("SELECT * FROM ProductReviews WHERE product_id = %s", (product_id,))
    reviews = cursor.fetchall()

    if request.method == 'POST':
        # Get form data for review
        rating = request.form['rating']
        review_text = request.form['review_text']
        customer_id = session.get('user_id')

        # Insert the review into the database
        cursor.execute("""
            INSERT INTO ProductReviews (product_id, customer_id, rating, review_text)
            VALUES (%s, %s, %s, %s)
        """, (product_id, customer_id, rating, review_text))
        conn.commit()

        flash("Your review has been submitted successfully.")
        return redirect(url_for('view_product_reviews', product_id=product_id))

    conn.close()
    return render_template('product_reviews.html', product=product, reviews=reviews)



@app.route('/product/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        quantity = request.form['quantity']
        category_id = request.form['category_id']

        image = request.files['image']
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = os.path.join('static', 'uploads', filename)
        else:
            image_path = None

        cursor.execute(
            "INSERT INTO Products (name, description, price, quantity, category_id, image_path) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, description, price, quantity, category_id, image_path)
        )
        conn.commit()
        conn.close()

        flash("Product added successfully!")
        return redirect(url_for('view_products'))

    # GET request: fetch category list for dropdown
    cursor.execute("SELECT * FROM productcategories")
    categories = cursor.fetchall()
    conn.close()

    return render_template('add_product.html', categories=categories)

@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        quantity = request.form['quantity']
        category_id = request.form['category_id']

        image_path = request.form.get('existing_image')

        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = os.path.join('static', 'uploads', filename)
        else:
            image_path = request.form.get('existing_image')
        
            cursor.execute("""
                UPDATE Products 
                SET name=%s, description=%s, price=%s, quantity=%s, category_id=%s, image_path=%s 
                WHERE product_id=%s
            """, (name, description, price, quantity, category_id, image_path, product_id))
        
        conn.commit()
        cursor.close()
        conn.close()

        flash("Product updated successfully!")
        return redirect(url_for('view_products'))

    cursor.execute("SELECT * FROM Products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()
    cursor.execute("SELECT category_id, category_name FROM productcategories")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()
    if product is None:
        flash("Product not found!")
        return redirect(url_for('view_products'))
    
    return render_template('edit_product.html', product=product, categories=categories)

@app.route('/product/delete/<int:product_id>')
@admin_required
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Products WHERE product_id=%s", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Product deleted successfully!")
    return redirect(url_for('view_products'))

@app.route('/category/<int:category_id>/products')
def view_products_by_category(category_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT name FROM Categories WHERE category_id = %s", (category_id,))
    category = cursor.fetchone()

    if not category:
        flash("Category not found.")
        return redirect(url_for('view_categories'))

    cursor.execute("""
        SELECT * FROM Products
        WHERE category_id = %s
    """, (category_id,))
    products = cursor.fetchall()

    conn.close()
    return render_template('products.html', products=products, category_name=category['name'])


@app.route('/order/new', methods=['GET', 'POST'])
def new_order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch customers and products to populate dropdowns in form
    cursor.execute("SELECT * FROM Customers")
    customers = cursor.fetchall()
    
    cursor.execute("SELECT product_id, name, price, image FROM Products WHERE quantity > 0")
    products = cursor.fetchall()
    
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        order_date = request.form['order_date']
        product_ids = request.form.getlist('product_id')   # list of product IDs
        quantities = request.form.getlist('quantity')      # list of quantities
        
        if not product_ids or not quantities:
            flash("Please add at least one product before submitting the order.")
            return redirect(url_for('new_order'))
        # Insert a new order
        order_date = request.form['order_date']
        
        # Calculate total_amount by summing (price * quantity)
        total_amount = 0
        
        # Calculate total and validate quantities
        for i in range(len(product_ids)):
            pid = int(product_ids[i])
            qty = int(quantities[i])
            # Get product price
            cursor.execute("SELECT price, quantity FROM Products WHERE product_id = %s", (pid,))
            prod = cursor.fetchone()
            if not prod:
                flash(f"Product with ID {pid} not found.")
                return redirect(url_for('new_order'))
            if qty > prod['quantity']:
                flash(f"Not enough stock for product {pid}")
                return redirect(url_for('new_order'))
            total_amount += prod['price'] * qty
        
        # Insert order
        cursor.execute("INSERT INTO Orders (customer_id, order_date, total_amount) VALUES (%s, %s, %s)",
                       (customer_id, order_date, total_amount))
        order_id = cursor.lastrowid
        
        # Insert order details and update product stock
        for i in range(len(product_ids)):
            pid = int(product_ids[i])
            qty = int(quantities[i])
            cursor.execute("SELECT price FROM Products WHERE product_id = %s", (pid,))
            price = cursor.fetchone()['price']
            cursor.execute("INSERT INTO OrderDetails (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)",
                           (order_id, pid, qty, price))
            # Update stock
            cursor.execute("UPDATE Products SET quantity = quantity - %s WHERE product_id = %s", (qty, pid))
        
        conn.commit()
        conn.close()
        flash("Order created successfully!")
        return redirect(url_for('view_orders'))
    
    conn.close()
    return render_template('new_order.html', customers=customers, products=products, current_date=dt.now().strftime('%Y-%m-%d'))

@app.route('/orders')
def view_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.order_id, c.name AS customer_name, o.order_date, o.total_amount
        FROM Orders o
        JOIN Customers c ON o.customer_id = c.customer_id
        ORDER BY o.order_date DESC
    """)
    orders = cursor.fetchall()
    conn.close()
    return render_template('orders.html', orders=orders)

@app.route('/order/<int:order_id>')
def order_details(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.order_id, c.name AS customer_name, o.order_date, o.total_amount
        FROM Orders o
        JOIN Customers c ON o.customer_id = c.customer_id
        WHERE o.order_id = %s
    """, (order_id,))
    order = cursor.fetchone()

    cursor.execute("""
        SELECT p.name, od.quantity, od.price, (od.quantity * od.price) AS subtotal
        FROM OrderDetails od
        JOIN Products p ON od.product_id = p.product_id
        WHERE od.order_id = %s
    """, (order_id,))
    order_items = cursor.fetchall()

    conn.close()
    return render_template('order_details.html', order=order, order_items=order_items)

@app.route('/customers', methods=['GET'])
def view_customers():
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if search_query:
        cursor.execute("SELECT * FROM Customers WHERE name LIKE %s OR email LIKE %s OR phone LIKE %s", ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%'))
    else:
        cursor.execute("SELECT * FROM Customers")
    customers = cursor.fetchall()
    conn.close()
    return render_template('customers.html', customers=customers)

@app.route('/customer/add', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Customers (name, email, phone) VALUES (%s, %s, %s)",
                       (name, email, phone))
        conn.commit()
        conn.close()
        flash("Customer added!")
        return redirect(url_for('view_customers'))

    return render_template('add_customer.html')

@app.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        cursor.execute("UPDATE Customers SET name=%s, email=%s, phone=%s WHERE customer_id=%s",
                       (name, email, phone, customer_id))
        conn.commit()
        conn.close()
        flash("Customer updated!")
        return redirect(url_for('view_customers'))

    cursor.execute("SELECT * FROM Customers WHERE customer_id=%s", (customer_id,))
    customer = cursor.fetchone()
    conn.close()
    return render_template('edit_customer.html', customer=customer)

@app.route('/customer/delete/<int:customer_id>')
def delete_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Customers WHERE customer_id=%s", (customer_id,))
    conn.commit()
    conn.close()
    flash("Customer deleted.")
    return redirect(url_for('view_customers'))

@app.route('/categories')
def view_categories():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Categories")
    categories = cursor.fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)

@app.route('/category/add', methods=['GET', 'POST'])
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Categories (name) VALUES (%s)", (name,))
        conn.commit()
        conn.close()
        flash("Category added successfully!")
        return redirect(url_for('view_categories'))
    return render_template('add_category.html')

@app.route('/category/edit/<int:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        cursor.execute("UPDATE Categories SET name = %s WHERE category_id = %s", (name, category_id))
        conn.commit()
        conn.close()
        flash("Category updated.")
        return redirect(url_for('view_categories'))

    cursor.execute("SELECT * FROM Categories WHERE category_id = %s", (category_id,))
    category = cursor.fetchone()
    conn.close()
    return render_template('edit_category.html', category=category)

@app.route('/category/delete/<int:category_id>')
def delete_category(category_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Categories WHERE category_id = %s", (category_id,))
    conn.commit()
    conn.close()
    flash("Category deleted.")
    return redirect(url_for('view_categories'))

@app.route('/employees')
@login_required
@admin_required
def view_employees():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Employees")
    employees = cursor.fetchall()
    conn.close()
    return render_template('employees.html', employees=employees)

@app.route('/employee/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        role = request.form['role']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Employees (name, email, role, password)
            VALUES (%s, %s, %s, %s)
        """, (name, email, role, password))
        conn.commit()
        conn.close()
        flash("Employee added.")
        return redirect(url_for('view_employees'))

    return render_template('add_employee.html')

@app.route('/employee/edit/<int:employee_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_employee(employee_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        role = request.form['role']
        cursor.execute("""
            UPDATE Employees SET name=%s, email=%s, role=%s WHERE employee_id=%s
        """, (name, email, role, employee_id))
        conn.commit()
        conn.close()
        flash("Employee updated.")
        return redirect(url_for('view_employees'))

    cursor.execute("SELECT * FROM Employees WHERE employee_id=%s", (employee_id,))
    employee = cursor.fetchone()
    conn.close()
    return render_template('edit_employee.html', employee=employee)

@app.route('/employee/delete/<int:employee_id>')
@login_required
@admin_required
def delete_employee(employee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Employees WHERE employee_id = %s", (employee_id,))
    conn.commit()
    conn.close()
    flash("Employee deleted.")
    return redirect(url_for('view_employees'))

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d'):
    return value.strftime(format)

from datetime import datetime as dt
from flask import render_template

@app.route('/reports')
@login_required
def reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Daily Sales
    cursor.execute("""
        SELECT DATE(order_date) AS date, SUM(total_amount) AS total_sales
        FROM Orders
        GROUP BY DATE(order_date)
        ORDER BY DATE(order_date) DESC
        LIMIT 10
    """)
    sales_by_date = cursor.fetchall()

    for row in sales_by_date:
        row['date'] = dt.strptime(str(row['date']), '%Y-%m-%d')

    for i in range(len(sales_by_date)):
        if i < len(sales_by_date) - 1:
            today = sales_by_date[i]['total_sales']
            prev = sales_by_date[i + 1]['total_sales']
            row_change = 0.0 if prev == 0 else ((today - prev) / prev) * 100
            sales_by_date[i]['change'] = round(row_change, 2)
        else:
            sales_by_date[i]['change'] = 0.0

    # Top Products
    cursor.execute("""
        SELECT p.name, SUM(od.quantity) AS total_sold,
               SUM(od.quantity * od.price) AS revenue,
               COALESCE(c.category_name, 'Uncategorized') AS category
        FROM OrderDetails od
        JOIN Products p ON od.product_id = p.product_id
        LEFT JOIN productcategories c ON p.category_id = c.category_id
        GROUP BY od.product_id
        ORDER BY total_sold DESC
        LIMIT 10
    """)
    best_sellers = cursor.fetchall()

    # Low Stock
    cursor.execute("""
        SELECT name, quantity, 10 AS reorder_level
        FROM Products
        WHERE quantity < 10
    """)
    low_stock = cursor.fetchall()

    conn.close()
    return render_template("reports.html",
                           sales_by_date=sales_by_date,
                           best_sellers=best_sellers,
                           low_stock=low_stock)

if __name__ == '__main__':
    app.run(debug=True, port=5006)
