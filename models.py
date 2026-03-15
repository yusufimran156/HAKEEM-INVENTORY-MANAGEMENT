import secrets
import string
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

class UserModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def create_user(self, username, email, password, role='user'):
        password_hash = generate_password_hash(password)
        cur = self.mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)", 
                    (username, email, password_hash, role))
        user_id = cur.lastrowid
        # Automatically create wallet record
        cur.execute("INSERT IGNORE INTO wallets (user_id, balance) VALUES (%s, %s)", (user_id, 0.00))
        self.mysql.connection.commit()
        cur.close()

    def find_by_identifier(self, identifier):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (identifier, identifier))
        user = cur.fetchone()
        cur.close()
        return user

    def find_by_id(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        return user

    def get_user_with_wallet(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT u.*, w.balance 
            FROM users u
            LEFT JOIN wallets w ON u.id = w.user_id
            WHERE u.id = %s
        """, (user_id,))
        user = cur.fetchone()
        cur.close()
        return user

    def verify_password(self, stored_hash, password):
        return check_password_hash(stored_hash, password)

    def update_profile(self, user_id, data):
        cur = self.mysql.connection.cursor()
        query = """UPDATE users SET 
                   username = %s, email = %s, phone = %s, gender = %s, dob = %s"""
        params = [data.get('username'), data.get('email'), data.get('phone'), data.get('gender'), data.get('dob')]
        
        if data.get('profile_picture'):
            query += ", profile_picture = %s"
            params.append(data.get('profile_picture'))
            
        query += " WHERE id = %s"
        params.append(user_id)
        
        cur.execute(query, tuple(params))
        self.mysql.connection.commit()
        cur.close()

    def get_reward_points(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT reward_points FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        return result['reward_points'] if result else 0

    def add_reward_points(self, user_id, points):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE users SET reward_points = reward_points + %s WHERE id = %s", (points, user_id))
        self.mysql.connection.commit()
        cur.close()

    def deduct_reward_points(self, user_id, points):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE users SET reward_points = reward_points - %s WHERE id = %s", (points, user_id))
        self.mysql.connection.commit()
        cur.close()

    def update_password(self, user_id, new_password):
        password_hash = generate_password_hash(new_password)
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
        self.mysql.connection.commit()
        cur.close()

    def get_all_users(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        cur.close()
        return users

    def update_role(self, user_id, new_role):
        cur = self.mysql.connection.cursor()
        is_admin = 1 if new_role == 'admin' else 0
        cur.execute("UPDATE users SET role = %s, is_admin = %s WHERE id = %s", (new_role, is_admin, user_id))
        self.mysql.connection.commit()
        cur.close()

    def update_status(self, user_id, new_status):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
        self.mysql.connection.commit()
        cur.close()

    def toggle_admin(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE users SET is_admin = NOT is_admin WHERE id = %s", (user_id,))
        # Also sync role
        cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
        is_admin = cur.fetchone()['is_admin']
        new_role = 'admin' if is_admin else 'user'
        cur.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        self.mysql.connection.commit()
        cur.close()

    def delete_user(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        self.mysql.connection.commit()
        cur.close()

class CategoryModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM categories ORDER BY name ASC")
        categories = cur.fetchall()
        cur.close()
        return categories

    def get_all_with_counts(self):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT c.*, (SELECT COUNT(*) FROM products WHERE category_id = c.id AND is_active = TRUE) as item_count 
            FROM categories c 
            ORDER BY c.name ASC
        """)
        categories = cur.fetchall()
        cur.close()
        return categories
    
    def add(self, name, description):
        cur = self.mysql.connection.cursor()
        cur.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (name, description))
        self.mysql.connection.commit()
        cur.close()

    def update(self, cat_id, name, description):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE categories SET name = %s, description = %s WHERE id = %s", (name, description, cat_id))
        self.mysql.connection.commit()
        cur.close()

    def delete(self, cat_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM categories WHERE id = %s", (cat_id,))
        self.mysql.connection.commit()
        cur.close()

class ProductModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT p.*, c.name as category_name, s.name as supplier_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id 
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            ORDER BY p.name ASC
        """)
        products = cur.fetchall()
        cur.close()
        return products

    def get_by_id(self, product_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id 
            WHERE p.id = %s
        """, (product_id,))
        product = cur.fetchone()
        cur.close()
        return product

    def add(self, data):
        cur = self.mysql.connection.cursor()
        price = float(data.get('price', 0)) if data.get('price') else 0.0
        quantity = int(data.get('quantity', 0)) if data.get('quantity') else 0
        threshold = int(data.get('low_stock_threshold', 10)) if data.get('low_stock_threshold') else 10
        cat_id = int(data.get('category_id')) if data.get('category_id') else None
        sup_id = int(data.get('supplier_id')) if data.get('supplier_id') else None
        
        cur.execute("""
            INSERT INTO products (name, category_id, supplier_id, price, quantity, description, image_url, low_stock_threshold) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (data['name'], cat_id, sup_id, price, quantity, 
              data['description'], data['image_url'], threshold))
        self.mysql.connection.commit()
        cur.close()

    def update(self, product_id, data):
        cur = self.mysql.connection.cursor()
        price = float(data.get('price', 0)) if data.get('price') else 0.0
        quantity = int(data.get('quantity', 0)) if data.get('quantity') else 0
        threshold = int(data.get('low_stock_threshold', 10)) if data.get('low_stock_threshold') else 10
        cat_id = int(data.get('category_id')) if data.get('category_id') else None
        sup_id = int(data.get('supplier_id')) if data.get('supplier_id') else None

        cur.execute("""
            UPDATE products 
            SET name = %s, category_id = %s, supplier_id = %s, price = %s, quantity = %s, description = %s, image_url = %s, low_stock_threshold = %s 
            WHERE id = %s
        """, (data['name'], cat_id, sup_id, price, quantity, 
              data['description'], data['image_url'], threshold, product_id))
        self.mysql.connection.commit()
        cur.close()

    def delete(self, product_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        self.mysql.connection.commit()
        cur.close()

    def update_quantity(self, product_id, amount):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s", (amount, product_id))
        self.mysql.connection.commit()
        cur.close()

    def get_stats(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) as count FROM products")
        total_products = cur.fetchone()['count']
        cur.execute("SELECT SUM(quantity) as total_stock FROM products")
        result = cur.fetchone()
        total_stock = result['total_stock'] if result['total_stock'] is not None else 0
        cur.execute("SELECT COUNT(*) as low_stock FROM products WHERE quantity <= low_stock_threshold")
        low_stock_count = cur.fetchone()['low_stock']
        cur.execute("SELECT COUNT(*) as count FROM categories")
        total_categories = cur.fetchone()['count']
        cur.close()
        return {
            'total_products': total_products,
            'total_stock': total_stock,
            'low_stock_count': low_stock_count,
            'total_categories': total_categories
        }

    def get_chart_data(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT name, quantity FROM products ORDER BY quantity DESC LIMIT 5")
        bar_data = cur.fetchall()
        cur.execute("""
            SELECT c.name, COUNT(p.id) as count 
            FROM categories c 
            LEFT JOIN products p ON c.id = p.category_id 
            GROUP BY c.id
        """)
        pie_data = cur.fetchall()
        cur.close()
        return {
            'bar_labels': [item['name'] for item in bar_data],
            'bar_values': [item['quantity'] for item in bar_data],
            'pie_labels': [item['name'] for item in pie_data],
            'pie_values': [item['count'] for item in pie_data]
        }

    def search_products(self, query=None, category_id=None, sort_by=None, page=1, per_page=None, active_only=True):
        cur = self.mysql.connection.cursor()
        
        # Base query
        base_sql = "FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE 1=1"
        params = []
        
        if active_only:
            base_sql += " AND p.is_active = TRUE"
            
        if query:
            base_sql += " AND p.name LIKE %s"
            params.append(f"%{query}%")
        if category_id:
            base_sql += " AND p.category_id = %s"
            params.append(category_id)
            
        # Get total count
        count_sql = "SELECT COUNT(p.id) as total " + base_sql
        cur.execute(count_sql, tuple(params))
        total_count = cur.fetchone()['total']
        
        # Get actual records
        sql = "SELECT p.*, c.name as category_name " + base_sql
        
        if sort_by == 'price_low':
            sql += " ORDER BY p.price ASC"
        elif sort_by == 'price_high':
            sql += " ORDER BY p.price DESC"
        else:
            sql += " ORDER BY p.name ASC"
            
        if per_page:
            offset = (page - 1) * per_page
            sql += " LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
        cur.execute(sql, tuple(params))
        products = cur.fetchall()
        cur.close()
        
        # Convert any Decimal or None to normal format if needed
        return products, total_count
        
    def toggle_active_status(self, product_id):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE products SET is_active = NOT COALESCE(is_active, TRUE) WHERE id = %s", (product_id,))
        self.mysql.connection.commit()
        cur.close()

    def update_quantity(self, product_id, change):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s", (change, product_id))
        self.mysql.connection.commit()
        cur.close()

class StockHistoryModel:
    def __init__(self, mysql, product_model):
        self.mysql = mysql
        self.product_model = product_model

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT sh.*, p.name as product_name, u.username, u2.username as operator_name
            FROM stock_history sh
            LEFT JOIN products p ON sh.product_id = p.id
            LEFT JOIN users u ON sh.user_id = u.id
            LEFT JOIN users u2 ON sh.updated_by = u2.id
            ORDER BY sh.created_at DESC
        """)
        history = cur.fetchall()
        cur.close()
        return history

    def add_transaction(self, product_id, user_id, type_in_out, quantity, reason):
        qty = int(quantity) if quantity else 0
        if qty <= 0: raise ValueError("Quantity must be greater than zero")
        
        # Get current stock
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT quantity FROM products WHERE id = %s", (product_id,))
        res = cur.fetchone()
        old_stock = res['quantity'] if res else 0
        
        change = qty if type_in_out == 'IN' else -qty
        new_stock = old_stock + change
        
        cur.execute("""
            INSERT INTO stock_history (product_id, user_id, type, quantity, old_stock, added_quantity, new_stock, updated_by, reason) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (product_id, user_id, type_in_out, qty, old_stock, change, new_stock, user_id, reason))
        self.mysql.connection.commit()
        cur.close()
        
        self.product_model.update_quantity(product_id, change)

class CustomerModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM customers ORDER BY name ASC")
        customers = cur.fetchall()
        cur.close()
        return customers

    def add(self, name, email, phone, address):
        cur = self.mysql.connection.cursor()
        cur.execute("INSERT INTO customers (name, email, phone, address) VALUES (%s, %s, %s, %s)", 
                    (name, email, phone, address))
        last_id = cur.lastrowid
        self.mysql.connection.commit()
        cur.close()
        return last_id

    def update_balance(self, customer_id, amount):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE customers SET balance = balance + %s WHERE id = %s", (amount, customer_id))
        self.mysql.connection.commit()
        cur.close()

    def update(self, customer_id, name, email, phone, address):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            UPDATE customers SET name = %s, email = %s, phone = %s, address = %s 
            WHERE id = %s
        """, (name, email, phone, address, customer_id))
        self.mysql.connection.commit()
        cur.close()

    def delete(self, customer_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
        self.mysql.connection.commit()
        cur.close()

    def get_ledger(self, customer_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT 'SALE' as type, id, total_amount, paid_amount, due_amount, created_at 
            FROM sales WHERE customer_id = %s
            ORDER BY created_at DESC
        """, (customer_id,))
        ledger = cur.fetchall()
        cur.close()
        return ledger

class SupplierModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM suppliers ORDER BY name ASC")
        suppliers = cur.fetchall()
        cur.close()
        return suppliers

    def add(self, name, email, phone, address):
        cur = self.mysql.connection.cursor()
        cur.execute("INSERT INTO suppliers (name, email, phone, address) VALUES (%s, %s, %s, %s)", 
                    (name, email, phone, address))
        last_id = cur.lastrowid
        self.mysql.connection.commit()
        cur.close()
        return last_id

    def update_balance(self, supplier_id, amount):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE suppliers SET balance = balance + %s WHERE id = %s", (amount, supplier_id))
        cur.execute("UPDATE suppliers SET status = IF(balance > 0, 'Creditor', 'Debtor') WHERE id = %s", (supplier_id,))
        self.mysql.connection.commit()
        cur.close()

    def update(self, supplier_id, name, email, phone, address):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            UPDATE suppliers SET name = %s, email = %s, phone = %s, address = %s 
            WHERE id = %s
        """, (name, email, phone, address, supplier_id))
        self.mysql.connection.commit()
        cur.close()

    def delete(self, supplier_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
        self.mysql.connection.commit()
        cur.close()

    def get_ledger(self, supplier_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT 'PURCHASE' as type, id, total_amount, paid_amount, due_amount, created_at 
            FROM purchases WHERE supplier_id = %s
            ORDER BY created_at DESC
        """, (supplier_id,))
        ledger = cur.fetchall()
        cur.close()
        return ledger

class SaleModel:
    def __init__(self, mysql, customer_model):
        self.mysql = mysql
        self.customer_model = customer_model

    def add(self, customer_id, total, paid, due, method):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            INSERT INTO sales (customer_id, total_amount, paid_amount, due_amount, payment_method) 
            VALUES (%s, %s, %s, %s, %s)
        """, (customer_id, total, paid, due, method))
        sale_id = cur.lastrowid
        self.mysql.connection.commit()
        cur.close()
        if due > 0:
            self.customer_model.update_balance(customer_id, due)
        return sale_id

    def get_stats(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT SUM(total_amount) as total_sales FROM sales")
        total_sales = cur.fetchone()['total_sales'] or 0
        cur.execute("SELECT SUM(due_amount) as outstanding_sales FROM sales")
        outstanding_sales = cur.fetchone()['outstanding_sales'] or 0
        cur.close()
        return total_sales, outstanding_sales

    def add_from_order(self, order_id, user_id, product_id, amount):
        cur = self.mysql.connection.cursor()
        # Set both 'amount' and 'total_amount' for compatibility
        cur.execute("""
            INSERT INTO sales (order_id, user_id, product_id, amount, total_amount) 
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, user_id, product_id, amount, amount))
        self.mysql.connection.commit()
        cur.close()

    def delete_by_order(self, order_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM sales WHERE order_id = %s", (order_id,))
        self.mysql.connection.commit()
        cur.close()

    def get_all_with_details(self):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT s.*, u.username, p.name as product_name 
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN products p ON s.product_id = p.id
            ORDER BY s.created_at DESC
        """)
        sales = cur.fetchall()
        cur.close()
        return sales

class PurchaseModel:
    def __init__(self, mysql, supplier_model):
        self.mysql = mysql
        self.supplier_model = supplier_model

    def add(self, supplier_id, total, paid, due, method):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            INSERT INTO purchases (supplier_id, total_amount, paid_amount, due_amount, payment_method) 
            VALUES (%s, %s, %s, %s, %s)
        """, (supplier_id, total, paid, due, method))
        purchase_id = cur.lastrowid
        self.mysql.connection.commit()
        cur.close()
        if due > 0:
            self.supplier_model.update_balance(supplier_id, due)
        return purchase_id

    def get_stats(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT SUM(total_amount) as total_purchases FROM purchases")
        total_purchases = cur.fetchone()['total_purchases'] or 0
        cur.close()
        return total_purchases

class WalletModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_balance(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT balance FROM wallets WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        if not result:
            # Fallback/Safety: Create wallet if missing
            cur.execute("INSERT IGNORE INTO wallets (user_id, balance) VALUES (%s, %s)", (user_id, 0.00))
            self.mysql.connection.commit()
            cur.close()
            return 0.0
        cur.close()
        return float(result['balance'])

    def add_transaction(self, user_id, amount, type, method, transaction_id, status='SUCCESS', description=None, order_id=None):
        cur = self.mysql.connection.cursor()
        try:
            # 1. Fetch current balance
            cur.execute("SELECT balance FROM wallets WHERE user_id = %s FOR UPDATE", (user_id,))
            wallet = cur.fetchone()
            current_balance = float(wallet['balance']) if wallet else 0.0
            
            new_balance = current_balance
            
            if status == 'SUCCESS':
                if type == 'CREDIT':
                    new_balance += float(amount)
                elif type == 'DEBIT':
                    new_balance -= float(amount)
            
            # 2. Add Transaction
            cur.execute("""
                INSERT INTO wallet_transactions (user_id, amount, type, payment_method, transaction_id, status, balance_after_transaction, description, order_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, amount, type, method, transaction_id, status, new_balance, description, order_id))
            
            # 3. Update Balance in Wallets Table if SUCCESS
            if status == 'SUCCESS':
                cur.execute("UPDATE wallets SET balance = %s WHERE user_id = %s", (new_balance, user_id))
            
            self.mysql.connection.commit()
            return True
        except Exception as e:
            self.mysql.connection.rollback()
        finally:
            cur.close()

    def process_refund(self, user_id, amount, description, tx_id):
        cur = self.mysql.connection.cursor()
        try:
            cur.execute("SELECT balance FROM wallets WHERE user_id = %s FOR UPDATE", (user_id,))
            wallet = cur.fetchone()
            current_balance = float(wallet['balance']) if wallet else 0.0
            new_balance = current_balance + float(amount)
            
            # Avoid duplicate refunds by checking transaction ID
            cur.execute("SELECT id FROM wallet_transactions WHERE transaction_id = %s", (tx_id,))
            if cur.fetchone():
                return False

            cur.execute("""
                INSERT INTO wallet_transactions (user_id, amount, type, payment_method, transaction_id, status, balance_after_transaction, description) 
                VALUES (%s, %s, 'CREDIT', 'Refund', %s, 'SUCCESS', %s, %s)
            """, (user_id, amount, tx_id, new_balance, description))
            
            cur.execute("UPDATE wallets SET balance = %s WHERE user_id = %s", (new_balance, user_id))
            self.mysql.connection.commit()
            return True
        except Exception as e:
            self.mysql.connection.rollback()
            return False
        finally:
            cur.close()

    def get_transaction_by_id(self, tx_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM wallet_transactions WHERE id = %s", (tx_id,))
        tx = cur.fetchone()
        cur.close()
        return tx

    def update_transaction(self, tx_id, amount, type, method, status='SUCCESS'):
        cur = self.mysql.connection.cursor()
        try:
            # 1. Get old transaction
            cur.execute("SELECT * FROM wallet_transactions WHERE id = %s", (tx_id,))
            old_tx = cur.fetchone()
            if not old_tx: return False

            # 2. Reverse old balance change if it was SUCCESS
            if old_tx['status'] == 'SUCCESS':
                if old_tx['type'] == 'CREDIT':
                    cur.execute("UPDATE wallets SET balance = balance - %s WHERE user_id = %s", (old_tx['amount'], old_tx['user_id']))
                else:
                    cur.execute("UPDATE wallets SET balance = balance + %s WHERE user_id = %s", (old_tx['amount'], old_tx['user_id']))

            # 3. Update record
            cur.execute("""
                UPDATE wallet_transactions 
                SET amount = %s, type = %s, payment_method = %s, status = %s 
                WHERE id = %s
            """, (amount, type, method, status, tx_id))

            # 4. Apply new balance change if SUCCESS
            if status == 'SUCCESS':
                if type == 'CREDIT':
                    cur.execute("UPDATE wallets SET balance = balance + %s WHERE user_id = %s", (amount, old_tx['user_id']))
                else:
                    cur.execute("UPDATE wallets SET balance = balance - %s WHERE user_id = %s", (amount, old_tx['user_id']))

            self.mysql.connection.commit()
            return True
        except Exception as e:
            self.mysql.connection.rollback()
            print(f"Error updating transaction: {e}")
            return False
        finally:
            cur.close()

    def delete_transaction(self, tx_id):
        cur = self.mysql.connection.cursor()
        try:
            # 1. Get transaction
            cur.execute("SELECT * FROM wallet_transactions WHERE id = %s", (tx_id,))
            tx = cur.fetchone()
            if not tx: return False

            # 2. Reverse balance change if it was SUCCESS
            if tx['status'] == 'SUCCESS':
                if tx['type'] == 'CREDIT':
                    cur.execute("UPDATE wallets SET balance = balance - %s WHERE user_id = %s", (tx['amount'], tx['user_id']))
                else:
                    cur.execute("UPDATE wallets SET balance = balance + %s WHERE user_id = %s", (tx['amount'], tx['user_id']))

            # 3. Delete record
            cur.execute("DELETE FROM wallet_transactions WHERE id = %s", (tx_id,))
            
            self.mysql.connection.commit()
            return True
        except Exception as e:
            self.mysql.connection.rollback()
            print(f"Error deleting transaction: {e}")
            return False
        finally:
            cur.close()

    def get_transactions(self, user_id, limit=20):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM wallet_transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT %s", (user_id, limit))
        txs = cur.fetchall()
        cur.close()
        return txs

    def get_all_transactions(self):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT wt.*, u.username, u.email 
            FROM wallet_transactions wt 
            JOIN users u ON wt.user_id = u.id 
            ORDER BY wt.created_at DESC
        """)
        txs = cur.fetchall()
        cur.close()
        return txs

class TeamModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM team_members ORDER BY id ASC")
        members = cur.fetchall()
        cur.close()
        return members

    def get_by_id(self, member_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM team_members WHERE id = %s", (member_id,))
        member = cur.fetchone()
        cur.close()
        return member

    def add(self, name, role, description, image_url, linkedin=None, github=None, email=None):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            INSERT INTO team_members (name, role, description, image_url, linkedin, github, email) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, role, description, image_url, linkedin, github, email))
        self.mysql.connection.commit()
        cur.close()

    def update(self, member_id, name, role, description, image_url, linkedin=None, github=None, email=None):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            UPDATE team_members SET name = %s, role = %s, description = %s, image_url = %s, 
            linkedin = %s, github = %s, email = %s 
            WHERE id = %s
        """, (name, role, description, image_url, linkedin, github, email, member_id))
        self.mysql.connection.commit()
        cur.close()

    def delete(self, member_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM team_members WHERE id = %s", (member_id,))
        self.mysql.connection.commit()
        cur.close()

class CartModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def add_to_cart(self, user_id, product_id, quantity=1):
        cur = self.mysql.connection.cursor()
        # Check if already in cart
        cur.execute("SELECT * FROM cart WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        item = cur.fetchone()
        if item:
            cur.execute("UPDATE cart SET quantity = quantity + %s WHERE id = %s", (quantity, item['id']))
        else:
            cur.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)", (user_id, product_id, quantity))
        self.mysql.connection.commit()
        cur.close()

    def get_user_cart(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT c.*, p.name, p.price, p.image_url, p.quantity as stock 
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        items = cur.fetchall()
        cur.close()
        return items

    def remove_from_cart(self, cart_id, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM cart WHERE id = %s AND user_id = %s", (cart_id, user_id))
        self.mysql.connection.commit()
        cur.close()

    def update_quantity(self, cart_id, user_id, quantity):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE cart SET quantity = %s WHERE id = %s AND user_id = %s", (quantity, cart_id, user_id))
        self.mysql.connection.commit()
        cur.close()

    def clear_cart(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))
        self.mysql.connection.commit()
        cur.close()

    def get_count(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        return result['count'] if result['count'] else 0

class OrderModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def create(self, user_id, product_id, quantity, total_amount, payment_method='Wallet', payment_status='Paid', shipping_details=None, invoice_number=None, invoice_path=None):
        if not shipping_details: shipping_details = {}
        cur = self.mysql.connection.cursor()
        cur.execute("""
            INSERT INTO orders (
                user_id, product_id, quantity, total_amount, status, payment_method, payment_status, 
                shipping_name, shipping_phone, shipping_address, shipping_city, shipping_state, shipping_pincode,
                invoice_number, invoice_path
            ) 
            VALUES (%s, %s, %s, %s, 'Placed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, product_id, quantity, total_amount, payment_method, payment_status,
            shipping_details.get('full_name'),
            shipping_details.get('phone'),
            shipping_details.get('street', shipping_details.get('address')),
            shipping_details.get('city'),
            shipping_details.get('state'),
            shipping_details.get('pincode'),
            invoice_number, invoice_path
        ))
        order_id = cur.lastrowid
        
        # Save explicit shipping details
        cur.execute("""
            INSERT INTO order_shipping_details (
                user_id, order_id, full_name, email, phone, alternate_phone, address, pincode, city, state
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, order_id,
            shipping_details.get('full_name'),
            shipping_details.get('email', ''),
            shipping_details.get('phone'),
            shipping_details.get('alternate_phone', ''),
            shipping_details.get('street', shipping_details.get('address')),
            shipping_details.get('pincode'),
            shipping_details.get('city'),
            shipping_details.get('state')
        ))
        
        self.mysql.connection.commit()
        cur.close()
        return order_id
        
    def update_payment_status(self, order_id, status):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE orders SET payment_status = %s WHERE id = %s", (status, order_id))
        self.mysql.connection.commit()
        cur.close()

    def confirm_cod_payment(self, order_id):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE orders SET payment_status = 'Paid', cod_confirmed = TRUE, paid_at = NOW() WHERE id = %s", (order_id,))
        self.mysql.connection.commit()
        cur.close()

    def mark_reward_claimed(self, order_id):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE orders SET reward_claimed = TRUE WHERE id = %s", (order_id,))
        self.mysql.connection.commit()
        cur.close()

    def get_user_orders(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT o.*, p.name as product_name, p.image_url 
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC
        """, (user_id,))
        orders = cur.fetchall()
        cur.close()
        return orders

    def update_status(self, order_id, status):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
        self.mysql.connection.commit()
        cur.close()

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT o.*, u.username, p.name as product_name 
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN products p ON o.product_id = p.id
            ORDER BY o.created_at DESC
        """)
        orders = cur.fetchall()
        cur.close()
        return orders

    def get_by_id(self, order_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        cur.close()
        return order

    def get_user_stats(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT 
                COUNT(*) as total_orders, 
                IFNULL(SUM(total_amount), 0) as total_spent,
                MAX(created_at) as last_purchase
            FROM orders 
            WHERE user_id = %s AND status != 'Cancelled'
        """, (user_id,))
        stats = cur.fetchone()
        cur.close()
        return stats

class AddressModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_user_addresses(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM addresses WHERE user_id = %s ORDER BY is_default DESC, id DESC", (user_id,))
        addresses = cur.fetchall()
        cur.close()
        return addresses

    def get_by_id(self, address_id, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM addresses WHERE id = %s AND user_id = %s", (address_id, user_id))
        addr = cur.fetchone()
        cur.close()
        return addr

    def add(self, user_id, data):
        cur = self.mysql.connection.cursor()
        
        # Safe count extraction for first address -> set as default
        cur.execute("SELECT COUNT(*) AS c FROM addresses WHERE user_id = %s", (user_id,))
        res = cur.fetchone()
        count = res['c'] if (res and isinstance(res, dict) and 'c' in res) else (res[0] if isinstance(res, tuple) else 0)
        is_default = True if count == 0 else False
        
        cur.execute("""
            INSERT INTO addresses (user_id, full_name, phone, street, area, city, state, pincode, landmark, address_type, is_default)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, data.get('full_name'), data.get('phone'), data.get('street'), data.get('area'),
            data.get('city'), data.get('state'), data.get('pincode'), data.get('landmark'),
            data.get('address_type'), is_default
        ))
        self.mysql.connection.commit()
        cur.close()
        return True

    def update(self, address_id, user_id, data):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            UPDATE addresses SET 
            full_name=%s, phone=%s, street=%s, area=%s, city=%s, state=%s, pincode=%s, landmark=%s, address_type=%s
            WHERE id=%s AND user_id=%s
        """, (
            data.get('full_name'), data.get('phone'), data.get('street'), data.get('area'),
            data.get('city'), data.get('state'), data.get('pincode'), data.get('landmark'),
            data.get('address_type'), address_id, user_id
        ))
        self.mysql.connection.commit()
        cur.close()
        return True

    def delete(self, address_id, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("DELETE FROM addresses WHERE id=%s AND user_id=%s", (address_id, user_id))
        self.mysql.connection.commit()
        cur.close()
        return True

    def set_default(self, address_id, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE addresses SET is_default = FALSE WHERE user_id = %s", (user_id,))
        cur.execute("UPDATE addresses SET is_default = TRUE WHERE id = %s AND user_id = %s", (address_id, user_id))
        self.mysql.connection.commit()
        cur.close()
        return True

class RewardModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def add_transaction(self, user_id, points, type, order_id=None):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            INSERT INTO reward_transactions (user_id, points, type, order_id) 
            VALUES (%s, %s, %s, %s)
        """, (user_id, points, type, order_id))
        self.mysql.connection.commit()
        cur.close()

    def get_user_transactions(self, user_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM reward_transactions WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        transactions = cur.fetchall()
        cur.close()
        return transactions

class AdminTeamModel:
    def __init__(self, mysql):
        self.mysql = mysql

    def get_all(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM admin_team ORDER BY joined_date DESC")
        members = cur.fetchall()
        cur.close()
        return members

    def get_by_id(self, member_id):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT * FROM admin_team WHERE id = %s", (member_id,))
        member = cur.fetchone()
        cur.close()
        return member

    def add(self, data):
        cur = self.mysql.connection.cursor()
        cur.execute("""
            INSERT INTO admin_team (full_name, email, phone, role, department, profile_image, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (data['full_name'], data['email'], data['phone'], data['role'], data['department'], data.get('profile_image'), data.get('status', 'Active'), data.get('created_by')))
        self.mysql.connection.commit()
        cur.close()

    def update(self, member_id, data):
        cur = self.mysql.connection.cursor()
        if 'profile_image' in data and data['profile_image']:
            cur.execute("""
                UPDATE admin_team SET full_name=%s, email=%s, phone=%s, role=%s, department=%s, profile_image=%s, status=%s
                WHERE id = %s
            """, (data['full_name'], data['email'], data['phone'], data['role'], data['department'], data['profile_image'], data['status'], member_id))
        else:
            cur.execute("""
                UPDATE admin_team SET full_name=%s, email=%s, phone=%s, role=%s, department=%s, status=%s
                WHERE id = %s
            """, (data['full_name'], data['email'], data['phone'], data['role'], data['department'], data['status'], member_id))
        self.mysql.connection.commit()
        cur.close()

    def update_status(self, member_id, status):
        cur = self.mysql.connection.cursor()
        cur.execute("UPDATE admin_team SET status=%s WHERE id=%s", (status, member_id))
        self.mysql.connection.commit()
        cur.close()

    def get_stats(self):
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) as total FROM admin_team")
        total = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as active FROM admin_team WHERE status='Active'")
        active = cur.fetchone()['active']
        cur.execute("SELECT COUNT(*) as inactive FROM admin_team WHERE status='Inactive'")
        inactive = cur.fetchone()['inactive']
        cur.close()
        return {'total': total, 'active': active, 'inactive': inactive}

