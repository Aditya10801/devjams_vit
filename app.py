from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import base64
import io
import string
import qrcode
import base64

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///delivery_system.db"
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    reward_points = db.Column(db.Integer, default=10)
    room_no = db.Column(db.String(20))
    hostel_block = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)


class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    shop_type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    image_url = db.Column(db.String(200))
    items = db.relationship("Item", backref="shop", lazy=True)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    status = db.Column(db.String(20), default="pending")
    delivery_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    item = db.relationship("Item", backref="orders")
    user = db.relationship("User", foreign_keys=[user_id], backref="orders_placed")
    delivery_user = db.relationship(
        "User", foreign_keys=[delivery_user_id], backref="orders_delivered"
    )
    delivery_address = db.Column(db.String(200))
    delivery_fee = db.Column(db.Integer, default=1)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    user = db.relationship("User", backref="cart_items")
    item = db.relationship("Item", backref="cart_items")
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/listing")
def listing():
    shops = Shop.query.all()
    pending_orders = Order.query.filter_by(status="pending").all()
    is_admin = current_user.is_admin if current_user.is_authenticated else False
    return render_template(
        "index.html", shops=shops, orders=pending_orders, is_admin=is_admin
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password) and user.is_admin:
            return redirect(url_for("admin"))

        elif user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("listing"))
        
        else:
            return render_template("login.html", invalid=True)

    return render_template("login.html")


@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        room_no = request.form["room_no"]
        hostel_block = request.form["hostel_block"]

        if password != confirm_password:
            return redirect(url_for("register"))

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            room_no=room_no,
            hostel_block=hostel_block,
            is_admin=False,
        )
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("listing"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


@app.route("/edit_reward_points", methods=["POST"])
@login_required
def edit_reward_points():
    new_points = request.form.get("reward_points", type=int)
    if new_points is not None:
        current_user.reward_points = new_points
        db.session.commit()
    return redirect(url_for("profile"))


@app.route("/create_shop", methods=["GET", "POST"])
@login_required
def create_shop():
    if request.method == "POST":
        name = request.form["name"]
        shop_type = request.form["shop_type"]
        shop = Shop(name=name, shop_type=shop_type, user_id=current_user.id)
        db.session.add(shop)
        db.session.commit()

        # Add initial products
        product_names = request.form.getlist("product_names[]")
        product_prices = request.form.getlist("product_prices[]")
        for name, price in zip(product_names, product_prices):
            if name and price:
                item = Item(name=name, price=float(price), shop_id=shop.id)
                db.session.add(item)

        db.session.commit()
        return redirect(url_for("admin"))
    return render_template("create_shop.html")


@app.route("/shop/<int:shop_id>")
def shop_details(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    items = Item.query.filter_by(shop_id=shop_id).all()
    return render_template("shop_details.html", shop=shop, items=items)


@app.route("/place_order/<int:item_id>", methods=["POST"])
@login_required
def place_order(item_id):
    item = Item.query.get_or_404(item_id)
    if (
        current_user.reward_points >= 1
    ):  # Check if user has enough reward points for delivery
        current_user.reward_points -= 1  # Deduct 1 reward point for delivery
        delivery_address = f"{current_user.room_no}, {current_user.hostel_block}"
        order = Order(
            user_id=current_user.id,
            shop_id=item.shop_id,
            item_id=item.id,
            delivery_address=delivery_address,
        )
        db.session.add(order)
        db.session.commit()
    return redirect(url_for("shop_details", shop_id=item.shop_id))


@app.route("/manage_orders")
@login_required
def manage_orders():
    # Show all pending orders and orders related to the current user
    orders = Order.query.filter(
        (Order.status == "pending")
        | (Order.user_id == current_user.id)
        | (Order.delivery_user_id == current_user.id)
    ).all()
    return render_template("manage_orders.html", orders=orders)


@app.route("/accept_delivery/<int:order_id>", methods=["POST"])
@login_required
def accept_delivery(order_id):
    order = Order.query.get_or_404(order_id)
    # if order.user_id == current_user.id:
    #     flash('You are not allowed to accept this delivery.', 'error')
    # elif order.status != 'pending' or order.delivery_user_id is not None:
    #     flash('This order is no longer available for delivery.', 'error')
    # elif Order.query.filter_by(delivery_user_id=current_user.id, status='in_progress').first():
    #     flash('You can only accept one order at a time.', 'error')
    if (
        (order.user_id != current_user.id)
        and not (order.status != "pending" or order.delivery_user_id is not None)
        and not rder.query.filter_by(
            delivery_user_id=current_user.id, status="in_progress"
        ).first()
    ):
        order.delivery_user_id = current_user.id
        order.status = "in_progress"
        db.session.commit()
        # flash('Delivery accepted!', 'success')
    return redirect(url_for("manage_orders"))


@app.route("/complete_delivery/<int:order_id>", methods=["POST"])
@login_required
def complete_delivery(order_id):
    order = Order.query.get_or_404(order_id)
    # if order.delivery_user_id != current_user.id:
    #     flash('You are not authorized to complete this delivery.', 'error')
    if order.delivery_user_id == current_user.id:
        order.status = "completed"
        current_user.reward_points += 1  # Award 1 reward point to the delivery user
        db.session.commit()
        # flash('Delivery completed! You earned 1 reward point.', 'success')
    return redirect(url_for("manage_orders"))


@app.route("/shop/<int:shop_id>/add_product", methods=["GET", "POST"])
@login_required
def add_product(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    # if shop.user_id != current_user.id:
    #     # flash('You do not have permission to add products to this shop.', 'error')
    #     return redirect(url_for('index'))

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        item = Item(name=name, price=float(price), shop_id=shop.id)
        db.session.add(item)
        db.session.commit()
        # flash('Product added successfully!', 'success')
        return redirect(url_for("shop_details", shop_id=shop.id))

    return render_template("add_product.html", shop=shop)


@app.route("/user")
@login_required
def user():
    return render_template("user.html")


@app.route("/shop")
@login_required
def shop():
    return render_template("shop.html")


@app.route("/store")
@login_required
def store():
    return render_template("store.html")


@app.route("/checkout")
@login_required
def checkout():
    return render_template("checkout.html")


@app.route("/delivery")
@login_required
def delivery():
    return render_template("delivery.html")


@app.route("/add_to_cart/<int:item_id>", methods=["POST"])
@login_required
def add_to_cart(item_id):
    item = Item.query.get_or_404(item_id)
    user_cart = CartItem.query.filter_by(user_id=current_user.id).first()

    if user_cart and user_cart.shop_id != item.shop_id:
        # flash('You can only add items from one shop to your cart. Please clear your cart first.', 'warning')
        return redirect(url_for("shop_details", shop_id=item.shop_id))

    cart_item = CartItem.query.filter_by(
        user_id=current_user.id, item_id=item_id
    ).first()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(
            user_id=current_user.id, item_id=item_id, shop_id=item.shop_id
        )
        db.session.add(cart_item)

    db.session.commit()
    return redirect(url_for("shop_details", shop_id=item.shop_id))


@app.route("/cart")
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.item.price * item.quantity for item in cart_items)
    shop = Shop.query.get(cart_items[0].shop_id) if cart_items else None
    return render_template("cart.html", cart_items=cart_items, total=total, shop=shop)


@app.route("/remove_from_cart/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id, item_id=item_id
    ).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
    return redirect(url_for("cart"))


@app.route("/process_payment", methods=["POST"])
@login_required
def process_payment():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.item.price * item.quantity for item in cart_items)

    # Generate a simple UPI ID (this is a placeholder, use a real UPI ID in production)
    upi_id = f"dashmate{current_user.id}@upi"

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"upi://pay?pa={upi_id}&am={total}&pn=DashMate&tn=Order%20Payment")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert QR code image to base64 string
    buffered = io.BytesIO()
    img.save(buffered)
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

    return render_template(
        "paymentpage.html", qr_code=qr_code_base64, total=total, upi_id=upi_id
    )


@app.route("/order_confirmation/")
@login_required
def order_confirmation():
    return render_template(
        "order_confirmation.html",
        transaction_id=random.randint(1000000000, 999999999999),
    )


def add_sample_data():
    # Check if data already exists
    if Shop.query.first() is not None:
        return

    # Create sample users
    user1 = User(
        username="24BCE2383",
        password_hash=generate_password_hash("Utkarsh"),
        reward_points=10,
        room_no="328",
        hostel_block="Q",
    )
    user2 = User(
        username="24BCE2370",
        password_hash=generate_password_hash("Aditya"),
        reward_points=5,
        room_no="217",
        hostel_block="T",
    )
    user3 = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        reward_points=5,
        room_no="000",
        hostel_block="AA",
        is_admin=True,
    )
    db.session.add_all([user1, user2, user3])
    db.session.commit()

    # Create sample shops
    shops = [
        Shop(
            name="Darling Canteen",
            shop_type="Food",
            image_url="https://fastly.4sqi.net/img/general/600x600/RC1KFl_fDRNv9FWIxwZw5Tuyk75raK9mBAI08f2OqOU.jpg",
        ),
        Shop(
            name="Balaji Store",
            shop_type="Stationary",
            image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSJwB4wQLregfzlVw0eENXM_AF6HaZwGJCglw&s",
        ),
        Shop(
            name="K.C. Foods",
            shop_type="Food",
            image_url="https://content3.jdmagicbox.com/comp/def_content/food-court/02208331ef-food-court-4-rucet.jpg",
        ),
        Shop(
            name="Madras Caffe",
            shop_type="Food",
            image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRVGaEOLyBBF33A-kmRHCDv5e5ZsWmuH7es8Q&s",
        ),
    ]

    db.session.add_all(shops)
    db.session.commit()

    # Create sample items for each shop
    items = [
        Item(name="Dosa", price=30, shop_id=shops[0].id),
        Item(name="Idli", price=20, shop_id=shops[0].id),
        Item(name="Coffee", price=15, shop_id=shops[0].id),
        Item(name="Notebook", price=40, shop_id=shops[1].id),
        Item(name="Pen", price=10, shop_id=shops[1].id),
        Item(name="Pencil", price=5, shop_id=shops[1].id),
        Item(name="Biriyani", price=80, shop_id=shops[2].id),
        Item(name="Fried Rice", price=60, shop_id=shops[2].id),
        Item(name="Filter Coffee", price=20, shop_id=shops[3].id),
        Item(name="Vada", price=15, shop_id=shops[3].id),
    ]

    db.session.add_all(items)
    db.session.commit()

    # Create sample orders
    order1 = Order(
        user_id=user1.id,
        item_id=items[0].id,
        status="pending",
        delivery_address=f"{user1.room_no}, {user1.hostel_block}",
    )
    order2 = Order(
        user_id=user2.id,
        item_id=items[3].id,
        status="pending",
        delivery_address=f"{user2.room_no}, {user2.hostel_block}",
    )

    db.session.add_all([order1, order2])
    db.session.commit()

    print("Sample data added successfully!")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        add_sample_data()
    app.run(debug=True, port=3000)
