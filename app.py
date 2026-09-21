import os
from datetime import date, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash


load_dotenv()

app = Flask(__name__)

# =========================================================
# SECURITY
# =========================================================

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY is not configured.")

database_url = os.environ.get(
    "DATABASE_URL",
    "sqlite:///pharmacy.db"
)

# Some hosting providers may provide postgres://
# instead of postgresql://.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Secure session settings
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Enable this when deployed behind HTTPS.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE",
    "False"
).lower() == "true"


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


# =========================================================
# DATABASE MODELS
# =========================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

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
        server_default=func.now()
    )

    @property
    def is_active(self):
        return self.is_active_user

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


class Medicine(db.Model):
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)

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
        db.String(100)
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
        nullable=False
    )


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)

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
        db.Date,
        nullable=False,
        default=date.today
    )

    sold_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    medicine = db.relationship(
        "Medicine",
        backref="sales"
    )

    user = db.relationship(
        "User",
        backref="sales"
    )


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
        server_default=func.now()
    )


# =========================================================
# LOGIN
# =========================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# =========================================================
# HELPERS
# =========================================================

def log_activity(action):
    username = (
        current_user.username
        if current_user.is_authenticated
        else "system"
    )

    log = ActivityLog(
        username=username,
        action=action
    )

    db.session.add(log)
    db.session.commit()


def admin_required(function):
    @wraps(function)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.role != "admin":
            flash(
                "Administrator access required.",
                "danger"
            )
            return redirect(url_for("index"))

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# INITIAL DATABASE SETUP
# =========================================================

def initialize_database():
    db.create_all()

    # Create default admin only if there are no users.
    if User.query.count() == 0:

        admin = User(
            username="admin",
            role="admin"
        )

        # Development-only initial password.
        # Change it immediately after first login.
        admin.set_password(
            os.environ.get(
                "INITIAL_ADMIN_PASSWORD",
                "ChangeMe123!"
            )
        )

        db.session.add(admin)
        db.session.commit()


with app.app_context():
    initialize_database()


# =========================================================
# LOGIN / LOGOUT
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

        if (
            user
            and user.is_active
            and user.check_password(password)
        ):

            login_user(user)

            log_activity("User logged in")

            return redirect(url_for("index"))

        flash(
            "Invalid username or password.",
            "danger"
        )

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():

    log_activity("User logged out")

    logout_user()

    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def index():

    total_medicines = Medicine.query.count()

    low_stock = Medicine.query.filter(
        Medicine.quantity <= 10
    ).count()

    today_sales = db.session.query(
        func.coalesce(
            func.sum(Sale.total_price),
            0
        )
    ).filter(
        Sale.sale_date == date.today()
    ).scalar()

    today = date.today()
    thirty_days = today + timedelta(days=30)

    expiring_soon = Medicine.query.filter(
        Medicine.expiry_date >= today,
        Medicine.expiry_date <= thirty_days
    ).count()

    return render_template(
        "index.html",
        total_medicines=total_medicines,
        low_stock=low_stock,
        today_sales=today_sales,
        expiring_soon=expiring_soon
    )


# =========================================================
# MEDICINES
# =========================================================

@app.route("/medicines")
@login_required
def medicines():

    search = request.args.get(
        "search",
        ""
    ).strip()

    query = Medicine.query

    if search:
        query = query.filter(
            Medicine.name.ilike(f"%{search}%")
            |
            Medicine.barcode.ilike(f"%{search}%")
        )

    medicines_list = query.order_by(
        Medicine.name
    ).all()

    return render_template(
        "medicines.html",
        medicines=medicines_list,
        search=search
    )


@app.route("/medicines/add", methods=["GET", "POST"])
@login_required
def add_medicine():

    if request.method == "POST":

        medicine = Medicine(
            name=request.form["name"].strip(),
            barcode=request.form["barcode"].strip(),
            category=request.form.get(
                "category",
                ""
            ).strip(),
            quantity=int(
                request.form["quantity"]
            ),
            purchase_price=float(
                request.form["purchase_price"]
            ),
            selling_price=float(
                request.form["selling_price"]
            ),
            expiry_date=date.fromisoformat(
                request.form["expiry_date"]
            )
        )

        db.session.add(medicine)
        db.session.commit()

        log_activity(
            f"Added medicine: {medicine.name}"
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
    "/medicines/edit/<int:medicine_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_medicine(medicine_id):

    medicine = db.get_or_404(
        Medicine,
        medicine_id
    )

    if request.method == "POST":

        medicine.name = request.form[
            "name"
        ].strip()

        medicine.barcode = request.form[
            "barcode"
        ].strip()

        medicine.category = request.form.get(
            "category",
            ""
        ).strip()

        medicine.quantity = int(
            request.form["quantity"]
        )

        medicine.purchase_price = float(
            request.form["purchase_price"]
        )

        medicine.selling_price = float(
            request.form["selling_price"]
        )

        medicine.expiry_date = date.fromisoformat(
            request.form["expiry_date"]
        )

        db.session.commit()

        log_activity(
            f"Updated medicine: {medicine.name}"
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
    "/medicines/delete/<int:medicine_id>",
    methods=["POST"]
)
@admin_required
def delete_medicine(medicine_id):

    medicine = db.get_or_404(
        Medicine,
        medicine_id
    )

    name = medicine.name

    db.session.delete(medicine)
    db.session.commit()

    log_activity(
        f"Deleted medicine: {name}"
    )

    flash(
        "Medicine deleted.",
        "success"
    )

    return redirect(
        url_for("medicines")
    )


# =========================================================
# SALES
# =========================================================

@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():

    if request.method == "POST":

        medicine_id = int(
            request.form["medicine_id"]
        )

        quantity = int(
            request.form["quantity"]
        )

        medicine = db.get_or_404(
            Medicine,
            medicine_id
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

        total = (
            float(medicine.selling_price)
            * quantity
        )

        medicine.quantity -= quantity

        sale = Sale(
            medicine_id=medicine.id,
            quantity=quantity,
            total_price=total,
            sale_date=date.today(),
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

    recent_sales = Sale.query.order_by(
        Sale.id.desc()
    ).limit(20).all()

    return render_template(
        "sales.html",
        medicines=medicines_list,
        sales=recent_sales
    )


# =========================================================
# USER MANAGEMENT
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


@app.route(
    "/users/add",
    methods=["POST"]
)
@admin_required
def add_user():

    username = request.form[
        "username"
    ].strip()

    password = request.form[
        "password"
    ]

    role = request.form.get(
        "role",
        "staff"
    )

    if role not in ["admin", "staff"]:
        role = "staff"

    if User.query.filter_by(
        username=username
    ).first():

        flash(
            "Username already exists.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    user = User(
        username=username,
        role=role
    )

    user.set_password(password)

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


@app.route(
    "/users/toggle/<int:user_id>",
    methods=["POST"]
)
@admin_required
def toggle_user(user_id):

    user = db.get_or_404(
        User,
        user_id
    )

    if user.id == current_user.id:
        flash(
            "You cannot deactivate your own account.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    user.is_active_user = (
        not user.is_active_user
    )

    db.session.commit()

    log_activity(
        f"Changed account status: {user.username}"
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
        ActivityLog.id.desc()
    ).limit(200).all()

    return render_template(
        "logs.html",
        logs=logs_list
    )


# =========================================================
# PRODUCTION
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )