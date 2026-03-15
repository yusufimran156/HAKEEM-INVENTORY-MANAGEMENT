import os
import time
import io
import secrets
import string
import re
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from functools import wraps
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from models import UserModel, CategoryModel, ProductModel, StockHistoryModel, CustomerModel, SupplierModel, SaleModel, PurchaseModel, WalletModel, TeamModel, OrderModel, CartModel, AddressModel, RewardModel, AdminTeamModel
from utils import InvoiceGenerator
# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'super-secret-key-donot-share'

# Clever Cloud MySQL Environment Variables support
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_ADDON_HOST') or os.environ.get('MYSQL_HOST') or 'localhost'
app.config['MYSQL_USER'] = os.environ.get('MYSQL_ADDON_USER') or os.environ.get('MYSQL_USER') or 'root'
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_ADDON_PASSWORD') or os.environ.get('MYSQL_PASSWORD') or 'yusufimran787161'
app.config['MYSQL_DB'] = os.environ.get('MYSQL_ADDON_DB') or os.environ.get('MYSQL_DB') or 'inventory_db'
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_ADDON_PORT') or 3306)

# Database integrity check
def check_db_integrity():
    with app.app_context():
        try:
            cur = mysql.connection.cursor()
            cur.execute("SHOW COLUMNS FROM sales")
            cols = [c['Field'] for c in cur.fetchall()]
            
            # Ensure 'amount' exists
            if 'amount' not in cols:
                cur.execute("ALTER TABLE sales ADD COLUMN amount DECIMAL(10,2) AFTER product_id")
                cur.execute("UPDATE sales SET amount = total_amount")
                mysql.connection.commit()
            
            # Ensure 'user_id' exists
            if 'user_id' not in cols:
                cur.execute("ALTER TABLE sales ADD COLUMN user_id INT AFTER order_id")
                mysql.connection.commit()
                
            # Ensure 'product_id' exists
            if 'product_id' not in cols:
                cur.execute("ALTER TABLE sales ADD COLUMN product_id INT AFTER user_id")
                mysql.connection.commit()
                
            # products is_active column
            cur.execute("SHOW COLUMNS FROM products")
            prod_cols = [c['Field'] for c in cur.fetchall()]
            if 'is_active' not in prod_cols:
                cur.execute("ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
                mysql.connection.commit()
                
            # users profile and rewards
            cur.execute("SHOW COLUMNS FROM users")
            user_cols = [c['Field'] for c in cur.fetchall()]
            if 'phone' not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
            if 'gender' not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN gender VARCHAR(20) DEFAULT NULL")
            if 'dob' not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN dob DATE DEFAULT NULL")
            if 'profile_picture' not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN profile_picture VARCHAR(255) DEFAULT NULL")
            if 'reward_points' not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN reward_points INT DEFAULT 0")
            mysql.connection.commit()

            # transaction balance
            cur.execute("SHOW COLUMNS FROM wallet_transactions")
            wt_cols = [c['Field'] for c in cur.fetchall()]
            if 'balance_after_transaction' not in wt_cols:
                cur.execute("ALTER TABLE wallet_transactions ADD COLUMN balance_after_transaction DECIMAL(10,2) DEFAULT NULL")
            mysql.connection.commit()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                full_name VARCHAR(100),
                phone VARCHAR(20),
                street VARCHAR(255),
                area VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(100),
                pincode VARCHAR(20),
                landmark VARCHAR(255),
                address_type VARCHAR(50),
                is_default BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """)
            mysql.connection.commit()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS reward_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                order_id INT,
                points INT NOT NULL,
                type VARCHAR(50) NOT NULL COMMENT 'Earned or Redeemed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
            )
            """)
            mysql.connection.commit()

            # orders fields
            cur.execute("SHOW COLUMNS FROM orders")
            order_cols = [c['Field'] for c in cur.fetchall()]
            if 'payment_method' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(50) DEFAULT 'Wallet' AFTER status")
            if 'shipping_name' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN shipping_name VARCHAR(100) DEFAULT NULL")
            if 'shipping_phone' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN shipping_phone VARCHAR(20) DEFAULT NULL")
            if 'shipping_address' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN shipping_address VARCHAR(255) DEFAULT NULL")
            if 'shipping_city' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN shipping_city VARCHAR(100) DEFAULT NULL")
            if 'shipping_state' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN shipping_state VARCHAR(100) DEFAULT NULL")
            if 'shipping_pincode' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN shipping_pincode VARCHAR(20) DEFAULT NULL")
            if 'reward_claimed' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN reward_claimed BOOLEAN DEFAULT FALSE")
            if 'payment_status' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'Paid' AFTER payment_method")
            if 'cod_confirmed' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN cod_confirmed BOOLEAN DEFAULT FALSE")
            if 'paid_at' not in order_cols:
                cur.execute("ALTER TABLE orders ADD COLUMN paid_at DATETIME DEFAULT NULL")
            mysql.connection.commit()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_team (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                phone VARCHAR(20),
                role VARCHAR(50) NOT NULL,
                department VARCHAR(50) NOT NULL,
                profile_image VARCHAR(255),
                status VARCHAR(20) DEFAULT 'Active',
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """)
            mysql.connection.commit()
                
            cur.close()
            print("Database integrity check passed.")
        except Exception as e:
            print(f"Database integrity check failed: {e}")

app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Initialize Extensions ---
mysql = MySQL(app)
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# --- Initialize Models ---
user_model = UserModel(mysql)
category_model = CategoryModel(mysql)
product_model = ProductModel(mysql)
stock_model = StockHistoryModel(mysql, product_model)
customer_model = CustomerModel(mysql)
supplier_model = SupplierModel(mysql)
sale_model = SaleModel(mysql, customer_model)
purchase_model = PurchaseModel(mysql, supplier_model)
wallet_model = WalletModel(mysql)
team_model = TeamModel(mysql)
order_model = OrderModel(mysql)
cart_model = CartModel(mysql)
address_model = AddressModel(mysql)
reward_model = RewardModel(mysql)
admin_team_model = AdminTeamModel(mysql)

# Call this after mysql initialization
with app.app_context():
    try:
        check_db_integrity()
    except Exception as e:
        print(f"Failed db check: {e}")

# --- Helpers ---
def is_logged_in():
    return 'user_id' in session

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin' and not session.get('is_admin'):
            flash('Access denied: Admins only', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_global_data():
    data = {'cart_count': 0, 'wallet_balance': 0.0, 'global_categories': []}
    if is_logged_in():
        user_id = session['user_id']
        data['cart_count'] = cart_model.get_count(user_id)
        data['wallet_balance'] = wallet_model.get_balance(user_id)
    
    # Safely load global categories
    try:
        data['global_categories'] = category_model.get_all_with_counts()
    except Exception:
        data['global_categories'] = []
        
    return data

@app.before_request
def check_auth():
    open_routes = ['login', 'signup', 'static', 'google_callback', 'login_google', 'team']
    if request.endpoint not in open_routes and not is_logged_in():
        if request.endpoint:
            return redirect(url_for('login'))
            
    if is_logged_in() and request.endpoint not in ['logout', 'static']:
        user_id = session.get('user_id')
        user = user_model.find_by_id(user_id)
        if not user or user.get('status') in ['blocked', 'disabled']:
            session.clear()
            flash('Your account has been disabled. Please contact support.', 'danger')
            return redirect(url_for('login'))

# --- Routes ---
# Team routes removed

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shop')
def shop():
    query = request.args.get('q')
    category_id = request.args.get('category')
    sort_by = request.args.get('sort')
    page = int(request.args.get('page', 1))
    per_page = 15
    
    categories = category_model.get_all()
    products, total_count = product_model.search_products(query, category_id, sort_by, page=page, per_page=per_page, active_only=True)
    import math
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
    
    return render_template('shop.html', 
                         categories=categories, 
                         products=products, 
                         page=page, total_pages=total_pages,
                         query=query, category_id=category_id, sort_by=sort_by)

@app.route('/category/<int:id>')
def category_view_flipkart(id):
    categories = category_model.get_all()
    category = next((c for c in categories if c['id'] == id), None)
    if not category:
        flash('Category not found', 'danger')
        return redirect(url_for('index'))
    
    sort_by = request.args.get('sort')
    page = int(request.args.get('page', 1))
    per_page = 15
    
    products, total_count = product_model.search_products(None, id, sort_by, page=page, per_page=per_page, active_only=True)
    import math
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
    
    return render_template('category_products.html', category=category, products=products, total_items=total_count, page=page, total_pages=total_pages)

@app.route('/buy/<int:id>', methods=['POST'])
def buy_product(id):
    if not is_logged_in():
        flash('Please login to purchase items', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    qty = int(request.form.get('quantity', 1))
    product = product_model.get_by_id(id)
    
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('shop'))
    
    if product['quantity'] < qty:
        flash(f'Insufficient stock. Only {product["quantity"]} units available.', 'danger')
        return redirect(url_for('product_view', id=id))
        
    address_id = request.form.get('address_id')
    if not address_id:
        flash('Please select a delivery address.', 'danger')
        return redirect(url_for('product_view', id=id))
        
    address = address_model.get_by_id(address_id, user_id)
    if not address:
        flash('Invalid delivery address selected.', 'danger')
        return redirect(url_for('product_view', id=id))
    
    total_price = float(product['price']) * qty
    payment_method = request.form.get('payment_method', 'Wallet')

    if payment_method == 'Wallet':
        balance = wallet_model.get_balance(user_id)
        if balance < total_price:
            flash(f'Insufficient wallet balance. You need ₹{total_price - balance:.2f} more.', 'danger')
            return redirect(url_for('wallet'))
        payment_status = 'Paid'
    else:
        payment_status = 'Pending'
        
    # Create Order
    order_id = order_model.create(user_id, id, qty, total_price, payment_method, payment_status=payment_status, shipping_details=address)

    if payment_method == 'Wallet':
        # Process Transaction
        tx_id = f"PAY-{order_id}-{int(time.time())}"
        desc = f"Purchased {qty}x {product['name']}"
        if not wallet_model.add_transaction(user_id, total_price, 'DEBIT', 'Wallet', tx_id, 'SUCCESS', desc, order_id):
            flash('Transaction failed. Please try again.', 'danger')
            return redirect(url_for('product_view', id=id))
    # Update Stock
    stock_model.add_transaction(id, user_id, 'OUT', qty, f"Purchase Order #{order_id}")
    # Add to Sales
    sale_model.add_from_order(order_id, user_id, id, total_price)
    
    flash('Order placed successfully!', 'success')
    return redirect(url_for('order_success'))

# --- Order Success Route ---
@app.route('/order-success')
def order_success():
    if not is_logged_in(): return redirect(url_for('login'))
    
    order_id = session.get('last_order_id', 'Unknown')
    payment_status = session.get('last_order_status', 'Pending')
    
    from datetime import datetime, timedelta
    est_delivery = (datetime.now() + timedelta(days=3)).strftime('%d %b %Y')
    
    return render_template('order_success.html', order_id=order_id, payment_status=payment_status, delivery_date=est_delivery)

# --- Cart Routes ---
@app.route('/cart')
def view_cart():
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    items = cart_model.get_user_cart(user_id)
    total = sum(float(item['price']) * item['quantity'] for item in items)
    balance = wallet_model.get_balance(user_id)
    addresses = address_model.get_user_addresses(user_id)
    return render_template('cart.html', items=items, total=total, balance=balance, addresses=addresses)

@app.route('/cart/add/<int:id>', methods=['POST'])
def add_to_cart(id):
    if not is_logged_in(): return redirect(url_for('login'))
    qty = int(request.form.get('quantity', 1))
    product = product_model.get_by_id(id)
    if product and product['quantity'] >= qty:
        cart_model.add_to_cart(session['user_id'], id, qty)
        flash('Product added to cart successfully.', 'success')
    else:
        flash('Out of stock or invalid quantity', 'danger')
    return redirect(request.referrer or url_for('shop'))

@app.route('/cart/remove/<int:id>')
def remove_from_cart(id):
    if not is_logged_in(): return redirect(url_for('login'))
    cart_model.remove_from_cart(id, session['user_id'])
    return redirect(url_for('view_cart'))

@app.route('/cart/update/<int:id>', methods=['POST'])
def update_cart_quantity(id):
    if not is_logged_in(): return {'status': 'unauthorized'}, 401
    
    data = request.get_json()
    qty = int(data.get('quantity', 1)) if data else int(request.form.get('quantity', 1))
    
    if qty < 1: qty = 1
    
    cart_model.update_quantity(id, session['user_id'], qty)
    
    return {'status': 'success'}

@app.route('/checkout', methods=['GET', 'POST'])
def checkout_wizard():
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    items = cart_model.get_user_cart(user_id)
    if not items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('shop'))
        
    total = sum(float(item['price']) * item['quantity'] for item in items)
    balance = wallet_model.get_balance(user_id)
    addresses = address_model.get_user_addresses(user_id)
    
    # Initialize or retrieve step
    step = session.get('checkout_step', 2) # Step 1 is cart review.
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'to_address':
            session['checkout_step'] = 2
            return redirect(url_for('checkout_wizard'))
            
        elif action == 'to_payment':
            address_id = request.form.get('address_id')
            if not address_id:
                flash('Please select an address.', 'danger')
            else:
                session['checkout_address_id'] = address_id
                session['checkout_step'] = 3
            return redirect(url_for('checkout_wizard'))
            
        elif action == 'to_confirm':
            payment_method = request.form.get('payment_method')
            if not payment_method:
                flash('Please select a payment method.', 'danger')
            elif payment_method == 'Wallet' and balance < total:
                flash('Insufficient wallet balance.', 'danger')
            else:
                session['checkout_payment_method'] = payment_method
                session['checkout_step'] = 4
            return redirect(url_for('checkout_wizard'))
            
        elif action == 'place_order':
            if step < 4:
                return redirect(url_for('checkout_wizard'))
                
            address_id = session.get('checkout_address_id')
            payment_method = session.get('checkout_payment_method')
            address = address_model.get_by_id(address_id, user_id)
            if not address or not payment_method:
                flash('Checkout session invalid, please try again.', 'danger')
                session['checkout_step'] = 2
                return redirect(url_for('checkout_wizard'))
                
            # Verify stock
            for item in items:
                if item['stock'] < item['quantity']:
                    flash(f'Product {item["name"]} is now out of stock.', 'danger')
                    return redirect(url_for('view_cart'))
                    
            if payment_method == 'Wallet':
                if balance < total:
                    flash('Insufficient wallet balance', 'danger')
                    return redirect(url_for('checkout_wizard'))
                    
                desc = f"Purchased {len(items)} items from Cart"
                tx_id = f"CART-{int(time.time())}"
                if not wallet_model.add_transaction(user_id, total, 'DEBIT', 'Wallet', tx_id, 'SUCCESS', desc, None):
                    flash('Checkout failed', 'danger')
                    return redirect(url_for('checkout_wizard'))
                payment_status = 'Paid'
            else:
                payment_status = 'Pending'
                
            user_data = user_model.find_by_id(user_id)
            shipping_details = {
                'full_name': request.form.get('full_name', user_data.get('username', 'Customer') if user_data else 'Customer'),
                'email': request.form.get('email', user_data.get('email', '') if user_data else ''),
                'phone': request.form.get('phone', address.get('phone', '') if address else ''),
                'address': f"{address.get('street', '')}, {address.get('area', '')}" if address else '',
                'pincode': address.get('pincode', '') if address else '',
                'city': address.get('city', '') if address else '',
                'state': address.get('state', '') if address else ''
            }
            
            generator = InvoiceGenerator()
            order_ref = f"ORD{int(time.time())}"
            invoice_num, invoice_path = generator.generate_invoice(
                order_id=order_ref, 
                user=user_data, 
                items=items, 
                total=total, 
                shipping=shipping_details
            )

            for item in items:
                order_id = order_model.create(
                    user_id, 
                    item['product_id'], 
                    item['quantity'], 
                    float(item['price']) * item['quantity'], 
                    payment_method, 
                    payment_status,
                    shipping_details=shipping_details,
                    invoice_number=invoice_num,
                    invoice_path=invoice_path
                )
                stock_model.add_transaction(item['product_id'], user_id, 'OUT', item['quantity'], f"Checkout #{order_id}")
                sale_model.add_from_order(order_id, user_id, item['product_id'], float(item['price']) * item['quantity'])
                
            points_earned = int(float(total) * 10)
            user_model.add_reward_points(user_id, points_earned)
            reward_model.add_transaction(user_id, points_earned, 'Earned', None)
                
            cart_model.clear_cart(user_id)
            session.pop('checkout_step', None)
            session.pop('checkout_address_id', None)
            session.pop('checkout_payment_method', None)
            
            session['last_order_id'] = order_ref
            session['last_order_status'] = payment_status
            
            flash(f'All items ordered successfully! Invoice generated. You earned {points_earned} reward points!', 'success')
            return redirect(url_for('order_success'))
            
    # GET Logic
    selected_address = None
    if session.get('checkout_address_id'):
        selected_address = address_model.get_by_id(session.get('checkout_address_id'), user_id)
        
    payment_method = session.get('checkout_payment_method')
    
    return render_template('checkout.html', 
                         step=step, 
                         items=items, 
                         total=total, 
                         balance=balance, 
                         addresses=addresses,
                         selected_address=selected_address,
                         selected_payment=payment_method)

@app.route('/my-orders')
def my_orders():
    if not is_logged_in(): return redirect(url_for('login'))
    orders = order_model.get_user_orders(session['user_id'])
    return render_template('orders.html', orders=orders)

@app.route('/confirm-cod-payment/<int:order_id>', methods=['POST'])
def confirm_cod_payment(order_id):
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    
    # Prevent admin from accessing payment confirmation route
    if session.get('role') == 'admin' or session.get('is_admin'):
        flash('Admins cannot confirm payments here.', 'warning')
        return redirect(url_for('admin_sales'))
        
    order = order_model.get_by_id(order_id)

    if not order or order['user_id'] != user_id:
        flash('Order not found', 'danger')
        return redirect(url_for('my_orders'))
        
    if order['payment_method'] != 'COD' or order['status'] != 'Delivered' or order['payment_status'] != 'Pending':
        flash('Cannot confirm COD payment for this order.', 'danger')
        return redirect(url_for('my_orders'))
        
    order_model.confirm_cod_payment(order_id)
    
    # Update payment_status = 'Paid' and paid_at timestamp is handled by order_model.confirm_cod_payment
    flash('COD Payment Confirmed successfully. Thank you for your purchase!', 'success')
    return redirect(url_for('my_orders'))

@app.route('/orders/cancel/<int:id>')
def cancel_order(id):
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    order = order_model.get_by_id(id)
    
    if not order or order['user_id'] != user_id:
        flash('Order not found', 'danger')
        return redirect(url_for('my_orders'))
        
    if order['status'] not in ['Placed', 'Pending', 'Confirmed']:
        flash('Only Placed or Confirmed orders can be cancelled', 'warning')
        return redirect(url_for('my_orders'))
        
    # Process Refund if prepaid
    refund_success = True
    payment_method = order.get('payment_method', 'Wallet')
    if payment_method in ['Wallet', 'Online']:
        tx_id = f"REF-{int(time.time())}"
        desc = f'Refund for Cancelled Order #{id}'
        refund_success = wallet_model.add_transaction(user_id, order['total_amount'], 'CREDIT', 'Refund', tx_id, 'SUCCESS', desc, id)
    
    if refund_success:
        # Restore Stock
        product_model.update_quantity(order['product_id'], order['quantity'])
        stock_model.add_transaction(order['product_id'], user_id, 'IN', order['quantity'], f"Order #{id} Cancelled")
        # Reduce Revenue via deleting sale
        sale_model.delete_by_order(id)
        # Update Order Status
        order_model.update_status(id, 'Cancelled')
        if payment_method in ['Wallet', 'Online']:
            flash('Order cancelled and amount refunded to your wallet.', 'success')
        else:
            flash('Order cancelled successfully.', 'success')
    else:
        flash('Refund failed. Please contact support.', 'danger')
        
    return redirect(url_for('my_orders'))



@app.route('/admin/sales')
@admin_required
def admin_sales():
    sales = sale_model.get_all_with_details()
    return render_template('admin_sales.html', sales=sales)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username, email = request.form.get('username'), request.form.get('email')
        password, confirm = request.form.get('password'), request.form.get('confirm_password')

        if not all([username, email, password]):
            flash('Please fill out all fields', 'danger')
        elif password != confirm:
            flash('Passwords do not match', 'danger')
        else:
            email = email.strip()
            password = password.strip()
            
            # Simple Email Format Validation
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                flash('Please enter a valid email address.', 'danger')
                return render_template('signup.html')

            # Advanced Server-side Password Validation
            if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password) or not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                flash('Password must be at least 8 characters long, include an uppercase letter, a lowercase letter, a number, and a special character.', 'danger')
                return render_template('signup.html')
            
            # Block Common Weak Passwords
            weak_passwords = ['12345678', 'password', 'admin123', 'qwerty123', '123456789']
            if password.lower() in weak_passwords:
                flash('Password is too common or weak. Please choose a stronger password.', 'danger')
                return render_template('signup.html')

            try:
                user_model.create_user(username.strip(), email, password)
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                error_str = str(e).lower()
                if 'duplicate entry' in error_str or 'integrityerror' in error_str:
                    flash('A user with that email or username already exists. Please try another.', 'warning')
                else:
                    flash('Registration failed due to a server error. Please try again later.', 'danger')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier, password = request.form.get('username'), request.form.get('password')
        user = user_model.find_by_identifier(identifier)
        if user and user_model.verify_password(user['password_hash'], password):
            if user.get('status') == 'blocked':
                flash('Your account has been blocked. Please contact admin.', 'danger')
                return redirect(url_for('login'))
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user.get('role', 'user')
            session['is_admin'] = bool(user.get('is_admin'))
            
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        identifier, password = request.form.get('username'), request.form.get('password')
        user = user_model.find_by_identifier(identifier)
        if user and user_model.verify_password(user['password_hash'], password):
            # Check if admin
            if user.get('role') == 'admin' or user.get('is_admin'):
                if user.get('status') == 'blocked':
                    flash('Admin account is blocked.', 'danger')
                    return redirect(url_for('admin_login'))
                
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = 'admin'
                session['is_admin'] = True
                flash('Welcome to Admin Panel!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Access Denied: Not an admin account', 'danger')
                return redirect(url_for('admin_login'))
        flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/login/google')
def login_google():
    return google.authorize_redirect(url_for('google_callback', _external=True))

@app.route('/login/google/callback')
def google_callback():
    token = google.authorize_access_token()
    user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
    email, name = user_info['email'], user_info['name']
    
    user = user_model.find_by_identifier(email)
    if not user:
        rand_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
        user_model.create_user(name, email, rand_pass)
        user = user_model.find_by_identifier(email)
    
    session['user_id'], session['username'], session['role'] = user['id'], user['username'], user.get('role', 'user')
    flash(f'Welcome back, {name}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    wallet_balance = wallet_model.get_balance(session.get('user_id'))
    stats = product_model.get_stats()
    
    # Get recent activity and low stock (moved from original)
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT sh.*, p.name as product_name 
        FROM stock_history sh
        LEFT JOIN products p ON sh.product_id = p.id
        ORDER BY sh.created_at DESC LIMIT 5
    """)
    recent_activity = cur.fetchall()
    cur.execute("SELECT * FROM products WHERE quantity <= 5 ORDER BY quantity ASC LIMIT 5")
    low_stock = cur.fetchall()

    if session.get('is_admin'):
        # Admin Stats
        cur.execute("SELECT COUNT(*) as count FROM users")
        total_users = cur.fetchone()['count']
        
        # Robust Revenue Calculation
        total_revenue = 0
        try:
            # Check sales table for amount or total_amount
            cur.execute("SHOW COLUMNS FROM sales")
            cols = [c['Field'] for c in cur.fetchall()]
            if 'total_amount' in cols:
                cur.execute("SELECT SUM(total_amount) as revenue FROM sales")
                total_revenue = cur.fetchone()['revenue'] or 0
            elif 'amount' in cols:
                cur.execute("SELECT SUM(amount) as revenue FROM sales")
                total_revenue = cur.fetchone()['revenue'] or 0
        except Exception as e:
            print(f"Revenue query failed: {e}")
                
        cur.execute("SELECT COUNT(*) as count FROM orders")
        total_orders = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'Cancelled'")
        cancelled_orders = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'Returned'")
        returned_orders = cur.fetchone()['count']
        
        # Pie Chart: Order status distribution
        cur.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
        order_statuses = cur.fetchall()
        pie_labels = [row['status'] for row in order_statuses]
        pie_data   = [row['count'] for row in order_statuses]
        
        # Bar Chart: Sales overview
        revenue_col = 'amount' if 'amount' in cols else 'total_amount'
        cur.execute(f"""
            SELECT DATE(created_at) as d, SUM({revenue_col}) as revenue 
            FROM sales GROUP BY d ORDER BY d DESC LIMIT 7
        """)
        sales_data = cur.fetchall()[::-1]
        bar_labels = [row['d'].strftime('%d %b') if row['d'] else '' for row in sales_data]
        bar_data   = [float(row['revenue']) if row['revenue'] else 0 for row in sales_data]
        
        cur.close()
        
        return render_template('admin_dashboard.html', 
                             stats=stats, 
                             total_users=total_users,
                             total_revenue=total_revenue,
                             total_orders=total_orders,
                             cancelled_orders=cancelled_orders,
                             returned_orders=returned_orders,
                             pie_labels=pie_labels, pie_data=pie_data,
                             bar_labels=bar_labels, bar_data=bar_data,
                             low_stock=low_stock,
                             recent_activity=recent_activity)
    else:
        cur.close()
        # User Dashboard
        orders = order_model.get_user_orders(session.get('user_id'))
        transactions = wallet_model.get_transactions(session.get('user_id'), limit=5)
        return render_template('user_dashboard.html', 
                             wallet_balance=wallet_balance,
                             orders=orders,
                             transactions=transactions,
                             categories=category_model.get_all())

@app.route('/admin/products')
@admin_required
def admin_products():
    page = int(request.args.get('page', 1))
    query = request.args.get('q')
    category_id = request.args.get('category')
    
    products, total_count = product_model.search_products(query, category_id, page=page, per_page=50, active_only=False)
    import math
    total_pages = math.ceil(total_count / 50) if total_count > 0 else 1
    
    return render_template('admin_products.html', 
                          products=products,
                          categories=category_model.get_all(),
                          suppliers=supplier_model.get_all(),
                          page=page, total_pages=total_pages, query=query, category_id=category_id)

@app.route('/admin/add-product', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        data = request.form.to_dict()
        file = request.files.get('image')
        data['image_url'] = None
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{int(time.time())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            data['image_url'] = filename
        product_model.add(data)
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin_add_product.html', 
                          categories=category_model.get_all(),
                          suppliers=supplier_model.get_all())

@app.route('/admin/categories')
@admin_required
def categories_admin():
    return render_template('categories.html', categories=category_model.get_all())

@app.route('/categories/add', methods=['POST'])
@admin_required
def add_category():
    name, desc = request.form.get('name'), request.form.get('description')
    if name:
        category_model.add(name, desc)
        flash('Category added successfully!', 'success')
    return redirect(url_for('categories_admin'))

@app.route('/categories/edit/<int:id>', methods=['POST'])
@admin_required
def edit_category(id):
    name, desc = request.form.get('name'), request.form.get('description')
    category_model.update(id, name, desc)
    flash('Category updated successfully!', 'success')
    return redirect(url_for('categories_admin'))

@app.route('/categories/delete/<int:id>')
@admin_required
def delete_category(id):
    # Check if products exist in this category
    products, total_count = product_model.search_products(category_id=id, active_only=False)
    if total_count > 0:
        flash('Cannot delete category: It contains products. Please delete or reassign them first.', 'danger')
    else:
        category_model.delete(id)
        flash('Category deleted successfully!', 'success')
    return redirect(url_for('categories_admin'))

@app.route('/products/toggle/<int:id>')
@admin_required
def toggle_product(id):
    product_model.toggle_active_status(id)
    flash('Product status updated.', 'success')
    return redirect(request.referrer or url_for('admin_products'))

@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    product = product_model.get_by_id(id)
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('admin_products'))

    if request.method == 'POST':
        data = request.form.to_dict()
        file = request.files.get('image')
        data['image_url'] = product['image_url']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{int(time.time())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            data['image_url'] = filename
        
        product_model.update(id, data)
        flash('Product updated', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin_add_product.html', 
                          product=product,
                          categories=category_model.get_all(),
                          suppliers=supplier_model.get_all())

@app.route('/products/delete/<int:id>')
@admin_required
def delete_product(id):
    # 1. First gather ALL pending/placed orders for this exact product
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, user_id, quantity, total_amount, payment_method, status FROM orders WHERE product_id = %s AND status IN ('Placed', 'Pending', 'Confirmed')", (id,))
    pending_orders = cur.fetchall()
    
    # 2. Refund all affected users securely using the wallet model
    if pending_orders:
        for order in pending_orders:
            # Refund logic
            if order['payment_method'] in ['Wallet', 'Online']:
                tx_id = f"REF-ADMIN-{order['id']}-{int(time.time())}"
                wallet_model.process_refund(
                    order['user_id'], 
                    order['total_amount'], 
                    f"Admin removed product. Auto-Refund for Order {order['id']}",
                    tx_id
                )
            
            # Cancel the order softly and reduce revenue statistics
            order_model.update_status(order['id'], 'Out of Stock')
            sale_model.delete_by_order(order['id'])

    # 3. Soft disable product rather than full delete if orders exist, to prevent foreign key breakages. 
    # For now, we will perform a full delete if requested, assuming setup script uses cascading deletes.
    product_model.delete(id)
    cur.close()
    
    flash('Product deleted. Processing automated refunds for any pending customers affected.', 'success')
    return redirect(url_for('admin_products'))

@app.route('/products/view/<int:id>')
def product_view(id):
    product = product_model.get_by_id(id)
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('products'))
    
    addresses = []
    if is_logged_in():
        addresses = address_model.get_user_addresses(session['user_id'])
        
    return render_template('product_view.html', product=product, addresses=addresses)

@app.route('/stock')
def stock():
    return render_template('stock.html', history=stock_model.get_all(), products=product_model.get_all())

@app.route('/stock/add', methods=['POST'])
@admin_required
def add_stock_transaction():
    p_id, t_type, qty, reason = request.form.get('product_id'), request.form.get('type'), request.form.get('quantity'), request.form.get('reason')
    if t_type == 'OUT' and product_model.get_by_id(p_id)['quantity'] < int(qty):
        flash('Insufficient stock', 'danger')
    else:
        stock_model.add_transaction(p_id, session.get('user_id'), t_type, qty, reason)
        flash('Stock updated', 'success')
    return redirect(url_for('stock'))

@app.route('/reports')
@admin_required
def reports():
    cur = mysql.connection.cursor()
    # Inventory stats
    cur.execute("SELECT SUM(price * quantity) as total_value FROM products")
    total_value = cur.fetchone()['total_value'] or 0
    cur.execute("SELECT * FROM products WHERE quantity <= low_stock_threshold")
    low_stock = cur.fetchall()
    
    # Sales Overview
    cur.execute("SHOW COLUMNS FROM sales")
    cols = [c['Field'] for c in cur.fetchall()]
    revenue_col = 'total_amount' if 'total_amount' in cols else 'amount'
    
    cur.execute(f"SELECT SUM({revenue_col}) as revenue, COUNT(*) as count FROM sales")
    sales_overview = cur.fetchone()
    if not sales_overview['revenue']: sales_overview['revenue'] = 0

    # Monthly Sales (Last 6 months)
    cur.execute(f"""
        SELECT DATE_FORMAT(created_at, '%Y-%m') as month, SUM({revenue_col}) as revenue 
        FROM sales GROUP BY month ORDER BY month DESC LIMIT 6
    """)
    monthly_sales = cur.fetchall()[::-1] # Reverse to chronological
    
    # Daily Sales (Last 14 days)
    cur.execute(f"""
        SELECT DATE(created_at) as date, SUM({revenue_col}) as revenue 
        FROM sales GROUP BY date ORDER BY date DESC LIMIT 14
    """)
    daily_sales = cur.fetchall()[::-1]
    
    cur.execute("""
        SELECT c.name, COUNT(p.id) as product_count, SUM(p.quantity) as total_qty
        FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.id
    """)
    cat_stats = cur.fetchall()
    cur.close()

    # Prepare data for Chart.js
    monthly_labels = [row['month'] for row in monthly_sales]
    monthly_data = [float(row['revenue']) for row in monthly_sales]
    daily_labels = [row['date'].strftime('%d %b') for row in daily_sales]
    daily_data = [float(row['revenue']) for row in daily_sales]
    
    return render_template('reports.html', 
                         total_value=total_value, 
                         low_stock_products=low_stock, 
                         category_stats=cat_stats,
                         sales_overview=sales_overview,
                         monthly_labels=monthly_labels,
                         monthly_data=monthly_data,
                         daily_labels=daily_labels,
                         daily_data=daily_data)

@app.route('/api/admin/revenue-trend')
@admin_required
def api_revenue_trend():
    period = request.args.get('period', 'monthly')
    cur = mysql.connection.cursor()
    
    # Check if 'amount' exists, otherwise use 'total_amount'
    cur.execute("SHOW COLUMNS FROM sales")
    cols = [c['Field'] for c in cur.fetchall()]
    rev_col = 'amount' if 'amount' in cols else 'total_amount'
    
    if period == 'weekly':
        cur.execute(f"SELECT DATE(created_at) as label, SUM({rev_col}) as data FROM sales WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) GROUP BY label ORDER BY label ASC")
    elif period == 'monthly':
        cur.execute(f"SELECT DATE_FORMAT(created_at, '%%Y-%%m-%%d') as label, SUM({rev_col}) as data FROM sales WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) GROUP BY label ORDER BY label ASC")
    elif period == 'yearly':
        cur.execute(f"SELECT DATE_FORMAT(created_at, '%%Y-%%m') as label, SUM({rev_col}) as data FROM sales WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH) GROUP BY label ORDER BY label ASC")
    
    results = cur.fetchall()
    cur.close()
    
    labels = [row['label'] for row in results]
    data = [float(row['data']) if row['data'] else 0 for row in results]
    
    return {'labels': labels, 'data': data}

@app.route('/admin/export-report/<type>')
@admin_required
def export_report(type):
    cur = mysql.connection.cursor()
    # Build query based on type
    time_filter = ""
    if type == 'weekly':
        time_filter = "WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
    elif type == 'monthly':
        time_filter = "WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
    elif type == 'yearly':
        time_filter = "WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)"
        
    query = f"""
        SELECT o.id as order_id, u.username, p.name as product_name, o.quantity, 
               o.total_amount, o.status, DATE_FORMAT(o.created_at, '%%Y-%%m-%%d %%H:%%i') as order_date
        FROM orders o 
        LEFT JOIN users u ON o.user_id = u.id 
        LEFT JOIN products p ON o.product_id = p.id
        {time_filter}
        ORDER BY o.created_at DESC
    """
    cur.execute(query)
    orders = cur.fetchall()
    cur.close()

    wb = Workbook()
    ws = wb.active
    ws.title = f"{type.capitalize()} Report"
    headers = ['Order ID', 'Username', 'Product Name', 'Quantity', 'Total Amount (₹)', 'Status', 'Order Date']
    ws.append(headers)
    
    for row in orders:
        ws.append([row['order_id'], row['username'], row['product_name'], row['quantity'], float(row['total_amount']), row['status'], row['order_date']])
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"export_{type}_{int(time.time())}.xlsx"
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=filename)

@app.route('/rewards/redeem', methods=['POST'])
def redeem_rewards():
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    
    points = user_model.get_reward_points(user_id)
    if points >= 100:
        money_value = points / 10  # 100 points = Rs 10
        user_model.deduct_reward_points(user_id, points)
        reward_model.add_transaction(user_id, points, 'Redeemed')
        
        tx_id = f"RWD-{int(time.time())}"
        wallet_model.add_transaction(user_id, money_value, 'CREDIT', 'Rewards', tx_id, 'SUCCESS')
        
        flash(f'Successfully redeemed {points} points for ₹{money_value} wallet balance.', 'success')
    else:
        flash('You need at least 100 points to redeem.', 'warning')
        
    return redirect(request.referrer or url_for('profile'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    user = user_model.find_by_id(user_id)
    addresses = address_model.get_user_addresses(user_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            data = request.form.to_dict()
            file = request.files.get('profile_picture')
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{int(time.time())}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                data['profile_picture'] = filename
            
            user_model.update_profile(user_id, data)
            session['username'] = data.get('username')
            flash('Profile updated', 'success')
            
        elif action == 'change_password':
            if user_model.verify_password(user['password_hash'], request.form.get('old_password')):
                if request.form.get('new_password') == request.form.get('confirm_password'):
                    user_model.update_password(user_id, request.form.get('new_password'))
                    flash('Password changed', 'success')
                else: flash('Passwords do not match', 'danger')
            else: flash('Incorrect old password', 'danger')
        return redirect(url_for('profile'))
    
    # E-commerce stats
    user_orders = order_model.get_user_orders(user_id)
    stats = {
        'total_orders': len(user_orders),
        'total_spent': sum(float(o['total_amount']) for o in user_orders if o['status'] != 'Cancelled')
    }
    return render_template('profile.html', user=user, stats=stats, addresses=addresses)

@app.route('/add_address', methods=['POST'])
def add_address():
    if not is_logged_in(): return redirect(url_for('login'))
    
    try:
        data = request.form.to_dict()
        
        # Validations for required fields
        required_fields = ['full_name', 'phone', 'pincode', 'street', 'city', 'state']
        for field in required_fields:
            if not data.get(field) or not str(data.get(field)).strip():
                flash(f"Error: {field.replace('_', ' ').title()} is required and cannot be empty.", "danger")
                return redirect(request.referrer or url_for('profile'))
        
        # Validate exact 10 length phone
        if len(str(data.get('phone'))) != 10 or not str(data.get('phone')).isdigit():
            flash("Error: Phone number must be exactly 10 digits.", "danger")
            return redirect(request.referrer or url_for('profile'))
            
        # Validate pincode length
        if len(str(data.get('pincode'))) != 6 or not str(data.get('pincode')).isdigit():
            flash("Error: Pincode must be exactly 6 digits.", "danger")
            return redirect(request.referrer or url_for('profile'))
        
        address_model.add(session['user_id'], data)
        flash("Address added successfully!", "success")
    except Exception as e:
        flash(f"Database Error: Could not save address. Please check input formats.", "danger")
        print(f"Address Add Error: {e}")
        
    return redirect(request.referrer or url_for('profile'))

@app.route('/addresses/edit/<int:id>', methods=['POST'])
def edit_address(id):
    if not is_logged_in(): return redirect(url_for('login'))
    data = request.form.to_dict()
    address_model.update(id, session['user_id'], data)
    flash("Address updated successfully!", "success")
    return redirect(request.referrer or url_for('profile'))

@app.route('/addresses/delete/<int:id>')
def delete_address(id):
    if not is_logged_in(): return redirect(url_for('login'))
    address_model.delete(id, session['user_id'])
    flash("Address deleted successfully.", "success")
    return redirect(request.referrer or url_for('profile'))

@app.route('/addresses/default/<int:id>')
def set_default_address(id):
    if not is_logged_in(): return redirect(url_for('login'))
    address_model.set_default(id, session['user_id'])
    flash("Default address updated.", "success")
    return redirect(request.referrer or url_for('profile'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        session['theme'] = request.form.get('theme')
        flash('Settings saved', 'success')
    return render_template('settings.html')

@app.route('/users')
@admin_required
def users():
    return render_template('users.html', users=user_model.get_all_users())

@app.route('/users/role/<int:user_id>', methods=['POST'])
@admin_required
def update_user_role(user_id):
    if user_id == session.get('user_id'):
        flash('Cannot change your own role!', 'danger')
        return redirect(url_for('users'))
    user_model.update_role(user_id, request.form.get('role'))
    flash('User role updated', 'success')
    return redirect(url_for('users'))

@app.route('/admin/users/status/<int:user_id>/<string:status>')
@admin_required
def update_user_status(user_id, status):
    if user_id == session.get('user_id'):
        flash('Cannot block yourself!', 'danger')
        return redirect(url_for('users'))
    if status not in ['active', 'blocked']:
        flash('Invalid status', 'danger')
        return redirect(url_for('users'))
    user_model.update_status(user_id, status)
    flash(f'User account {status} successfully', 'success')
    return redirect(url_for('users'))

@app.route('/admin/users/toggle-admin/<int:user_id>')
@admin_required
def toggle_admin_status(user_id):
    if user_id == session.get('user_id'):
        flash('Cannot remove your own admin status!', 'danger')
        return redirect(url_for('users'))
    user_model.toggle_admin(user_id)
    flash('Admin status updated', 'success')
    return redirect(url_for('users'))

@app.route('/admin/users/details/<int:user_id>')
@admin_required
def admin_user_details(user_id):
    target_user = user_model.get_user_with_wallet(user_id)
    if not target_user:
        flash('User not found', 'danger')
        return redirect(url_for('users'))
        
    orders = order_model.get_user_orders(user_id)
    transactions = wallet_model.get_transactions(user_id, limit=100)
    stats = order_model.get_user_stats(user_id)
    
    return render_template('admin_user_details.html', 
                         user=target_user, 
                         orders=orders, 
                         transactions=transactions,
                         stats=stats)

@app.route('/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('Cannot delete yourself!', 'danger')
        return redirect(url_for('users'))
    user_model.delete_user(user_id)
    flash('User deleted successfully', 'success')
    return redirect(url_for('users'))

@app.route('/admin/users/reset-password/<int:user_id>')
@admin_required
def admin_reset_password(user_id):
    new_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    user_model.update_password(user_id, new_pass)
    flash(f'Password reset successful. New password: {new_pass}', 'success')
    return redirect(url_for('users'))


@app.route('/customers')
def customers():
    return render_template('customers.html', customers=customer_model.get_all())

@app.route('/customers/add', methods=['POST'])
def add_customer():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')
    id = customer_model.add(name, email, phone, address)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'status': 'success', 'id': id, 'name': name}
    flash('Customer added', 'success')
    return redirect(url_for('customers'))

@app.route('/customers/ledger/<int:id>')
def customer_ledger(id):
    customer = customer_model.get_all() # Just to find it
    customer = next((c for c in customer if c['id'] == id), None)
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('customers'))
    return render_template('ledger.html', entity=customer, ledger=customer_model.get_ledger(id), type='Customer')

@app.route('/customers/edit/<int:id>', methods=['POST'])
def edit_customer(id):
    customer_model.update(id, request.form.get('name'), request.form.get('email'), request.form.get('phone'), request.form.get('address'))
    flash('Customer updated', 'success')
    return redirect(url_for('customers'))

@app.route('/customers/delete/<int:id>')
def delete_customer(id):
    customer_model.delete(id)
    flash('Customer deleted', 'success')
    return redirect(url_for('customers'))

@app.route('/suppliers')
def suppliers():
    return render_template('suppliers.html', suppliers=supplier_model.get_all())

@app.route('/suppliers/add', methods=['POST'])
def add_supplier():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')
    id = supplier_model.add(name, email, phone, address)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'status': 'success', 'id': id, 'name': name}
    flash('Supplier added', 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/edit/<int:id>', methods=['POST'])
def edit_supplier(id):
    supplier_model.update(id, request.form.get('name'), request.form.get('email'), request.form.get('phone'), request.form.get('address'))
    flash('Supplier updated', 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/delete/<int:id>')
def delete_supplier(id):
    supplier_model.delete(id)
    flash('Supplier deleted', 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/ledger/<int:id>')
def supplier_ledger(id):
    supplier = supplier_model.get_all()
    supplier = next((s for s in supplier if s['id'] == id), None)
    if not supplier:
        flash('Supplier not found', 'danger')
        return redirect(url_for('suppliers'))
    return render_template('ledger.html', entity=supplier, ledger=supplier_model.get_ledger(id), type='Supplier')

@app.route('/sales/add', methods=['POST'])
def add_sale():
    data = request.form
    try:
        total = float(data['total'])
        paid = float(data['paid'])
        due = total - paid
        sale_id = sale_model.add(int(data['customer_id']), total, paid, due, data['method'])
        flash(f'Sale recorded! Invoice #INV-{sale_id}', 'success')
    except Exception as e:
        flash(f'Error recording sale: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/purchases/add', methods=['POST'])
def add_purchase():
    data = request.form
    try:
        total = float(data['total'])
        paid = float(data['paid'])
        due = total - paid
        purchase_id = purchase_model.add(int(data['supplier_id']), total, paid, due, data['method'])
        flash(f'Purchase recorded! Invoice #PUR-{purchase_id}', 'success')
    except Exception as e:
         flash(f'Error recording purchase: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/invoice/<type>/<int:id>')
def generate_invoice(type, id):
    is_receipt = request.args.get('receipt', False)
    cur = mysql.connection.cursor()
    if type == 'sale':
        cur.execute("SELECT s.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone FROM sales s JOIN customers c ON s.customer_id = c.id WHERE s.id = %s", (id,))
    else:
        cur.execute("SELECT p.*, s.name as supplier_name, s.email as supplier_email, s.phone as supplier_phone FROM purchases p JOIN suppliers s ON p.supplier_id = s.id WHERE p.id = %s", (id,))
    data = cur.fetchone()
    cur.close()
    if not data:
        flash('Document not found', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('invoice.html', data=data, type=type, is_receipt=is_receipt)

@app.route('/members')
def members():
    return render_template('members.html', team=team_model.get_all())

@app.route('/admin/members', methods=['GET', 'POST'])
@admin_required
def manage_members():
    if request.method == 'POST':
        action = request.form.get('action')
        flash(f"Processing action: {action}", 'info')
        # Handle Image Upload
        file = request.files.get('image')
        image_url = request.form.get('image_url') # Fallback to URL if no file
        
        print(f"DEBUG: Action={action}, File={file.filename if file else 'None'}, URL={image_url}")

        if file and allowed_file(file.filename):
            filename = secure_filename(f"team_{int(time.time())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = filename

        if action == 'add':
            print(f"Adding member: {request.form.get('name')}")
            try:
                team_model.add(
                    request.form.get('name'), 
                    request.form.get('role'), 
                    request.form.get('description'), 
                    image_url,
                    request.form.get('linkedin') or None,
                    request.form.get('github') or None,
                    request.form.get('email') or None
                )
                flash('Member added successfully', 'success')
            except Exception as e:
                print(f"ADD ERROR: {e}")
                flash(f"Error adding member: {e}", 'danger')
        elif action == 'edit':
            member_id = request.form.get('id')
            print(f"Editing member ID: {member_id}")
            # Keep old image if no new one provided
            if not (file and file.filename) and not request.form.get('image_url'):
                existing = team_model.get_by_id(member_id)
                if existing:
                    image_url = existing['image_url']
                    print(f"Keeping existing image: {image_url}")
            
            try:
                team_model.update(
                    member_id, 
                    request.form.get('name'), 
                    request.form.get('role'), 
                    request.form.get('description'), 
                    image_url,
                    request.form.get('linkedin') or None,
                    request.form.get('github') or None,
                    request.form.get('email') or None
                )
                flash('Member updated successfully', 'success')
            except Exception as e:
                print(f"UPDATE ERROR: {e}")
                flash(f"Error updating member: {e}", 'danger')
        return redirect(url_for('manage_members'))
    return render_template('manage_members.html', team=team_model.get_all())

@app.route('/admin/members/delete/<int:id>')
@admin_required
def delete_member(id):
    team_model.delete(id)
    flash('Member deleted', 'success')
    return redirect(url_for('manage_members'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/wallet', methods=['GET', 'POST'])
def wallet():
    if not is_logged_in(): return redirect(url_for('login'))
    if session.get('role') == 'admin':
        flash('Unauthorized access to Wallet.', 'danger')
        return redirect(url_for('dashboard'))
    user_id = session['user_id']
    
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
            method = request.form.get('method', 'UPI')
            transaction_id = f"TXN-{secrets.token_hex(4).upper()}"
            
            if amount > 0:
                desc = f"Added funds to wallet via {method}"
                if wallet_model.add_transaction(user_id, amount, 'CREDIT', method, transaction_id, 'SUCCESS', desc, None):
                    flash(f'₹{amount} added to wallet successfully!', 'success')
                else:
                    flash('Transaction failed. Please try again.', 'danger')
            else:
                flash('Invalid amount entered.', 'danger')
        except ValueError:
            flash('Invalid amount format.', 'danger')
            
        return redirect(url_for('wallet'))

    balance = wallet_model.get_balance(user_id)
    transactions = wallet_model.get_transactions(user_id)
    reward_points = user_model.get_reward_points(user_id)
    
    total_added = sum(float(t['amount']) for t in transactions if t['type'] in ['CREDIT', 'Reward'])

    return render_template('wallet.html', balance=balance, transactions=transactions, 
                         total_added=total_added, reward_points=reward_points)

@app.route('/wallet/convert_points', methods=['POST'])
def convert_points():
    if not is_logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    points_to_convert = int(request.form.get('points', 0))
    
    current_points = user_model.get_reward_points(user_id)
    if points_to_convert <= 0 or points_to_convert > current_points:
        flash('Invalid points selected.', 'danger')
        return redirect(url_for('wallet'))
    
    wallet_money = points_to_convert / 10.0
    
    user_model.deduct_reward_points(user_id, points_to_convert)
    tx_id = f"RWD-{int(time.time())}"
    desc = f"Converted {points_to_convert} Reward Pts"
    wallet_model.add_transaction(user_id, wallet_money, 'CREDIT', 'Reward Conversion', tx_id, 'SUCCESS', desc, None)
    
    flash(f'Successfully converted {points_to_convert} points to ₹{wallet_money}.', 'success')
    return redirect(url_for('wallet'))

@app.route('/wallet/edit/<int:id>', methods=['POST'])
def edit_wallet_transaction(id):
    if not is_logged_in(): return redirect(url_for('login'))
    amount = float(request.form.get('amount'))
    t_type = request.form.get('type')
    method = request.form.get('method')
    if wallet_model.update_transaction(id, amount, t_type, method):
        flash('Transaction corrected successfully', 'success')
    else:
        flash('Failed to update transaction', 'danger')
    return redirect(url_for('wallet'))

@app.route('/wallet/delete/<int:id>')
def delete_wallet_transaction(id):
    if not is_logged_in(): return redirect(url_for('login'))
    if wallet_model.delete_transaction(id):
        flash('Transaction deleted and balance adjusted', 'success')
    else:
        flash('Failed to delete transaction', 'danger')
    return redirect(url_for('wallet'))

@app.route('/admin/wallet')
@admin_required
def admin_wallet():
    transactions = wallet_model.get_all_transactions()
    return render_template('admin_wallet.html', transactions=transactions)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = order_model.get_all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/orders/update-status/<int:id>', methods=['POST'])
@admin_required
def update_order_status(id):
    new_status = request.form.get('status')
    order = order_model.get_by_id(id)
    
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('admin_orders'))
        
    old_status = order['status']
    
    if old_status == new_status:
        return redirect(url_for('admin_orders'))
        
    # Logic for Cancellation & Refund
    if new_status == 'Cancelled' and old_status != 'Cancelled':
        refund_success = True
        payment_method = order.get('payment_method', 'Wallet')
        if payment_method in ['Wallet', 'Online']:
            tx_id = f"REF-{int(time.time())}"
            desc = f'Refund for Cancelled Order #{id}'
            refund_success = wallet_model.add_transaction(order['user_id'], order['total_amount'], 'CREDIT', 'Refund', tx_id, 'SUCCESS', desc, id)
            
        if refund_success:
            # Restore Stock
            qty = order['quantity']
            product_model.update_quantity(order['product_id'], qty)
            stock_model.add_transaction(order['product_id'], session.get('user_id'), 'IN', qty, f"Order #{id} Cancelled by Admin")
            # Reduce Revenue via deleting sale
            sale_model.delete_by_order(id)
            if payment_method in ['Wallet', 'Online']:
                flash(f'Order #{id} cancelled and amount refunded to user.', 'success')
            else:
                flash(f'Order #{id} cancelled. Stock restored.', 'success')
        else:
            flash('Refund failed. Status not updated.', 'danger')
            return redirect(url_for('admin_orders'))
            
    # Logic for Returns (restores stock, deducts revenue, optional refund depending on policy)
    elif new_status == 'Returned' and old_status not in ['Returned', 'Cancelled']:
        refund_success = True
        payment_method = order.get('payment_method', 'Wallet')
        if payment_method in ['Wallet', 'Online']:
             # Refund logic can apply to returned too
            tx_id = f"RET-{int(time.time())}"
            desc = f'Refund for Returned Order #{id}'
            refund_success = wallet_model.add_transaction(order['user_id'], order['total_amount'], 'CREDIT', 'Refund', tx_id, 'SUCCESS', desc, id)
            
        if refund_success:
            qty = order['quantity']
            product_model.update_quantity(order['product_id'], qty)
            stock_model.add_transaction(order['product_id'], session.get('user_id'), 'IN', qty, f"Order #{id} Returned")
            sale_model.delete_by_order(id)
            if payment_method in ['Wallet', 'Online']:
                flash(f'Order #{id} returned and amount refunded to user.', 'success')
            else:
                flash(f'Order #{id} returned. Stock restored.', 'success')
        else:
            flash('Refund failed. Status not updated.', 'danger')
            return redirect(url_for('admin_orders'))
            
    # Process Rewards when delivered
    elif new_status == 'Delivered' and old_status != 'Delivered':
        # Payment status for COD will now be handled manually via the "Mark Paid" button.
        pass
        
        if not order.get('reward_claimed'):
            total_amount = float(order['total_amount'])
            points_earned = int(total_amount // 1000) * 100
            
            if points_earned > 0:
                user_model.add_reward_points(order['user_id'], points_earned)
                order_model.mark_reward_claimed(id)
                # optionally show flash message to admin too
                
    order_model.update_status(id, new_status)
    flash(f'Order #{id} status updated to {new_status}', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/orders/mark-paid/<int:id>', methods=['POST'])
@admin_required
def mark_order_paid(id):
    order = order_model.get_by_id(id)
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('admin_orders'))
        
    if order.get('payment_method') == 'COD' and order.get('payment_status') != 'Paid':
        order_model.update_payment_status(id, 'Paid')
        flash(f'Payment for Order #{id} marked as successfully received.', 'success')
    else:
        flash('Payment is already settled or method is not Hand Cash/COD.', 'warning')
        
    return redirect(url_for('admin_orders'))

# Team routes fully removed

if __name__ == '__main__':
    print("Starting Hakeem Inventory System...")
    app.run(debug=True, host='0.0.0.0', port=5000)
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)