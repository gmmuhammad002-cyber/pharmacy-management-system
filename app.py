import os
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# --------------------------------------------------
# ENVIRONMENT
# --------------------------------------------------

load_dotenv()

secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    raise RuntimeError("SECRET_KEY is not set.")

database_url = os.getenv("DATABASE_URL", "sqlite:///pharmacy.db")

# Render/PostgreSQL sometimes provides postgresql://
# We use psycopg 3 explicitly.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )

elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


# --------------------------------------------------
# FLASK APP
# --------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

db = SQLAlchemy(app)


# --------------------------------------------------
# LOGIN MANAGER
# --------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# --------------------------------------------------
# MODELS
# --------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="staff",
    )

    is_active_user = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    sales = db.relationship(
        "Sale",
        backref="seller",
        lazy=True,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password,
        )

    def is_active(self):
        return self.is_active_user


class Medicine(db.Model):
    __tablename__ = "medicines"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    name = db.Column(
        db.String(150),
        nullable=False,
    )

    barcode = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
    )

    category = db.Column(
        db.String(100),
        nullable=False,
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    purchase_price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    selling_price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    expiry_date = db.Column(
        db.Date,
        nullable=False,
    )

    sales = db.relationship(
        "Sale",
        backref="medicine",
        lazy=True,
    )


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicines.id"),
        nullable=False,
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
    )

    total_price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    sale_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    sold_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    username = db.Column(
        db.String(80),
        nullable=False,
    )

    action = db.Column(
        db.String(255),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )


# --------------------------------------------------
# LOGIN USER LOADER
# --------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(
        User,
        int(user_id),
    )


# --------------------------------------------------
# ACTIVITY LOG
# --------------------------------------------------

def log_activity(action):
    if current_user.is_authenticated:
        log = ActivityLog(
            username=current_user.username,
            action=action,
        )

        db.session.add(log)
        db.session.commit()


# --------------------------------------------------
# ADMIN REQUIRED
# --------------------------------------------------

def admin_required(function):
    @wraps(function)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.role != "admin":
            flash(
                "Admin access required.",
                "danger",
            )

            return redirect(
                url_for("index")
            )

        return function(*args, **kwargs)

    return decorated_function


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        user = User.query.filter_by(
            username=username
        ).first()

        if (
            user
            and user.is_active_user
            and user.check_password(password)
        ):

            login_user(user)

            log_activity(
                "Logged in"
            )

            next_page = request.args.get(
                "next"
            )

            return redirect(
                next_page
                if next_page
                else url_for("index")
            )

        flash(
            "Invalid username or password.",
            "danger",
        )

    return render_template(
        "login.html"
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
@login_required
def logout():

    log_activity(
        "Logged out"
    )

    logout_user()

    return redirect(
        url_for("login")
    )


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/")
@login_required
def index():

    medicine_count = Medicine.query.count()

    total_stock = db.session.query(
        db.func.coalesce(
            db.func.sum(Medicine.quantity),
            0,
        )
    ).scalar()

    total_sales = db.session.query(
        db.func.coalesce(
            db.func.sum(Sale.total_price),
            0,
        )
    ).scalar()

    return render_template(
        "index.html",
        medicine_count=medicine_count,
        total_stock=total_stock,
        total_sales=total_sales,
    )


# --------------------------------------------------
# PUBLIC MEDICINE LIST
# --------------------------------------------------

@app.route("/medicines")
def medicines():

    search = request.args.get(
        "search",
        "",
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
                ),
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
        search=search,
    )


# --------------------------------------------------
# ADD MEDICINE
# LOGIN REQUIRED
# --------------------------------------------------

@app.route(
    "/medicines/add",
    methods=["GET", "POST"],
)
@login_required
def add_medicine():

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        barcode = request.form.get(
            "barcode",
            "",
        ).strip()

        category = request.form.get(
            "category",
            "",
        ).strip()

        quantity = request.form.get(
            "quantity",
            "0",
        )

        purchase_price = request.form.get(
            "purchase_price",
            "0",
        )

        selling_price = request.form.get(
            "selling_price",
            "0",
        )

        expiry_date = request.form.get(
            "expiry_date",
            "",
        )

        if not all(
            [
                name,
                barcode,
                category,
                expiry_date,
            ]
        ):

            flash(
                "Please fill in all required fields.",
                "danger",
            )

            return render_template(
                "add_medicine.html"
            )

        existing = Medicine.query.filter_by(
            barcode=barcode
        ).first()

        if existing:

            flash(
                "A medicine with this barcode already exists.",
                "danger",
            )

            return render_template(
                "add_medicine.html"
            )

        try:

            medicine = Medicine(
                name=name,
                barcode=barcode,
                category=category,
                quantity=int(quantity),
                purchase_price=float(
                    purchase_price
                ),
                selling_price=float(
                    selling_price
                ),
                expiry_date=datetime.strptime(
                    expiry_date,
                    "%Y-%m-%d",
                ).date(),
            )

            db.session.add(medicine)
            db.session.commit()

            log_activity(
                f"Added medicine: {name}"
            )

            flash(
                "Medicine added successfully.",
                "success",
            )

            return redirect(
                url_for("medicines")
            )

        except ValueError:

            flash(
                "Please enter valid values.",
                "danger",
            )

    return render_template(
        "add_medicine.html"
    )


# --------------------------------------------------
# EDIT MEDICINE
# LOGIN REQUIRED
# --------------------------------------------------

@app.route(
    "/medicines/edit/<int:medicine_id>",
    methods=["GET", "POST"],
)
@login_required
def edit_medicine(
    medicine_id
):

    medicine = db.get_or_404(
        Medicine,
        medicine_id,
    )

    if request.method == "POST":

        medicine.name = request.form.get(
            "name",
            "",
        ).strip()

        medicine.barcode = request.form.get(
            "barcode",
            "",
        ).strip()

        medicine.category = request.form.get(
            "category",
            "",
        ).strip()

        try:

            medicine.quantity = int(
                request.form.get(
                    "quantity",
                    "0",
                )
            )

            medicine.purchase_price = float(
                request.form.get(
                    "purchase_price",
                    "0",
                )
            )

            medicine.selling_price = float(
                request.form.get(
                    "selling_price",
                    "0",
                )
            )

            medicine.expiry_date = datetime.strptime(
                request.form.get(
                    "expiry_date"
                ),
                "%Y-%m-%d",
            ).date()

            db.session.commit()

            log_activity(
                f"Edited medicine: {medicine.name}"
            )

            flash(
                "Medicine updated successfully.",
                "success",
            )

            return redirect(
                url_for("medicines")
            )

        except ValueError:

            db.session.rollback()

            flash(
                "Please enter valid values.",
                "danger",
            )

    return render_template(
        "edit_medicine.html",
        medicine=medicine,
    )


# --------------------------------------------------
# DELETE MEDICINE
# ADMIN ONLY
# --------------------------------------------------

@app.route(
    "/medicines/delete/<int:medicine_id>",
    methods=["POST"],
)
@admin_required
def delete_medicine(
    medicine_id
):

    medicine = db.get_or_404(
        Medicine,
        medicine_id,
    )

    name = medicine.name

    try:

        db.session.delete(medicine)
        db.session.commit()

        log_activity(
            f"Deleted medicine: {name}"
        )

        flash(
            "Medicine deleted successfully.",
            "success",
        )

    except Exception:

        db.session.rollback()

        flash(
            "This medicine cannot be deleted because it has sales records.",
            "danger",
        )

    return redirect(
        url_for("medicines")
    )


# --------------------------------------------------
# SALES
# LOGIN REQUIRED
# --------------------------------------------------

@app.route(
    "/sales",
    methods=["GET", "POST"],
)
@login_required
def sales():

    medicines_list = Medicine.query.order_by(
        Medicine.name
    ).all()

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

            medicine = db.get_or_404(
                Medicine,
                medicine_id,
            )

            if quantity <= 0:

                flash(
                    "Quantity must be greater than zero.",
                    "danger",
                )

                return redirect(
                    url_for("sales")
                )

            if medicine.quantity < quantity:

                flash(
                    "Not enough stock.",
                    "danger",
                )

                return redirect(
                    url_for("sales")
                )

            total_price = (
                medicine.selling_price
                * quantity
            )

            medicine.quantity -= quantity

            sale = Sale(
                medicine_id=medicine.id,
                quantity=quantity,
                total_price=total_price,
                sold_by=current_user.id,
            )

            db.session.add(sale)
            db.session.commit()

            log_activity(
                f"Recorded sale: {medicine.name} x {quantity}"
            )

            flash(
                "Sale recorded successfully.",
                "success",
            )

            return redirect(
                url_for("sales")
            )

        except (
            ValueError,
            TypeError,
        ):

            flash(
                "Please enter valid sale information.",
                "danger",
            )

    sales_list = Sale.query.order_by(
        Sale.sale_date.desc()
    ).all()

    return render_template(
        "sales.html",
        medicines=medicines_list,
        sales=sales_list,
    )


# --------------------------------------------------
# USERS
# ADMIN ONLY
# --------------------------------------------------

@app.route("/users")
@admin_required
def users():

    users_list = User.query.order_by(
        User.username
    ).all()

    return render_template(
        "users.html",
        users=users_list,
    )


# --------------------------------------------------
# ADD USER
# ADMIN ONLY
# --------------------------------------------------

@app.route(
    "/users/add",
    methods=["GET", "POST"],
)
@admin_required
def add_user():

    if request.method == "POST":

        username = request.form.get(
            "username",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        role = request.form.get(
            "role",
            "staff",
        )

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger",
            )

            return render_template(
                "add_user.html"
            )

        existing = User.query.filter_by(
            username=username
        ).first()

        if existing:

            flash(
                "Username already exists.",
                "danger",
            )

            return render_template(
                "add_user.html"
            )

        if role not in [
            "admin",
            "staff",
        ]:

            role = "staff"

        user = User(
            username=username,
            role=role,
            is_active_user=True,
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
            "success",
        )

        return redirect(
            url_for("users")
        )

    return render_template(
        "add_user.html"
    )


# --------------------------------------------------
# TOGGLE USER
# ADMIN ONLY
# --------------------------------------------------

@app.route(
    "/users/toggle/<int:user_id>",
    methods=["POST"],
)
@admin_required
def toggle_user(
    user_id
):

    user = db.get_or_404(
        User,
        user_id,
    )

    if user.id == current_user.id:

        flash(
            "You cannot disable your own account.",
            "danger",
        )

        return redirect(
            url_for("users")
        )

    user.is_active_user = (
        not user.is_active_user
    )

    db.session.commit()

    status = (
        "activated"
        if user.is_active_user
        else "disabled"
    )

    log_activity(
        f"{status.capitalize()} user: {user.username}"
    )

    flash(
        f"User {status} successfully.",
        "success",
    )

    return redirect(
        url_for("users")
    )


# --------------------------------------------------
# ACTIVITY LOGS
# ADMIN ONLY
# --------------------------------------------------

@app.route("/logs")
@admin_required
def logs():

    logs_list = ActivityLog.query.order_by(
        ActivityLog.created_at.desc()
    ).all()

    return render_template(
        "logs.html",
        logs=logs_list,
    )


# --------------------------------------------------
# INITIAL DATABASE SETUP
# --------------------------------------------------

def initialize_database():

    with app.app_context():

        db.create_all()

        if User.query.count() == 0:

            initial_password = os.getenv(
                "INITIAL_ADMIN_PASSWORD"
            )

            if not initial_password:

                raise RuntimeError(
                    "INITIAL_ADMIN_PASSWORD is not set."
                )

            admin = User(
                username="admin",
                role="admin",
                is_active_user=True,
            )

            admin.set_password(
                initial_password
            )

            db.session.add(admin)
            db.session.commit()


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

initialize_database()


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )