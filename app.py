import os
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)

database_url = os.getenv("DATABASE_URL", "").strip()

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )
elif database_url.startswith("postgresql+psycopg2://"):
    database_url = database_url.replace(
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# =========================================================
# MODELS
# =========================================================

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="staff",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


class Medicine(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    barcode = db.Column(
        db.String(100),
        unique=True,
        nullable=True
    )

    category = db.Column(
        db.String(100),
        nullable=True
    )

    price = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    expiry_date = db.Column(
        db.Date,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Sale(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicine.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    total_price = db.Column(
        db.Float,
        nullable=False
    )

    sold_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    medicine = db.relationship(
        "Medicine",
        backref="sales"
    )

    user = db.relationship(
        "User",
        backref="sales"
    )


class Order(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    customer_name = db.Column(
        db.String(150),
        nullable=False
    )

    customer_phone = db.Column(
        db.String(50),
        nullable=False
    )

    customer_address = db.Column(
        db.Text,
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="Pending",
        nullable=False
    )

    total_price = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan"
    )


class OrderItem(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("order.id"),
        nullable=False
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicine.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    unit_price = db.Column(
        db.Float,
        nullable=False
    )

    total_price = db.Column(
        db.Float,
        nullable=False
    )

    medicine = db.relationship(
        "Medicine",
        backref="order_items"
    )


class ActivityLog(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        nullable=True
    )

    action = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# LOGIN
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


# =========================================================
# HELPERS
# =========================================================

def admin_required():

    return (
        current_user.is_authenticated
        and current_user.role == "admin"
    )


def log_activity(action):

    try:

        username = (
            current_user.username
            if current_user.is_authenticated
            else "Public"
        )

        log = ActivityLog(
            username=username,
            action=action
        )

        db.session.add(log)
        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print("ACTIVITY LOG ERROR")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    try:

        db.create_all()

        admin = User.query.filter_by(
            username="admin"
        ).first()

        if admin is None:

            initial_password = os.getenv(
                "INITIAL_ADMIN_PASSWORD"
            )

            if not initial_password:
                initial_password = "admin123"

            admin = User(
                username="admin",
                role="admin"
            )

            admin.set_password(initial_password)

            db.session.add(admin)
            db.session.commit()

            print("ADMIN USER CREATED")

        reset_password = os.getenv(
            "RESET_ADMIN_PASSWORD",
            ""
        ).strip()

        if reset_password:

            admin.set_password(reset_password)

            db.session.commit()

            print("ADMIN PASSWORD RESET SUCCESS")

    except Exception as e:

        db.session.rollback()

        print("================================")
        print("DATABASE INITIALIZATION ERROR")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))
        print("================================")


with app.app_context():
    initialize_database()


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
def index():

    medicine_count = Medicine.query.count()

    total_stock = db.session.query(
        db.func.coalesce(
            db.func.sum(Medicine.quantity),
            0
        )
    ).scalar()

    sales_count = Sale.query.count()

    today_start = datetime.combine(
        date.today(),
        datetime.min.time()
    )

    today_sales = db.session.query(
        db.func.coalesce(
            db.func.sum(Sale.total_price),
            0
        )
    ).filter(
        Sale.created_at >= today_start
    ).scalar()

    low_stock = Medicine.query.filter(
        Medicine.quantity <= 10
    ).count()

    expiring_date = date.today() + timedelta(days=30)

    expiring_soon = Medicine.query.filter(
        Medicine.expiry_date.isnot(None),
        Medicine.expiry_date <= expiring_date,
        Medicine.expiry_date >= date.today()
    ).count()

    recent_sales = Sale.query.order_by(
        Sale.created_at.desc()
    ).limit(10).all()

    pending_orders = Order.query.filter_by(
        status="Pending"
    ).count()

    return render_template(
        "index.html",
        medicine_count=medicine_count,
        total_stock=total_stock,
        sales_count=sales_count,
        today_sales=today_sales,
        low_stock=low_stock,
        expiring_soon=expiring_soon,
        recent_sales=recent_sales,
        pending_orders=pending_orders
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            username=username
        ).first()

        if user and user.check_password(password):

            login_user(user)

            log_activity(
                "User logged in"
            )

            return redirect(
                url_for("index")
            )

        flash(
            "Invalid username or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


@app.route("/logout")
@login_required
def logout():

    username = current_user.username

    log_activity(
        f"User logged out: {username}"
    )

    logout_user()

    return redirect(
        url_for("login")
    )


# =========================================================
# MEDICINES
# =========================================================

@app.route("/medicines")
def medicines():

    medicines = Medicine.query.order_by(
        Medicine.name.asc()
    ).all()

    return render_template(
        "medicines.html",
        medicines=medicines
    )


@app.route(
    "/medicines/add",
    methods=["GET", "POST"]
)
@login_required
def add_medicine():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        price_raw = request.form.get(
            "price",
            "0"
        )

        quantity_raw = request.form.get(
            "quantity",
            "0"
        )

        expiry_raw = request.form.get(
            "expiry_date",
            ""
        )

        if not name:

            flash(
                "Medicine name is required.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        try:

            price = float(price_raw)

            quantity = int(quantity_raw)

        except ValueError:

            flash(
                "Price and quantity must be valid numbers.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        expiry_date = None

        if expiry_raw:

            try:

                expiry_date = datetime.strptime(
                    expiry_raw,
                    "%Y-%m-%d"
                ).date()

            except ValueError:

                flash(
                    "Invalid expiry date.",
                    "danger"
                )

                return redirect(
                    url_for("add_medicine")
                )

        if barcode:

            existing = Medicine.query.filter_by(
                barcode=barcode
            ).first()

            if existing:

                flash(
                    "Barcode already exists.",
                    "danger"
                )

                return redirect(
                    url_for("add_medicine")
                )

        medicine = Medicine(
            name=name,
            barcode=barcode or None,
            category=category or None,
            price=price,
            quantity=quantity,
            expiry_date=expiry_date
        )

        db.session.add(medicine)
        db.session.commit()

        log_activity(
            f"Medicine added: {name}"
        )

        flash(
            "Medicine added successfully.",
            "success"
        )

        return redirect(
            url_for("medicines")
        )

    return render_template(
        "add_medicine.html"
    )


@app.route(
    "/medicines/edit/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def edit_medicine(id):

    medicine = db.session.get(
        Medicine,
        id
    )

    if not medicine:

        flash(
            "Medicine not found.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        price_raw = request.form.get(
            "price",
            "0"
        )

        quantity_raw = request.form.get(
            "quantity",
            "0"
        )

        expiry_raw = request.form.get(
            "expiry_date",
            ""
        )

        try:

            price = float(price_raw)

            quantity = int(quantity_raw)

        except ValueError:

            flash(
                "Price and quantity must be valid numbers.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        if barcode:

            existing = Medicine.query.filter(
                Medicine.barcode == barcode,
                Medicine.id != id
            ).first()

            if existing:

                flash(
                    "Barcode already exists.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_medicine",
                        id=id
                    )
                )

        expiry_date = None

        if expiry_raw:

            try:

                expiry_date = datetime.strptime(
                    expiry_raw,
                    "%Y-%m-%d"
                ).date()

            except ValueError:

                flash(
                    "Invalid expiry date.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_medicine",
                        id=id
                    )
                )

        medicine.name = name
        medicine.barcode = barcode or None
        medicine.category = category or None
        medicine.price = price
        medicine.quantity = quantity
        medicine.expiry_date = expiry_date

        db.session.commit()

        log_activity(
            f"Medicine updated: {medicine.name}"
        )

        flash(
            "Medicine updated successfully.",
            "success"
        )

        return redirect(
            url_for("medicines")
        )

    return render_template(
        "edit_medicine.html",
        medicine=medicine
    )


@app.route(
    "/medicines/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_medicine(id):

    medicine = db.session.get(
        Medicine,
        id
    )

    if not medicine:

        flash(
            "Medicine not found.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    existing_sale = Sale.query.filter_by(
        medicine_id=id
    ).first()

    if existing_sale:

        flash(
            "This medicine cannot be deleted because it has sales records.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    existing_order = OrderItem.query.filter_by(
        medicine_id=id
    ).first()

    if existing_order:

        flash(
            "This medicine cannot be deleted because it has order records.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    medicine_name = medicine.name

    db.session.delete(medicine)
    db.session.commit()

    log_activity(
        f"Medicine deleted: {medicine_name}"
    )

    flash(
        "Medicine deleted successfully.",
        "success"
    )

    return redirect(
        url_for("medicines")
    )


# =========================================================
# SALES
# =========================================================

@app.route(
    "/sales",
    methods=["GET", "POST"]
)
@login_required
def sales():

    medicines = Medicine.query.order_by(
        Medicine.name.asc()
    ).all()

    if request.method == "POST":

        medicine_id_raw = request.form.get(
            "medicine_id",
            ""
        )

        quantity_raw = request.form.get(
            "quantity",
            ""
        )

        try:

            medicine_id = int(
                medicine_id_raw
            )

            quantity = int(
                quantity_raw
            )

        except ValueError:

            flash(
                "Please select a medicine and enter a valid quantity.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        medicine = db.session.get(
            Medicine,
            medicine_id
        )

        if not medicine:

            flash(
                "Medicine not found.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        if quantity <= 0:

            flash(
                "Quantity must be greater than zero.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        if quantity > medicine.quantity:

            flash(
                "Not enough stock available.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        total_price = (
            float(medicine.price) * quantity
        )

        medicine.quantity -= quantity

        sale = Sale(
            medicine_id=medicine.id,
            quantity=quantity,
            total_price=total_price,
            sold_by=current_user.id
        )

        db.session.add(sale)

        db.session.commit()

        log_activity(
            f"Sale created: {medicine.name} x {quantity}"
        )

        flash(
            "Sale recorded successfully.",
            "success"
        )

        return redirect(
            url_for("sales")
        )

    recent_sales = Sale.query.order_by(
        Sale.created_at.desc()
    ).limit(10).all()

    return render_template(
        "sales.html",
        medicines=medicines,
        recent_sales=recent_sales
    )


@app.route(
    "/sales/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_sale(id):

    sale = db.session.get(
        Sale,
        id
    )

    if not sale:

        flash(
            "Sale record not found.",
            "danger"
        )

        return redirect(
            url_for("sales")
        )

    medicine = db.session.get(
        Medicine,
        sale.medicine_id
    )

    try:

        sale_quantity = int(
            sale.quantity or 0
        )

        if medicine:

            medicine.quantity = (
                int(medicine.quantity or 0)
                + sale_quantity
            )

        medicine_name = (
            medicine.name
            if medicine
            else "Unknown medicine"
        )

        db.session.delete(sale)

        db.session.commit()

        log_activity(
            f"Sale deleted: {medicine_name} x {sale_quantity}"
        )

        flash(
            "Sale record deleted successfully. "
            "The quantity was returned to stock.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print("================================")
        print("DELETE SALE ERROR")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))
        print("================================")

        flash(
            f"Delete error: {type(e).__name__}: {str(e)[:300]}",
            "danger"
        )

    return redirect(
        url_for("sales")
    )


# =========================================================
# PUBLIC ORDERS
# =========================================================

@app.route(
    "/orders",
    methods=["GET", "POST"]
)
def orders():

    medicines = Medicine.query.order_by(
        Medicine.name.asc()
    ).all()

    if request.method == "POST":

        customer_name = request.form.get(
            "customer_name",
            ""
        ).strip()

        customer_phone = request.form.get(
            "customer_phone",
            ""
        ).strip()

        customer_address = request.form.get(
            "customer_address",
            ""
        ).strip()

        medicine_id_raw = request.form.get(
            "medicine_id",
            ""
        )

        quantity_raw = request.form.get(
            "quantity",
            ""
        )

        if not customer_name:

            flash(
                "Customer name is required.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        if not customer_phone:

            flash(
                "Customer phone is required.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        if not customer_address:

            flash(
                "Customer address is required.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        try:

            medicine_id = int(
                medicine_id_raw
            )

            quantity = int(
                quantity_raw
            )

        except ValueError:

            flash(
                "Please select a medicine and enter a valid quantity.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        medicine = db.session.get(
            Medicine,
            medicine_id
        )

        if not medicine:

            flash(
                "Medicine not found.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        if quantity <= 0:

            flash(
                "Quantity must be greater than zero.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        if quantity > medicine.quantity:

            flash(
                "Requested quantity is not available.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        unit_price = float(
            medicine.price
        )

        total_price = (
            unit_price * quantity
        )

        order = Order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            status="Pending",
            total_price=total_price
        )

        db.session.add(order)

        db.session.flush()

        item = OrderItem(
            order_id=order.id,
            medicine_id=medicine.id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price
        )

        db.session.add(item)

        db.session.commit()

        log_activity(
            f"Public order created: #{order.id}"
        )

        flash(
            f"Order #{order.id} placed successfully.",
            "success"
        )

        return redirect(
            url_for("orders")
        )

    all_orders = []

    if current_user.is_authenticated and admin_required():

        all_orders = Order.query.order_by(
            Order.created_at.desc()
        ).all()

    return render_template(
        "orders.html",
        medicines=medicines,
        orders=all_orders
    )


# =========================================================
# ORDER STATUS
# =========================================================

@app.route(
    "/orders/<int:id>/status",
    methods=["POST"]
)
@login_required
def update_order_status(id):

    if not admin_required():

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("orders")
        )

    order = db.session.get(
        Order,
        id
    )

    if not order:

        flash(
            "Order not found.",
            "danger"
        )

        return redirect(
            url_for("orders")
        )

    new_status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = {
        "Pending",
        "Approved",
        "Completed",
        "Cancelled"
    }

    if new_status not in allowed_statuses:

        flash(
            "Invalid order status.",
            "danger"
        )

        return redirect(
            url_for("orders")
        )

    old_status = order.status

    try:

        # Pending -> Approved
        if (
            old_status == "Pending"
            and new_status == "Approved"
        ):

            for item in order.items:

                medicine = db.session.get(
                    Medicine,
                    item.medicine_id
                )

                if not medicine:

                    raise ValueError(
                        "Medicine for this order no longer exists."
                    )

                if medicine.quantity < item.quantity:

                    raise ValueError(
                        f"Not enough stock for {medicine.name}."
                    )

            for item in order.items:

                medicine = db.session.get(
                    Medicine,
                    item.medicine_id
                )

                medicine.quantity -= item.quantity

        # Cancelled -> Pending
        # No stock change because cancelled orders
        # never reduced stock.

        order.status = new_status

        db.session.commit()

        log_activity(
            f"Order #{order.id} status changed: "
            f"{old_status} -> {new_status}"
        )

        flash(
            f"Order #{order.id} updated to {new_status}.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print("================================")
        print("ORDER STATUS ERROR")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))
        print("================================")

        flash(
            f"Order update error: {str(e)[:300]}",
            "danger"
        )

    return redirect(
        url_for("orders")
    )


# =========================================================
# USERS
# =========================================================

@app.route("/users")
@login_required
def users():

    if not admin_required():

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    all_users = User.query.order_by(
        User.username.asc()
    ).all()

    return render_template(
        "users.html",
        users=all_users
    )


@app.route(
    "/users/add",
    methods=["GET", "POST"]
)
@login_required
def add_user():

    if not admin_required():

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        role = request.form.get(
            "role",
            "staff"
        ).strip()

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        if role not in {
            "admin",
            "staff"
        }:

            role = "staff"

        existing = User.query.filter_by(
            username=username
        ).first()

        if existing:

            flash(
                "Username already exists.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        user = User(
            username=username,
            role=role
        )

        user.set_password(password)

        db.session.add(user)

        db.session.commit()

        log_activity(
            f"User created: {username}"
        )

        flash(
            "User created successfully.",
            "success"
        )

        return redirect(
            url_for("users")
        )

    return render_template(
        "add_user.html"
    )


@app.route(
    "/users/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_user(id):

    if not admin_required():

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    user = db.session.get(
        User,
        id
    )

    if not user:

        flash(
            "User not found.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    if user.username == "admin":

        flash(
            "The main admin account cannot be deleted.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    username = user.username

    db.session.delete(user)

    db.session.commit()

    log_activity(
        f"User deleted: {username}"
    )

    flash(
        "User deleted successfully.",
        "success"
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# ACTIVITY LOGS
# =========================================================

@app.route("/logs")
@login_required
def logs():

    if not admin_required():

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    logs_list = ActivityLog.query.order_by(
        ActivityLog.created_at.desc()
    ).limit(200).all()

    return render_template(
        "logs.html",
        logs=logs_list
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    db.session.rollback()

    return render_template(
        "500.html"
    ), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )