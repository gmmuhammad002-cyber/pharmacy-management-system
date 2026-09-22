import os
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
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

# PostgreSQL URL compatibility
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
# MODELS
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

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


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

    # Create admin if it does not exist
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

            print(
                "ADMIN USER CREATED"
            )

        else:

            print(
                "WARNING: INITIAL_ADMIN_PASSWORD is not set."
            )

    # Optional admin password reset
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

    total_stock = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(Medicine.quantity),
                0
            )
        ).scalar()
    )

    sales_count = Sale.query.count()

    today = datetime.utcnow().date()

    today_sales = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(Sale.total_price),
                0
            )
        )
        .filter(
            db.func.date(
                Sale.sale_date
            ) == today
        )
        .scalar()
    )

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

    return render_template(
        "index.html",
        total_medicines=medicine_count,
        total_stock=total_stock,
        sales_count=sales_count,
        today_sales=today_sales,
        low_stock=low_stock,
        expiring_soon=expiring_soon,
        recent_sales=recent_sales
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

        quantity_text = request.form.get(
            "quantity",
            "0"
        )

        purchase_price_text = request.form.get(
            "purchase_price",
            "0"
        )

        selling_price_text = request.form.get(
            "selling_price",
            "0"
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

        try:

            quantity = int(
                quantity_text
            )

            purchase_price = float(
                purchase_price_text
            )

            selling_price = float(
                selling_price_text
            )

        except (TypeError, ValueError):

            flash(
                "Invalid quantity or price.",
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

            existing_barcode = Medicine.query.filter_by(
                barcode=barcode
            ).first()

            if existing_barcode:

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

        quantity_text = request.form.get(
            "quantity",
            "0"
        )

        purchase_price_text = request.form.get(
            "purchase_price",
            "0"
        )

        selling_price_text = request.form.get(
            "selling_price",
            "0"
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

        try:

            quantity = int(
                quantity_text
            )

            purchase_price = float(
                purchase_price_text
            )

            selling_price = float(
                selling_price_text
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

            existing_barcode = Medicine.query.filter(
                Medicine.barcode == barcode,
                Medicine.id != medicine.id
            ).first()

            if existing_barcode:

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

    # Do not allow deleting medicine
    # if it has sales history.
    existing_sale = Sale.query.filter_by(
        medicine_id=medicine.id
    ).first()

    if existing_sale:

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

    # -----------------------------------------------------
    # CREATE SALE
    # -----------------------------------------------------

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
            medicine.selling_price * quantity
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

    # -----------------------------------------------------
    # MEDICINE SEARCH
    # -----------------------------------------------------

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

    # Convert SQLAlchemy objects
    # into JSON-safe dictionaries.
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

    # -----------------------------------------------------
    # RECENT SALES
    # -----------------------------------------------------

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

    sale_quantity = int(
        sale.quantity or 0
    )

    medicine_name = (
        medicine.name
        if medicine
        else "Unknown medicine"
    )

    # Return the sold quantity to stock.
    if medicine:

        medicine.quantity = (
            int(medicine.quantity or 0)
            + sale_quantity
        )

    activity_text = (
        f"Deleted sale record: "
        f"{sale_quantity} x "
        f"{medicine_name}"
    )

    user_id = current_user.id

    try:

        # Delete sale first.
        db.session.delete(
            sale
        )

        # Make sure the delete is processed
        # before creating the activity log.
        db.session.flush()

        # Add activity log in the same transaction.
        db.session.add(
            ActivityLog(
                user_id=user_id,
                action=activity_text
            )
        )

        # Commit everything together.
        db.session.commit()

        flash(
            "Sale record deleted successfully. "
            "The quantity was returned to stock.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            "DELETE SALE ERROR:",
            repr(e)
        )

        flash(
            "Could not delete sale record.",
            "danger"
        )

    return redirect(
        url_for("sales")
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

    # Prevent deleting yourself.
    if user.id == current_user.id:

        flash(
            "You cannot delete your own account.",
            "warning"
        )

        return redirect(
            url_for("users")
        )

    # Prevent deleting admin account.
    if user.username == "admin":

        flash(
            "The main admin account cannot be deleted.",
            "warning"
        )

        return redirect(
            url_for("users")
        )

    username = user.username

    try:

        # Check if user has sales history.
        user_sales = Sale.query.filter_by(
            sold_by=user.id
        ).first()

        if user_sales:

            flash(
                "This user cannot be deleted because "
                "they have sales history.",
                "warning"
            )

            return redirect(
                url_for("users")
            )

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
# INITIALIZE DATABASE
# =========================================================

with app.app_context():

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
        debug=False
    )
