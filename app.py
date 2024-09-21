from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import qrcode
import base64
import io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///delivery_system.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    reward_points = db.Column(db.Integer, default=10)
    room_no = db.Column(db.String(20))
    hostel_block = db.Column(db.String(20))

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    shop_type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    image_url = db.Column(db.String(200))
    items = db.relationship('Item', backref='shop', lazy=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    delivery_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    item = db.relationship('Item', backref='orders')
    user = db.relationship('User', foreign_keys=[user_id], backref='orders_placed')
    delivery_user = db.relationship('User', foreign_keys=[delivery_user_id], backref='orders_delivered')
    delivery_address = db.Column(db.String(200))
    delivery_fee = db.Column(db.Integer, default=1)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    user = db.relationship('User', backref='cart_items')
    item = db.relationship('Item', backref='cart_items')
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        room_no = request.form['room_no']
        hostel_block = request.form['hostel_block']
        is_shop = 'is_shop' in request.form
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        user = User(username=username, password_hash=generate_password_hash(password), 
                    is_shop=False, room_no=room_no, hostel_block=hostel_block)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/create_shop', methods=['GET', 'POST'])
@login_required
def create_shop():
    if request.method == 'POST':
        name = request.form['name']
        shop_type = request.form['shop_type']
        shop = Shop(name=name, shop_type=shop_type, user_id=current_user.id)
        db.session.add(shop)
        db.session.commit()

        # Add initial products
        product_names = request.form.getlist('product_names[]')
        product_prices = request.form.getlist('product_prices[]')
        for name, price in zip(product_names, product_prices):
            if name and price:
                item = Item(name=name, price=float(price), shop_id=shop.id)
                db.session.add(item)
        
        db.session.commit()
        flash('Shop created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('create_shop.html')

@app.route('/user')
@login_required
def user():
    return render_template('user.html')

@app.route('/shop')
@login_required
def shop():
    return render_template('shop.html')

@app.route('/store')
@login_required
def store():
    return render_template('store.html')

@app.route('/checkout')
@login_required
def checkout():
    return render_template('checkout.html')

@app.route('/delivery')
@login_required
def delivery():
    return render_template('delivery.html')


@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.item.price * item.quantity for item in cart_items)
    shop = Shop.query.get(cart_items[0].shop_id) if cart_items else None
    return render_template('cart.html', cart_items=cart_items, total=total, shop=shop)

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart successfully!', 'success')
    return redirect(url_for('cart'))

@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.item.price * item.quantity for item in cart_items)
    
    upi_id = f"dashmate@upi"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"upi://pay?pa={upi_id}&am={total}&pn=DashMate&tn=Order%20Payment")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR code image to base64 string
    buffered = io.BytesIO()
    img.save(buffered)
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('paymentpage.html', qr_code=qr_code_base64, total=total, upi_id=upi_id)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        add_sample_data()
    app.run(debug=True, port=3000)