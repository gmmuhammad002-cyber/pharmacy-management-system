import os
from datetime import datetime
from functools import wraps
from decimal import Decimal

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is missing.")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///pharmacy.db"


# =========================================================
# POSTGRESQL DRIVER FIX
# =========================================================

# Render PostgreSQL URLs may start with:
# postgres://
# postgresql://
#
# We explicitly use psycopg 3.

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )

elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = SECRET_KEY

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True
}


# =========================================================
# SESSION SECURITY
# =========================================================

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv(
        "SESSION_COOKIE_SECURE",
        "false"
    ).lower() == "true"
)


# =========================================================
# DATABASE
# =========================================================

db = SQLAlchemy(app)


# =========================================================
# LOGIN MANAGER
# =========================================================

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

login_manager.login_message = "Please log in to access this page."

login_manager.login_message_category = "warning"


# =========================================================
# USER MODEL
# =========================================================

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

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
        nullable=False,
        default="staff"
    )

    is_active_user = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    sales = db.relationship(
        "Sale",
        backref="seller",
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

    @property
    def is_active(self):

        return self.is_active_user


# =========================================================
# MEDICINE MODEL
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

    barcode = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    purchase_price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    selling_price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    expiry_date = db.Column(
        db.Date,
        nullable=True
    )

    sales = db.relationship(
        "Sale",
        backref="medicine",
        lazy=True
    )


# =========================================================
# SALE MODEL
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
        db.Numeric(10, 2),
        nullable=False
    )

    sale_date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    sold_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )


# =========================================================
# ACTIVITY LOG MODEL
# =========================================================

class ActivityLog(db.Model):

    __tablename__ = "activity_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        nullable=False
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
            username=current_user.username,
            action=action
        )

        db.session.add(log)

        db.session.commit()

    except Exception:

        db.session.rollback()


# =========================================================
# ADMIN DECORATOR
# =========================================================

def admin_required(function):

    @wraps(function)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.role != "admin":

            flash(
                "Administrator access required.",
                "danger"
            )

            return redirect(
                url_for("index")
            )

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    if not current_user.is_authenticated:

        return redirect(
            url_for("medicines")
        )

    medicine_count = Medicine.query.count()

    total_stock = db.session.query(
        db.func.coalesce(
            db.func.sum(
                Medicine.quantity
            ),
            0
        )
    ).scalar()

    sales_count = Sale.query.count()

    return render_template(
        "index.html",
        medicine_count=medicine_count,
        total_stock=total_stock,
        sales_count=sales_count
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

            if not user.is_active_user:

                flash(
                    "This account is disabled.",
                    "danger"
                )

                return redirect(
                    url_for("login")
                )

            login_user(user)

            log_activity(
                "Logged in"
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

    return redirect(
        url_for("medicines")
    )


# =========================================================
# PUBLIC MEDICINE LIST
# =========================================================

@app.route("/medicines")
def medicines():

    search = request.args.get(
        "search",
        ""
    ).strip()

    if search:

        medicines_list = Medicine.query.filter(
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
        ).order_by(
            Medicine.name
        ).all()

    else:

        medicines_list = Medicine.query.order_by(
            Medicine.name
        ).all()

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

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        try:

            quantity = int(
                request.form.get(
                    "quantity",
                    "0"
                )
            )

            purchase_price = Decimal(
                request.form.get(
                    "purchase_price",
                    "0"
                )
            )

            selling_price = Decimal(
                request.form.get(
                    "selling_price",
                    "0"
                )
            )

        except Exception:

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
        )

        if not name or not barcode or not category:

            flash(
                "Please fill in all required fields.",
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
                "Prices cannot be negative.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        existing = Medicine.query.filter_by(
            barcode=barcode
        ).first()

        if existing:

            flash(
                "A medicine with this barcode already exists.",
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
            barcode=barcode,
            category=category,
            quantity=quantity,
            purchase_price=purchase_price,
            selling_price=selling_price,
            expiry_date=expiry_date
        )

        db.session.add(medicine)

        db.session.commit()

        log_activity(
            f"Added medicine: {name}"
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


# =========================================================
# EDIT MEDICINE
# =========================================================

@app.route(
    "/medicines/edit/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def edit_medicine(id):

    medicine = db.get_or_404(
        Medicine,
        id
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

        try:

            quantity = int(
                request.form.get(
                    "quantity",
                    "0"
                )
            )

            purchase_price = Decimal(
                request.form.get(
                    "purchase_price",
                    "0"
                )
            )

            selling_price = Decimal(
                request.form.get(
                    "selling_price",
                    "0"
                )
            )

        except Exception:

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
        )

        if not name or not barcode or not category:

            flash(
                "Please fill in all required fields.",
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
                "Prices cannot be negative.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        duplicate = Medicine.query.filter(
            Medicine.barcode == barcode,
            Medicine.id != id
        ).first()

        if duplicate:

            flash(
                "Another medicine already uses this barcode.",
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
        medicine.barcode = barcode
        medicine.category = category
        medicine.quantity = quantity
        medicine.purchase_price = purchase_price
        medicine.selling_price = selling_price
        medicine.expiry_date = expiry_date

        db.session.commit()

        log_activity(
            f"Edited medicine: {name}"
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


# =========================================================
# DELETE MEDICINE
# =========================================================

@app.route(
    "/medicines/delete/<int:id>",
    methods=["POST"]
)
@admin_required
def delete_medicine(id):

    medicine = db.get_or_404(
        Medicine,
        id
    )

    medicine_name = medicine.name

    try:

        db.session.delete(medicine)

        db.session.commit()

        log_activity(
            f"Deleted medicine: {medicine_name}"
        )

        flash(
            "Medicine deleted successfully.",
            "success"
        )

    except Exception:

        db.session.rollback()

        flash(
            "This medicine cannot be deleted.",
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
@login_required
def sales():

    if request.method == "POST":

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
                "Not enough stock.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        total_price = (
            medicine.selling_price * quantity
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
            f"Sold {quantity} x {medicine.name}"
        )

        flash(
            "Sale completed successfully.",
            "success"
        )

        return redirect(
            url_for("sales")
        )

    medicines_list = Medicine.query.order_by(
        Medicine.name
    ).all()

    sales_list = Sale.query.order_by(
        Sale.sale_date.desc()
    ).all()

    return render_template(
        "sales.html",
        medicines=medicines_list,
        sales=sales_list
    )


# =========================================================
# USERS
# =========================================================

@app.route("/users")
@admin_required
def users():

    users_list = User.query.order_by(
        User.username
    ).all()

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
@admin_required
def add_user():

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
        )

        if role not in ["admin", "staff"]:

            role = "staff"

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        if len(password) < 8:

            flash(
                "Password must be at least 8 characters.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

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

        user.set_password(
            password
        )

        db.session.add(user)

        db.session.commit()

        log_activity(
            f"Created user: {username}"
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


# =========================================================
# TOGGLE USER
# =========================================================

@app.route(
    "/users/toggle/<int:id>",
    methods=["POST"]
)
@admin_required
def toggle_user(id):

    user = db.get_or_404(
        User,
        id
    )

    if user.id == current_user.id:

        flash(
            "You cannot disable your own account.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    user.is_active_user = (
        not user.is_active_user
    )

    db.session.commit()

    status = (
        "enabled"
        if user.is_active_user
        else "disabled"
    )

    log_activity(
        f"{status.capitalize()} user: {user.username}"
    )

    flash(
        f"User {user.username} is now {status}.",
        "success"
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# ACTIVITY LOGS
# =========================================================

@app.route("/logs")
@admin_required
def logs():

    logs_list = ActivityLog.query.order_by(
        ActivityLog.created_at.desc()
    ).all()

    return render_template(
        "logs.html",
        logs=logs_list
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    with app.app_context():

        db.create_all()

        if User.query.count() == 0:

            initial_password = os.getenv(
                "INITIAL_ADMIN_PASSWORD"
            )

            if not initial_password:

                raise RuntimeError(
                    "INITIAL_ADMIN_PASSWORD environment variable is missing."
                )

            admin = User(
                username="admin",
                role="admin"
            )

            admin.set_password(
                initial_password
            )

            db.session.add(admin)

            db.session.commit()


# =========================================================
# STARTUP
# =========================================================

initialize_database()


# =========================================================
# LOCAL DEVELOPMENT
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
        debug=True
    )
