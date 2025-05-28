from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed to use sessions securely

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = 'static/uploads'


# Function to connect to MySQL
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("MYSQLHOST"),
        user=os.environ.get("MYSQLUSER"),
        password=os.environ.get("MYSQLPASSWORD"),
        database=os.environ.get("MYSQLDATABASE"),
        port=int(os.environ.get("MYSQLPORT"))
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/product/add', methods=['GET', 'POST'])
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
            image_path = filename
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
def edit_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        quantity = request.form['quantity']
        category_id = request.form['category_id']

        image = request.files.get('image')
        image_path = None
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'static/uploads/{filename}'
        if image_path:
            cursor.execute("""
                UPDATE Products 
                SET name=%s, description=%s, price=%s, quantity=%s, category_id=%s, image_path=%s 
                WHERE product_id=%s
            """, (name, description, price, quantity, category_id, image_path, product_id))
        else:
            cursor.execute("""
                UPDATE Products SET name=%s, description=%s, price=%s, quantity=%s, category_id=%s WHERE product_id=%s
                """, (name, description, price, quantity, category_id, product_id))
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
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Products WHERE product_id=%s", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Product deleted successfully!")
    return redirect(url_for('view_products'))

@app.route('/order/new', methods=['GET', 'POST'])
def new_order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch customers and products to populate dropdowns in form
    cursor.execute("SELECT * FROM Customers")
    customers = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Products WHERE quantity > 0")
    products = cursor.fetchall()
    
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        product_ids = request.form.getlist('product_id')   # list of product IDs
        quantities = request.form.getlist('quantity')      # list of quantities
        
        # Insert a new order
        from datetime import datetime
        order_date = datetime.now()
        
        # Calculate total_amount by summing (price * quantity)
        total_amount = 0
        
        # Calculate total and validate quantities
        for i in range(len(product_ids)):
            pid = int(product_ids[i])
            qty = int(quantities[i])
            # Get product price
            cursor.execute("SELECT price, quantity FROM Products WHERE product_id = %s", (pid,))
            prod = cursor.fetchone()
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
    return render_template('new_order.html', customers=customers, products=products)

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

@app.route('/customers')
def view_customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
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


@app.route('/reports')
@login_required
def reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total Sales by Date
    cursor.execute("""
        SELECT DATE(order_date) AS date, SUM(total_amount) AS total_sales
        FROM Orders
        GROUP BY DATE(order_date)
        ORDER BY date DESC
        LIMIT 10;
    """)
    sales_by_date = cursor.fetchall()

    # Best-selling Products
    cursor.execute("""
        SELECT p.name, SUM(od.quantity) AS total_sold
        FROM OrderDetails od
        JOIN Products p ON od.product_id = p.product_id
        GROUP BY od.product_id
        ORDER BY total_sold DESC
        LIMIT 10;
    """)
    best_sellers = cursor.fetchall()

    # Low Stock Products
    cursor.execute("""
        SELECT name, quantity
        FROM Products
        WHERE quantity < 10
        ORDER BY quantity ASC;
    """)
    low_stock = cursor.fetchall()

    conn.close()

    return render_template('reports.html',
                           sales_by_date=sales_by_date,
                           best_sellers=best_sellers,
                           low_stock=low_stock)

if __name__ == '__main__':
    app.run(debug=True, port=5006)

