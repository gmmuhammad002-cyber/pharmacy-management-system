import os
from datetime import datetime

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
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)

database_url = os.getenv(
    "DATABASE_URL",
    "sqlite:///pharmacy.db"
)

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


# =========================================================
# LOGIN
# =========================================================

login_manager = LoginManager(app)

login_manager.login_view = "login"
login_manager.login_message = "Please log in first."
login_manager.login_message_category = "warning"


# =========================================================
# USER
# =========================================================

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
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

    sales = db.relationship(
        "Sale",
        backref="seller",
        lazy=True
    )

    orders = db.relationship(
        "Order",
        backref="customer",
        lazy=True
    )

    def set_password(self, password):

        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):

        return check_password_hash(
            self.password_hash,
            password
        )


# =========================================================
# MEDICINE
# =========================================================

class Medicine(db.Model):

    __tablename__ = "medicines"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    category = db.Column(
        db.String(100)
    )

    barcode = db.Column(
        db.String(100),
        unique=True
    )

    quantity = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    purchase_price = db.Column(
        db.Float,
        default=0
    )

    selling_price = db.Column(
        db.Float,
        default=0
    )

    expiry_date = db.Column(
        db.Date
    )

    sales = db.relationship(
        "Sale",
        backref="medicine",
        lazy=True
    )

    order_items = db.relationship(
        "OrderItem",
        backref="medicine",
        lazy=True
    )


# =========================================================
# SALE
# =========================================================

class Sale(db.Model):

    __tablename__ = "sales"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicines.id"),
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

    sale_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    sold_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )


# =========================================================
# ACTIVITY LOG
# =========================================================

class ActivityLog(db.Model):

    __tablename__ = "activity_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    action = db.Column(
        db.String(255),
        nullable=False
    )

    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="activity_logs"
    )


# =========================================================
# ORDER
# =========================================================

class Order(db.Model):

    __tablename__ = "orders"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    total_price = db.Column(
        db.Float,
        default=0,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    items = db.relationship(
        "OrderItem",
        backref="order",
        lazy=True,
        cascade="all, delete-orphan"
    )


# =========================================================
# ORDER ITEM
# =========================================================

class OrderItem(db.Model):

    __tablename__ = "order_items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicines.id"),
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


# =========================================================
# LOGIN USER LOADER
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id)
        )

    except (TypeError, ValueError):

        return None


# =========================================================
# ACTIVITY LOG
# =========================================================

def log_activity(action):

    if not current_user.is_authenticated:
        return

    try:

        log = ActivityLog(
            user_id=current_user.id,
            action=action
        )

        db.session.add(log)
        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "ACTIVITY LOG ERROR:",
            repr(e)
        )


# =========================================================
# ADMIN CHECK
# =========================================================

def admin_required():

    return (
        current_user.is_authenticated
        and current_user.role == "admin"
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    db.create_all()

    admin = User.query.filter_by(
        username="admin"
    ).first()

    if admin is None:

        initial_password = os.getenv(
            "INITIAL_ADMIN_PASSWORD"
        )

        if initial_password:

            admin = User(
                username="admin",
                role="admin"
            )

            admin.set_password(
                initial_password
            )

            db.session.add(admin)
            db.session.commit()

            print("ADMIN USER CREATED")

        else:

            print(
                "WARNING: INITIAL_ADMIN_PASSWORD is not set."
            )

    reset_password = os.getenv(
        "RESET_ADMIN_PASSWORD",
        ""
    ).strip()

    if reset_password and admin:

        admin.set_password(
            reset_password
        )

        db.session.commit()

        print(
            "ADMIN PASSWORD RESET SUCCESS"
        )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def index():

    medicine_count = Medicine.query.count()

    total_stock = db.session.query(
        db.func.coalesce(
            db.func.sum(Medicine.quantity),
            0
        )
    ).scalar()

    sales_count = Sale.query.count()

    today = datetime.utcnow().date()

    today_sales = db.session.query(
        db.func.coalesce(
            db.func.sum(Sale.total_price),
            0
        )
    ).filter(
        db.func.date(Sale.sale_date) == today
    ).scalar()

    low_stock = Medicine.query.filter(
        Medicine.quantity <= 10
    ).count()

    expiring_soon = Medicine.query.filter(
        Medicine.expiry_date.isnot(None),
        Medicine.expiry_date <= today
    ).count()

    recent_sales = (
        Sale.query
        .order_by(
            Sale.sale_date.desc()
        )
        .limit(5)
        .all()
    )

    pending_orders = Order.query.filter_by(
        status="Pending"
    ).count()

    return render_template(
        "index.html",
        total_medicines=medicine_count,
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

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

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

        user = User.query.filter_by(
            username=username
        ).first()

        if user and user.check_password(password):

            login_user(user)

            log_activity(
                "Logged in"
            )

            flash(
                "Login successful.",
                "success"
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


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
@login_required
def logout():

    log_activity(
        "Logged out"
    )

    logout_user()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# MEDICINES
# =========================================================

@app.route("/medicines")
def medicines():

    search = request.args.get(
        "search",
        ""
    ).strip()

    query = Medicine.query

    if search:

        query = query.filter(
            db.or_(
                Medicine.name.ilike(
                    f"%{search}%"
                ),
                Medicine.barcode.ilike(
                    f"%{search}%"
                ),
                Medicine.category.ilike(
                    f"%{search}%"
                )
            )
        )

    medicines_list = (
        query
        .order_by(
            Medicine.name
        )
        .all()
    )

    return render_template(
        "medicines.html",
        medicines=medicines_list,
        search=search
    )


# =========================================================
# ADD MEDICINE
# =========================================================

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

        category = request.form.get(
            "category",
            ""
        ).strip()

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        try:

            quantity = int(
                request.form.get(
                    "quantity",
                    "0"
                )
            )

            purchase_price = float(
                request.form.get(
                    "purchase_price",
                    "0"
                )
            )

            selling_price = float(
                request.form.get(
                    "selling_price",
                    "0"
                )
            )

        except (TypeError, ValueError):

            flash(
                "Invalid quantity or price.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        expiry_date_text = request.form.get(
            "expiry_date",
            ""
        ).strip()

        if not name:

            flash(
                "Medicine name is required.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        if quantity < 0:

            flash(
                "Quantity cannot be negative.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        if purchase_price < 0 or selling_price < 0:

            flash(
                "Price cannot be negative.",
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
                    "This barcode already exists.",
                    "danger"
                )

                return redirect(
                    url_for("add_medicine")
                )

        expiry_date = None

        if expiry_date_text:

            try:

                expiry_date = datetime.strptime(
                    expiry_date_text,
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

        medicine = Medicine(
            name=name,
            category=category or None,
            barcode=barcode or None,
            quantity=quantity,
            purchase_price=purchase_price,
            selling_price=selling_price,
            expiry_date=expiry_date
        )

        try:

            db.session.add(
                medicine
            )

            db.session.commit()

            log_activity(
                f"Added medicine: {name}"
            )

            flash(
                "Medicine added successfully.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "ADD MEDICINE ERROR:",
                repr(e)
            )

            flash(
                "Could not add medicine.",
                "danger"
            )

        return redirect(
            url_for("medicines")
        )

    return render_template(
        "add_medicine.html"
    )


# =========================================================
# EDIT MEDICINE
# =========================================================

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

        category = request.form.get(
            "category",
            ""
        ).strip()

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        try:

            quantity = int(
                request.form.get(
                    "quantity",
                    "0"
                )
            )

            purchase_price = float(
                request.form.get(
                    "purchase_price",
                    "0"
                )
            )

            selling_price = float(
                request.form.get(
                    "selling_price",
                    "0"
                )
            )

        except (TypeError, ValueError):

            flash(
                "Invalid quantity or price.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        expiry_date_text = request.form.get(
            "expiry_date",
            ""
        ).strip()

        if not name:

            flash(
                "Medicine name is required.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        if quantity < 0:

            flash(
                "Quantity cannot be negative.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        if purchase_price < 0 or selling_price < 0:

            flash(
                "Price cannot be negative.",
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
                Medicine.id != medicine.id
            ).first()

            if existing:

                flash(
                    "This barcode already exists.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_medicine",
                        id=id
                    )
                )

        expiry_date = None

        if expiry_date_text:

            try:

                expiry_date = datetime.strptime(
                    expiry_date_text,
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
        medicine.category = category or None
        medicine.barcode = barcode or None
        medicine.quantity = quantity
        medicine.purchase_price = purchase_price
        medicine.selling_price = selling_price
        medicine.expiry_date = expiry_date

        try:

            db.session.commit()

            log_activity(
                f"Updated medicine: {name}"
            )

            flash(
                "Medicine updated successfully.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "EDIT MEDICINE ERROR:",
                repr(e)
            )

            flash(
                "Could not update medicine.",
                "danger"
            )

        return redirect(
            url_for("medicines")
        )

    return render_template(
        "edit_medicine.html",
        medicine=medicine
    )


# =========================================================
# DELETE MEDICINE
# =========================================================

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

    if Sale.query.filter_by(
        medicine_id=medicine.id
    ).first():

        flash(
            "This medicine cannot be deleted.",
            "warning"
        )

        return redirect(
            url_for("medicines")
        )

    medicine_name = medicine.name

    try:

        db.session.delete(
            medicine
        )

        db.session.commit()

        log_activity(
            f"Deleted medicine: {medicine_name}"
        )

        flash(
            "Medicine deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            "DELETE MEDICINE ERROR:",
            repr(e)
        )

        flash(
            "Could not delete medicine.",
            "danger"
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
def sales():

    search = request.args.get(
        "search",
        ""
    ).strip()

    if request.method == "POST":

        if not current_user.is_authenticated:

            flash(
                "Please log in to make a sale.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        try:

            medicine_id = int(
                request.form.get(
                    "medicine_id"
                )
            )

            quantity = int(
                request.form.get(
                    "quantity"
                )
            )

        except (TypeError, ValueError):

            flash(
                "Invalid sale information.",
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

        if medicine.quantity < quantity:

            flash(
                "Not enough stock available.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        total_price = (
            float(medicine.selling_price or 0)
            * quantity
        )

        medicine.quantity -= quantity

        sale = Sale(
            medicine_id=medicine.id,
            quantity=quantity,
            total_price=total_price,
            sold_by=current_user.id
        )

        try:

            db.session.add(
                sale
            )

            db.session.commit()

            log_activity(
                f"Sold {quantity} x {medicine.name}"
            )

            flash(
                "Sale completed successfully.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "CREATE SALE ERROR:",
                repr(e)
            )

            flash(
                "Could not complete sale.",
                "danger"
            )

        return redirect(
            url_for("sales")
        )

    if search:

        medicines_list = (
            Medicine.query
            .filter(
                db.or_(
                    Medicine.name.ilike(
                        f"%{search}%"
                    ),
                    Medicine.barcode.ilike(
                        f"%{search}%"
                    ),
                    Medicine.category.ilike(
                        f"%{search}%"
                    )
                )
            )
            .order_by(
                Medicine.name
            )
            .all()
        )

    else:

        medicines_list = (
            Medicine.query
            .order_by(
                Medicine.name
            )
            .all()
        )

    medicines_json = []

    for medicine in medicines_list:

        medicines_json.append(
            {
                "id": medicine.id,
                "name": medicine.name,
                "category": medicine.category or "",
                "barcode": medicine.barcode or "",
                "quantity": medicine.quantity,
                "selling_price": float(
                    medicine.selling_price or 0
                )
            }
        )

    recent_sales = (
        Sale.query
        .order_by(
            Sale.sale_date.desc()
        )
        .limit(10)
        .all()
    )

    return render_template(
        "sales.html",
        medicines=medicines_json,
        recent_sales=recent_sales,
        search=search
    )


# =========================================================
# DELETE SALE
# =========================================================

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

        db.session.delete(
            sale
        )

        db.session.commit()

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
            f"Delete error: "
            f"{type(e).__name__}: "
            f"{str(e)[:300]}",
            "danger"
        )

    return redirect(
        url_for("sales")
    )


# =========================================================
# ORDERS - CUSTOMER
# =========================================================

@app.route(
    "/orders",
    methods=["GET", "POST"]
)
@login_required
def orders():

    if request.method == "POST":

        medicine_id = request.form.get(
            "medicine_id"
        )

        quantity_text = request.form.get(
            "quantity",
            "1"
        )

        try:

            medicine_id = int(
                medicine_id
            )

            quantity = int(
                quantity_text
            )

        except (TypeError, ValueError):

            flash(
                "Invalid order information.",
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

        if medicine.quantity < quantity:

            flash(
                "Not enough stock available.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        total_price = (
            float(medicine.selling_price or 0)
            * quantity
        )

        try:

            order = Order(
                user_id=current_user.id,
                status="Pending",
                total_price=total_price
            )

            db.session.add(
                order
            )

            db.session.flush()

            item = OrderItem(
                order_id=order.id,
                medicine_id=medicine.id,
                quantity=quantity,
                unit_price=float(
                    medicine.selling_price or 0
                ),
                total_price=total_price
            )

            db.session.add(
                item
            )

            db.session.commit()

            log_activity(
                f"Created order #{order.id}"
            )

            flash(
                "Order created successfully.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "CREATE ORDER ERROR:",
                repr(e)
            )

            flash(
                "Could not create order.",
                "danger"
            )

        return redirect(
            url_for("orders")
        )

    medicines_list = (
        Medicine.query
        .filter(
            Medicine.quantity > 0
        )
        .order_by(
            Medicine.name
        )
        .all()
    )

    if admin_required():

        orders_list = (
            Order.query
            .order_by(
                Order.created_at.desc()
            )
            .all()
        )

    else:

        orders_list = (
            Order.query
            .filter_by(
                user_id=current_user.id
            )
            .order_by(
                Order.created_at.desc()
            )
            .all()
        )

    return render_template(
        "orders.html",
        medicines=medicines_list,
        orders=orders_list,
        is_admin=admin_required()
    )


# =========================================================
# UPDATE ORDER STATUS
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

    allowed_statuses = [
        "Pending",
        "Approved",
        "Completed",
        "Cancelled"
    ]

    if new_status not in allowed_statuses:

        flash(
            "Invalid order status.",
            "danger"
        )

        return redirect(
            url_for("orders")
        )

    # -----------------------------------------------------
    # APPROVE ORDER
    # -----------------------------------------------------

    if new_status == "Approved":

        if order.status == "Approved":

            flash(
                "This order is already approved.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        if order.status in [
            "Completed",
            "Cancelled"
        ]:

            flash(
                "This order can no longer be approved.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        try:

            # Check stock for every item first.
            for item in order.items:

                medicine = db.session.get(
                    Medicine,
                    item.medicine_id
                )

                if not medicine:

                    raise ValueError(
                        f"Medicine for order item "
                        f"{item.id} was not found."
                    )

                if medicine.quantity < item.quantity:

                    raise ValueError(
                        f"Not enough stock for "
                        f"{medicine.name}."
                    )

            # Reduce stock only after every item passes.
            for item in order.items:

                medicine = db.session.get(
                    Medicine,
                    item.medicine_id
                )

                medicine.quantity -= item.quantity

            order.status = "Approved"

            db.session.commit()

            log_activity(
                f"Approved order #{order.id}"
            )

            flash(
                f"Order #{order.id} approved.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "APPROVE ORDER ERROR:",
                repr(e)
            )

            flash(
                f"Could not approve order: {str(e)[:300]}",
                "danger"
            )

        return redirect(
            url_for("orders")
        )

    # -----------------------------------------------------
    # CANCEL ORDER
    # -----------------------------------------------------

    if new_status == "Cancelled":

        if order.status == "Cancelled":

            flash(
                "This order is already cancelled.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        if order.status in [
            "Completed"
        ]:

            flash(
                "Completed orders cannot be cancelled.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        try:

            order.status = "Cancelled"

            db.session.commit()

            log_activity(
                f"Cancelled order #{order.id}"
            )

            flash(
                f"Order #{order.id} cancelled.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "CANCEL ORDER ERROR:",
                repr(e)
            )

            flash(
                "Could not cancel order.",
                "danger"
            )

        return redirect(
            url_for("orders")
        )

    # -----------------------------------------------------
    # COMPLETE ORDER
    # -----------------------------------------------------

    if new_status == "Completed":

        if order.status != "Approved":

            flash(
                "Only approved orders can be completed.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        try:

            order.status = "Completed"

            db.session.commit()

            log_activity(
                f"Completed order #{order.id}"
            )

            flash(
                f"Order #{order.id} completed.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "COMPLETE ORDER ERROR:",
                repr(e)
            )

            flash(
                "Could not complete order.",
                "danger"
            )

        return redirect(
            url_for("orders")
        )

    # -----------------------------------------------------
    # PENDING
    # -----------------------------------------------------

    if new_status == "Pending":

        if order.status != "Approved":

            order.status = "Pending"

            try:

                db.session.commit()

                flash(
                    f"Order #{order.id} set to pending.",
                    "success"
                )

            except Exception as e:

                db.session.rollback()

                print(
                    "UPDATE ORDER ERROR:",
                    repr(e)
                )

                flash(
                    "Could not update order.",
                    "danger"
                )

        else:

            flash(
                "An approved order cannot be returned to pending.",
                "warning"
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

    users_list = (
        User.query
        .order_by(
            User.username
        )
        .all()
    )

    return render_template(
        "users.html",
        users=users_list
    )


# =========================================================
# ADD USER
# =========================================================

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
        ).strip().lower()

        if not username:

            flash(
                "Username is required.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        if not password:

            flash(
                "Password is required.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        if role not in [
            "admin",
            "staff"
        ]:

            role = "staff"

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:

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

        user.set_password(
            password
        )

        try:

            db.session.add(
                user
            )

            db.session.commit()

            log_activity(
                f"Added user: {username}"
            )

            flash(
                "User added successfully.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "ADD USER ERROR:",
                repr(e)
            )

            flash(
                "Could not add user.",
                "danger"
            )

        return redirect(
            url_for("users")
        )

    return render_template(
        "add_user.html"
    )


# =========================================================
# DELETE USER
# =========================================================

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

    if user.id == current_user.id:

        flash(
            "You cannot delete your own account.",
            "warning"
        )

        return redirect(
            url_for("users")
        )

    if user.username == "admin":

        flash(
            "The main admin account cannot be deleted.",
            "warning"
        )

        return redirect(
            url_for("users")
        )

    if Sale.query.filter_by(
        sold_by=user.id
    ).first():

        flash(
            "This user cannot be deleted because "
            "they have sales history.",
            "warning"
        )

        return redirect(
            url_for("users")
        )

    if Order.query.filter_by(
        user_id=user.id
    ).first():

        flash(
            "This user cannot be deleted because "
            "they have order history.",
            "warning"
        )

        return redirect(
            url_for("users")
        )

    username = user.username

    try:

        db.session.delete(
            user
        )

        db.session.commit()

        log_activity(
            f"Deleted user: {username}"
        )

        flash(
            "User deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            "DELETE USER ERROR:",
            repr(e)
        )

        flash(
            "Could not delete user.",
            "danger"
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

    logs_list = (
        ActivityLog.query
        .order_by(
            ActivityLog.timestamp.desc()
        )
        .limit(100)
        .all()
    )

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
def internal_error(error):

    db.session.rollback()

    print(
        "500 ERROR:",
        repr(error)
    )

    return render_template(
        "500.html"
    ), 500


# =========================================================
# DATABASE
# =========================================================

with app.app_context():

    initialize_database()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                5000
            )
        ),
        debug=False
    )
