import os
from datetime import datetime, date, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)

database_url = os.getenv(
    "DATABASE_URL",
    ""
).strip()

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

if not database_url:
    database_url = "sqlite:///pharmacy.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# =========================================================
# CONSTANTS
# =========================================================

STOCK_MOVEMENT_TYPES = {
    "Purchase",
    "Sale",
    "Adjustment",
    "Return",
    "Transfer",
    "Damage",
    "Expiry",
    "Order",
    "Initial Stock"
}

ORDER_STATUSES = {
    "Pending",
    "Approved",
    "Completed",
    "Cancelled"
}

USER_ROLES = {
    "admin",
    "pharmacist",
    "inventory",
    "cashier",
    "viewer"
}


# =========================================================
# MODELS
# =========================================================

class User(UserMixin, db.Model):

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
        db.String(30),
        default="cashier",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
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

    sku = db.Column(
        db.String(100),
        unique=True,
        nullable=True
    )

    generic_name = db.Column(
        db.String(150),
        nullable=True
    )

    brand_name = db.Column(
        db.String(150),
        nullable=True
    )

    category = db.Column(
        db.String(100),
        nullable=True
    )

    dosage_form = db.Column(
        db.String(100),
        nullable=True
    )

    route = db.Column(
        db.String(100),
        nullable=True
    )

    strength = db.Column(
        db.String(100),
        nullable=True
    )

    unit = db.Column(
        db.String(50),
        nullable=True
    )

    manufacturer = db.Column(
        db.String(150),
        nullable=True
    )

    supplier = db.Column(
        db.String(150),
        nullable=True
    )

    price = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    purchase_price = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    minimum_stock = db.Column(
        db.Integer,
        nullable=False,
        default=10
    )

    maximum_stock = db.Column(
        db.Integer,
        nullable=False,
        default=100
    )

    reorder_level = db.Column(
        db.Integer,
        nullable=False,
        default=10
    )

    expiry_date = db.Column(
        db.Date,
        nullable=True
    )

    storage_requirements = db.Column(
        db.String(255),
        nullable=True
    )

    prescription_required = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Batch(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicine.id"),
        nullable=False
    )

    batch_number = db.Column(
        db.String(100),
        nullable=False
    )

    supplier = db.Column(
        db.String(150),
        nullable=True
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    purchase_price = db.Column(
        db.Float,
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

    medicine = db.relationship(
        "Medicine",
        backref=db.backref(
            "batches",
            cascade="all, delete-orphan"
        )
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

    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("batch.id"),
        nullable=True
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

    batch = db.relationship(
        "Batch",
        backref="sales"
    )

    user = db.relationship(
        "User",
        backref="sales"
    )


class StockMovement(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicine.id"),
        nullable=False
    )

    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("batch.id"),
        nullable=True
    )

    movement_type = db.Column(
        db.String(50),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    previous_quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    new_quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    reason = db.Column(
        db.String(255),
        nullable=True
    )

    reference = db.Column(
        db.String(150),
        nullable=True
    )

    username = db.Column(
        db.String(80),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    medicine = db.relationship(
        "Medicine",
        backref="stock_movements"
    )

    batch = db.relationship(
        "Batch",
        backref="stock_movements"
    )


class Supplier(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    phone = db.Column(
        db.String(50),
        nullable=True
    )

    email = db.Column(
        db.String(150),
        nullable=True
    )

    address = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class PurchaseOrder(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("supplier.id"),
        nullable=True
    )

    status = db.Column(
        db.String(50),
        default="Pending",
        nullable=False
    )

    total_price = db.Column(
        db.Float,
        default=0,
        nullable=False
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    supplier = db.relationship(
        "Supplier",
        backref="purchase_orders"
    )

    user = db.relationship(
        "User",
        backref="purchase_orders"
    )

    items = db.relationship(
        "PurchaseOrderItem",
        backref="purchase_order",
        cascade="all, delete-orphan"
    )


class PurchaseOrderItem(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    purchase_order_id = db.Column(
        db.Integer,
        db.ForeignKey("purchase_order.id"),
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
        backref="purchase_items"
    )


class Customer(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    phone = db.Column(
        db.String(50),
        nullable=True
    )

    address = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Prescription(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customer.id"),
        nullable=True
    )

    doctor_name = db.Column(
        db.String(150),
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(50),
        default="Pending",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    customer = db.relationship(
        "Customer",
        backref="prescriptions"
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

        return db.session.get(
            User,
            int(user_id)
        )

    except Exception:

        return None


# =========================================================
# PERMISSION HELPERS
# =========================================================

def admin_required():

    return (
        current_user.is_authenticated
        and current_user.role == "admin"
    )


def can_manage_inventory():

    return (
        current_user.is_authenticated
        and current_user.role in {
            "admin",
            "pharmacist",
            "inventory"
        }
    )


def can_make_sale():

    return (
        current_user.is_authenticated
        and current_user.role in {
            "admin",
            "pharmacist",
            "cashier"
        }
    )


def can_view_inventory():

    return (
        current_user.is_authenticated
        and current_user.role in {
            "admin",
            "pharmacist",
            "inventory",
            "cashier",
            "viewer"
        }
    )


# =========================================================
# LOGGING
# =========================================================

def log_activity(action):

    try:

        username = (
            current_user.username
            if current_user.is_authenticated
            else "Public"
        )

        db.session.add(
            ActivityLog(
                username=username,
                action=action
            )
        )

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "ACTIVITY LOG ERROR:",
            type(e).__name__,
            str(e)
        )


def add_stock_movement(
    medicine,
    movement_type,
    quantity,
    previous_quantity,
    new_quantity,
    reason="",
    reference="",
    batch=None
):

    username = (
        current_user.username
        if current_user.is_authenticated
        else "System"
    )

    movement = StockMovement(
        medicine_id=medicine.id,
        batch_id=batch.id if batch else None,
        movement_type=movement_type,
        quantity=quantity,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        reason=reason,
        reference=reference,
        username=username
    )

    db.session.add(movement)


# =========================================================
# DATABASE
# =========================================================

def initialize_database():

    try:

        db.create_all()

        # Lightweight schema migration for the bundled SQLite database.
        # New deployments are handled by create_all(); existing databases
        # receive only the columns that are missing.
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)

        sqlite_migrations = {
            "medicine": {
                "sku": "VARCHAR(100)",
                "generic_name": "VARCHAR(150)",
                "brand_name": "VARCHAR(150)",
                "dosage_form": "VARCHAR(100)",
                "route": "VARCHAR(100)",
                "strength": "VARCHAR(100)",
                "unit": "VARCHAR(50)",
                "manufacturer": "VARCHAR(150)",
                "supplier": "VARCHAR(150)",
                "purchase_price": "FLOAT NOT NULL DEFAULT 0",
                "minimum_stock": "INTEGER NOT NULL DEFAULT 10",
                "maximum_stock": "INTEGER NOT NULL DEFAULT 100",
                "reorder_level": "INTEGER NOT NULL DEFAULT 10",
                "storage_requirements": "VARCHAR(255)",
                "prescription_required": "BOOLEAN NOT NULL DEFAULT 0",
                "active": "BOOLEAN NOT NULL DEFAULT 1"
            },
            "sale": {
                "batch_id": "INTEGER"
            }
        }

        if db.engine.dialect.name == "sqlite":
            for table_name, columns in sqlite_migrations.items():
                if table_name not in inspector.get_table_names():
                    continue
                existing = {column["name"] for column in inspector.get_columns(table_name)}
                for column_name, definition in columns.items():
                    if column_name not in existing:
                        db.session.execute(text(
                            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                        ))
            db.session.commit()

            # Keep SKU unique when the column exists on an older database.
            db.session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_medicine_sku_unique "
                "ON medicine (sku) WHERE sku IS NOT NULL"
            ))
            db.session.commit()

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

            admin.set_password(
                initial_password
            )

            db.session.add(admin)
            db.session.commit()

            print("ADMIN USER CREATED")

        reset_password = os.getenv(
            "RESET_ADMIN_PASSWORD",
            ""
        ).strip()

        if reset_password:

            admin.set_password(
                reset_password
            )

            db.session.commit()

            print(
                "ADMIN PASSWORD RESET SUCCESS"
            )

    except Exception as e:

        db.session.rollback()

        print(
            "DATABASE INITIALIZATION ERROR:",
            type(e).__name__,
            str(e)
        )


with app.app_context():
    initialize_database()


# =========================================================
# MEDICINE STATUS HELPERS
# =========================================================

def get_expiry_status(expiry_date):

    if not expiry_date:

        return {
            "label": "No Expiry",
            "class": "neutral"
        }

    today = date.today()

    if expiry_date < today:

        return {
            "label": "Expired",
            "class": "danger"
        }

    days = (
        expiry_date - today
    ).days

    if days <= 30:

        return {
            "label": "Expires Soon",
            "class": "warning"
        }

    if days <= 90:

        return {
            "label": "Expires in 90 Days",
            "class": "notice"
        }

    return {
        "label": "Valid",
        "class": "success"
    }


def get_stock_status(medicine):

    quantity = int(
        medicine.quantity or 0
    )

    reorder = int(
        medicine.reorder_level or 10
    )

    if quantity <= 0:

        return {
            "label": "Out of Stock",
            "class": "danger"
        }

    if quantity <= reorder:

        return {
            "label": "Low Stock",
            "class": "warning"
        }

    return {
        "label": "In Stock",
        "class": "success"
    }


def medicine_to_dict(medicine):

    expiry = get_expiry_status(
        medicine.expiry_date
    )

    stock = get_stock_status(
        medicine
    )

    return {
        "id": medicine.id,
        "name": medicine.name,
        "barcode": medicine.barcode or "",
        "sku": medicine.sku or "",
        "generic_name": medicine.generic_name or "",
        "brand_name": medicine.brand_name or "",
        "category": medicine.category or "",
        "dosage_form": medicine.dosage_form or "",
        "route": medicine.route or "",
        "strength": medicine.strength or "",
        "unit": medicine.unit or "",
        "manufacturer": medicine.manufacturer or "",
        "supplier": medicine.supplier or "",
        "price": float(
            medicine.price or 0
        ),
        "selling_price": float(
            medicine.price or 0
        ),
        "purchase_price": float(
            medicine.purchase_price or 0
        ),
        "quantity": int(
            medicine.quantity or 0
        ),
        "minimum_stock": int(
            medicine.minimum_stock or 0
        ),
        "maximum_stock": int(
            medicine.maximum_stock or 0
        ),
        "reorder_level": int(
            medicine.reorder_level or 0
        ),
        "expiry_date": (
            medicine.expiry_date.isoformat()
            if medicine.expiry_date
            else ""
        ),
        "expiry_status": expiry["label"],
        "stock_status": stock["label"],
        "prescription_required": bool(
            medicine.prescription_required
        )
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
def index():

    today = date.today()

    medicine_count = Medicine.query.filter_by(
        active=True
    ).count()

    total_stock = db.session.query(
        db.func.coalesce(
            db.func.sum(Medicine.quantity),
            0
        )
    ).filter(
        Medicine.active.is_(True)
    ).scalar()

    sales_count = Sale.query.count()

    today_start = datetime.combine(
        today,
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
        Medicine.active.is_(True),
        Medicine.quantity > 0,
        Medicine.quantity <= Medicine.reorder_level
    ).count()

    out_of_stock = Medicine.query.filter(
        Medicine.active.is_(True),
        Medicine.quantity <= 0
    ).count()

    expired = Medicine.query.filter(
        Medicine.active.is_(True),
        Medicine.expiry_date.isnot(None),
        Medicine.expiry_date < today
    ).count()

    expiring_soon = Medicine.query.filter(
        Medicine.active.is_(True),
        Medicine.expiry_date.isnot(None),
        Medicine.expiry_date >= today,
        Medicine.expiry_date <= (
            today + timedelta(days=30)
        )
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
        out_of_stock=out_of_stock,
        expired=expired,
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

        if user and user.check_password(
            password
        ):

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

    search = request.args.get(
        "search",
        ""
    ).strip()

    status = request.args.get(
        "status",
        "all"
    ).strip().lower()

    category = request.args.get(
        "category",
        ""
    ).strip()

    query = Medicine.query.filter_by(
        active=True
    )

    if search:

        term = f"%{search}%"

        query = query.filter(
            db.or_(
                Medicine.name.ilike(term),
                Medicine.barcode.ilike(term),
                Medicine.sku.ilike(term),
                Medicine.generic_name.ilike(term),
                Medicine.brand_name.ilike(term),
                Medicine.category.ilike(term)
            )
        )

    if category:

        query = query.filter(
            Medicine.category == category
        )

    today = date.today()

    if status == "low":

        query = query.filter(
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.reorder_level
        )

    elif status == "out":

        query = query.filter(
            Medicine.quantity <= 0
        )

    elif status == "expired":

        query = query.filter(
            Medicine.expiry_date.isnot(None),
            Medicine.expiry_date < today
        )

    elif status == "expiring":

        query = query.filter(
            Medicine.expiry_date.isnot(None),
            Medicine.expiry_date >= today,
            Medicine.expiry_date <= (
                today + timedelta(days=30)
            )
        )

    medicines_list = query.order_by(
        Medicine.name.asc()
    ).all()

    categories = db.session.query(
        Medicine.category
    ).filter(
        Medicine.category.isnot(None),
        Medicine.category != ""
    ).distinct().order_by(
        Medicine.category.asc()
    ).all()

    category_list = [
        row[0]
        for row in categories
    ]

    summary = {
        "total": Medicine.query.filter_by(active=True).count(),
        "low": Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.reorder_level
        ).count(),
        "out": Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.quantity <= 0
        ).count(),
        "expiring": Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.expiry_date.isnot(None),
            Medicine.expiry_date >= today,
            Medicine.expiry_date <= today + timedelta(days=30)
        ).count(),
        "expired": Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.expiry_date.isnot(None),
            Medicine.expiry_date < today
        ).count()
    }

    medicine_data = []

    for medicine in medicines_list:

        data = medicine_to_dict(
            medicine
        )

        data["expiry_info"] = get_expiry_status(
            medicine.expiry_date
        )

        data["stock_info"] = get_stock_status(
            medicine
        )

        medicine_data.append(
            data
        )

    return render_template(
        "medicines.html",
        medicines=medicines_list,
        medicine_data=medicine_data,
        categories=category_list,
        search=search,
        status=status,
        selected_category=category,
        inventory_summary=summary
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

    if not can_manage_inventory():

        flash(
            "You do not have permission to add medicines.",
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

        sku = request.form.get(
            "sku",
            ""
        ).strip()

        generic_name = request.form.get(
            "generic_name",
            ""
        ).strip()

        brand_name = request.form.get(
            "brand_name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        dosage_form = request.form.get(
            "dosage_form",
            ""
        ).strip()

        route = request.form.get(
            "route",
            ""
        ).strip()

        strength = request.form.get(
            "strength",
            ""
        ).strip()

        unit = request.form.get(
            "unit",
            ""
        ).strip()

        manufacturer = request.form.get(
            "manufacturer",
            ""
        ).strip()

        supplier = request.form.get(
            "supplier",
            ""
        ).strip()

        price_raw = request.form.get(
            "price",
            "0"
        )

        purchase_price_raw = request.form.get(
            "purchase_price",
            "0"
        )

        minimum_stock_raw = request.form.get(
            "minimum_stock",
            "10"
        )

        maximum_stock_raw = request.form.get(
            "maximum_stock",
            "100"
        )

        reorder_level_raw = request.form.get(
            "reorder_level",
            "10"
        )

        expiry_raw = request.form.get(
            "expiry_date",
            ""
        )

        storage_requirements = request.form.get(
            "storage_requirements",
            ""
        ).strip()

        prescription_required = (
            request.form.get(
                "prescription_required"
            ) == "on"
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

            price = float(
                price_raw or 0
            )

            purchase_price = float(
                purchase_price_raw or 0
            )

            minimum_stock = int(
                minimum_stock_raw or 10
            )

            maximum_stock = int(
                maximum_stock_raw or 100
            )

            reorder_level = int(
                reorder_level_raw or 10
            )

        except ValueError:

            flash(
                "Numeric fields contain invalid values.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        if (
            price < 0
            or purchase_price < 0
            or minimum_stock < 0
            or maximum_stock < 0
            or reorder_level < 0
        ):

            flash(
                "Numeric values cannot be negative.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        if maximum_stock < minimum_stock:

            flash(
                "Maximum stock cannot be lower than minimum stock.",
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

            if Medicine.query.filter_by(
                barcode=barcode
            ).first():

                flash(
                    "Barcode already exists.",
                    "danger"
                )

                return redirect(
                    url_for("add_medicine")
                )

        if sku:

            if Medicine.query.filter_by(
                sku=sku
            ).first():

                flash(
                    "SKU already exists.",
                    "danger"
                )

                return redirect(
                    url_for("add_medicine")
                )

        medicine = Medicine(
            name=name,
            barcode=barcode or None,
            sku=sku or None,
            generic_name=generic_name or None,
            brand_name=brand_name or None,
            category=category or None,
            dosage_form=dosage_form or None,
            route=route or None,
            strength=strength or None,
            unit=unit or None,
            manufacturer=manufacturer or None,
            supplier=supplier or None,
            price=price,
            purchase_price=purchase_price,
            quantity=quantity,
            minimum_stock=minimum_stock,
            maximum_stock=maximum_stock,
            reorder_level=reorder_level,
            expiry_date=expiry_date,
            storage_requirements=storage_requirements or None,
            prescription_required=prescription_required,
            active=True
        )

        db.session.add(medicine)

        db.session.flush()

        if quantity > 0:

            add_stock_movement(
                medicine=medicine,
                movement_type="Initial Stock",
                quantity=quantity,
                previous_quantity=0,
                new_quantity=quantity,
                reason="Initial medicine stock"
            )

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

    if not can_manage_inventory():

        flash(
            "You do not have permission to edit medicines.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    if request.method == "POST":

        old_quantity = int(
            medicine.quantity or 0
        )

        name = request.form.get(
            "name",
            ""
        ).strip()

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        sku = request.form.get(
            "sku",
            ""
        ).strip()

        generic_name = request.form.get(
            "generic_name",
            ""
        ).strip()

        brand_name = request.form.get(
            "brand_name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        dosage_form = request.form.get(
            "dosage_form",
            ""
        ).strip()

        route = request.form.get(
            "route",
            ""
        ).strip()

        strength = request.form.get(
            "strength",
            ""
        ).strip()

        unit = request.form.get(
            "unit",
            ""
        ).strip()

        manufacturer = request.form.get(
            "manufacturer",
            ""
        ).strip()

        supplier = request.form.get(
            "supplier",
            ""
        ).strip()

        price_raw = request.form.get(
            "price",
            "0"
        )

        purchase_price_raw = request.form.get(
            "purchase_price",
            "0"
        )

        minimum_stock_raw = request.form.get(
            "minimum_stock",
            "10"
        )

        maximum_stock_raw = request.form.get(
            "maximum_stock",
            "100"
        )

        reorder_level_raw = request.form.get(
            "reorder_level",
            "10"
        )

        expiry_raw = request.form.get(
            "expiry_date",
            ""
        )

        storage_requirements = request.form.get(
            "storage_requirements",
            ""
        ).strip()

        prescription_required = (
            request.form.get(
                "prescription_required"
            ) == "on"
        )

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

            price = float(
                price_raw or 0
            )

            purchase_price = float(
                purchase_price_raw or 0
            )

            minimum_stock = int(
                minimum_stock_raw or 10
            )

            maximum_stock = int(
                maximum_stock_raw or 100
            )

            reorder_level = int(
                reorder_level_raw or 10
            )

        except ValueError:

            flash(
                "Numeric fields contain invalid values.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        if (
            price < 0
            or purchase_price < 0
            or minimum_stock < 0
            or maximum_stock < 0
            or reorder_level < 0
        ):

            flash(
                "Numeric values cannot be negative.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        if maximum_stock < minimum_stock:

            flash(
                "Maximum stock cannot be lower than minimum stock.",
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

        if sku:

            existing = Medicine.query.filter(
                Medicine.sku == sku,
                Medicine.id != id
            ).first()

            if existing:

                flash(
                    "SKU already exists.",
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
        medicine.sku = sku or None
        medicine.generic_name = generic_name or None
        medicine.brand_name = brand_name or None
        medicine.category = category or None
        medicine.dosage_form = dosage_form or None
        medicine.route = route or None
        medicine.strength = strength or None
        medicine.unit = unit or None
        medicine.manufacturer = manufacturer or None
        medicine.supplier = supplier or None
        medicine.price = price
        medicine.purchase_price = purchase_price
        # Stock is intentionally not editable here.
        # Use /adjust-stock so the change gets a reason/reference and audit entry.
        medicine.minimum_stock = minimum_stock
        medicine.maximum_stock = maximum_stock
        medicine.reorder_level = reorder_level
        medicine.expiry_date = expiry_date
        medicine.storage_requirements = (
            storage_requirements or None
        )
        medicine.prescription_required = (
            prescription_required
        )

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


# =========================================================
# DELETE MEDICINE
# =========================================================

@app.route(
    "/medicines/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_medicine(id):

    if not admin_required():

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

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

    medicine.active = False

    medicine_name = medicine.name

    db.session.commit()

    log_activity(
        f"Medicine archived: {medicine_name}"
    )

    flash(
        "Medicine archived successfully.",
        "success"
    )

    return redirect(
        url_for("medicines")
    )


# =========================================================
# STOCK ADJUSTMENT
# =========================================================

@app.route(
    "/medicines/<int:id>/adjust-stock",
    methods=["POST"]
)
@login_required
def adjust_stock(id):

    if not can_manage_inventory():

        flash(
            "You do not have permission to adjust stock.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

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

    try:

        adjustment = int(
            request.form.get(
                "adjustment",
                "0"
            )
        )

    except ValueError:

        flash(
            "Invalid stock adjustment.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    reason = request.form.get(
        "reason",
        ""
    ).strip()

    reference = request.form.get(
        "reference",
        ""
    ).strip()

    previous_quantity = int(
        medicine.quantity or 0
    )

    new_quantity = (
        previous_quantity +
        adjustment
    )

    if new_quantity < 0:

        flash(
            "Stock cannot become negative.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    medicine.quantity = new_quantity

    add_stock_movement(
        medicine=medicine,
        movement_type="Adjustment",
        quantity=adjustment,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        reason=reason or "Manual stock adjustment",
        reference=reference
    )

    db.session.commit()

    log_activity(
        f"Stock adjusted: {medicine.name} "
        f"{previous_quantity} -> {new_quantity}"
    )

    flash(
        "Stock adjusted successfully.",
        "success"
    )

    return redirect(
        url_for("medicines")
    )


# =========================================================
# BATCHES
# =========================================================

@app.route(
    "/medicines/<int:medicine_id>/batches/add",
    methods=["POST"]
)
@login_required
def add_batch(medicine_id):

    if not can_manage_inventory():

        flash(
            "You do not have permission to add batches.",
            "danger"
        )

        return redirect(
            url_for("medicines")
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
            url_for("medicines")
        )

    batch_number = request.form.get(
        "batch_number",
        ""
    ).strip()

    supplier = request.form.get(
        "supplier",
        ""
    ).strip()

    expiry_raw = request.form.get(
        "expiry_date",
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

    except ValueError:

        flash(
            "Invalid batch values.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    if not batch_number:

        flash(
            "Batch number is required.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    if quantity < 0:

        flash(
            "Batch quantity cannot be negative.",
            "danger"
        )

        return redirect(
            url_for("medicines")
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
                "Invalid batch expiry date.",
                "danger"
            )

            return redirect(
                url_for("medicines")
            )

    batch = Batch(
        medicine_id=medicine.id,
        batch_number=batch_number,
        supplier=supplier or None,
        quantity=quantity,
        purchase_price=purchase_price,
        expiry_date=expiry_date
    )

    db.session.add(batch)

    previous_quantity = int(
        medicine.quantity or 0
    )

    medicine.quantity = (
        previous_quantity +
        quantity
    )

    add_stock_movement(
        medicine=medicine,
        movement_type="Purchase",
        quantity=quantity,
        previous_quantity=previous_quantity,
        new_quantity=medicine.quantity,
        reason="New batch received",
        reference=batch_number,
        batch=batch
    )

    db.session.commit()

    log_activity(
        f"Batch added: {medicine.name} / {batch_number}"
    )

    flash(
        "Batch added successfully.",
        "success"
    )

    return redirect(
        url_for("medicines")
    )


@app.route(
    "/medicines/<int:medicine_id>/batches"
)
@login_required
def medicine_batches(medicine_id):

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
            url_for("medicines")
        )

    batches = Batch.query.filter_by(
        medicine_id=medicine_id
    ).order_by(
        Batch.expiry_date.asc()
    ).all()

    return render_template(
        "medicines.html",
        medicines=[medicine],
        medicine_data=[
            medicine_to_dict(medicine)
        ],
        categories=[],
        search="",
        status="all",
        selected_category="",
        selected_batches=batches
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

    if not can_make_sale():

        flash(
            "You do not have permission to make sales.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        try:

            medicine_id = int(
                request.form.get(
                    "medicine_id",
                    ""
                )
            )

            quantity = int(
                request.form.get(
                    "quantity",
                    ""
                )
            )

        except (
            ValueError,
            TypeError
        ):

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

        remaining = quantity
        selected_batch = None

        batches = Batch.query.filter(
            Batch.medicine_id == medicine.id,
            Batch.quantity > 0,
            db.or_(
                Batch.expiry_date.is_(None),
                Batch.expiry_date >= date.today()
            )
        ).order_by(
            Batch.expiry_date.asc().nullslast(),
            Batch.id.asc()
        ).all()

        for batch in batches:

            if remaining <= 0:
                break

            take = min(
                batch.quantity,
                remaining
            )

            batch.quantity -= take
            remaining -= take

            if selected_batch is None:
                selected_batch = batch

        if batches and remaining > 0:
            flash(
                "Not enough non-expired batch stock available.",
                "danger"
            )
            return redirect(url_for("sales"))

        previous_quantity = int(
            medicine.quantity
        )

        medicine.quantity -= quantity

        total_price = (
            float(medicine.price) *
            quantity
        )

        sale = Sale(
            medicine_id=medicine.id,
            batch_id=(
                selected_batch.id
                if selected_batch
                else None
            ),
            quantity=quantity,
            total_price=total_price,
            sold_by=current_user.id
        )

        db.session.add(sale)

        add_stock_movement(
            medicine=medicine,
            movement_type="Sale",
            quantity=-quantity,
            previous_quantity=previous_quantity,
            new_quantity=medicine.quantity,
            reason="Sale",
            reference=f"Sale #{sale.id}"
            if sale.id
            else "New Sale",
            batch=selected_batch
        )

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

    medicine_records = Medicine.query.filter_by(
        active=True
    ).order_by(
        Medicine.name.asc()
    ).all()

    medicines = [
        medicine_to_dict(
            medicine
        )
        for medicine in medicine_records
    ]

    recent_sales = Sale.query.order_by(
        Sale.created_at.desc()
    ).limit(25).all()

    return render_template(
        "sales.html",
        medicines=medicines,
        recent_sales=recent_sales
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

    if not can_make_sale():

        flash(
            "You do not have permission to delete sales.",
            "danger"
        )

        return redirect(
            url_for("sales")
        )

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

            previous_quantity = int(
                medicine.quantity or 0
            )

            medicine.quantity = (
                previous_quantity +
                sale_quantity
            )

            if sale.batch_id:
                batch = db.session.get(Batch, sale.batch_id)
                if batch:
                    batch.quantity += sale_quantity

            add_stock_movement(
                medicine=medicine,
                movement_type="Return",
                quantity=sale_quantity,
                previous_quantity=previous_quantity,
                new_quantity=medicine.quantity,
                reason="Sale deleted",
                reference=f"Sale #{sale.id}",
                batch=(
                    db.session.get(Batch, sale.batch_id)
                    if sale.batch_id else None
                )
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
            "Sale deleted and stock returned.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Delete error: {type(e).__name__}: {str(e)[:300]}",
            "danger"
        )

    return redirect(
        url_for("sales")
    )


# =========================================================
# STOCK MOVEMENTS
# =========================================================

@app.route("/stock-movements")
@login_required
def stock_movements():

    if not can_view_inventory():

        flash(
            "Access denied.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    movements = StockMovement.query.order_by(
        StockMovement.created_at.desc()
    ).limit(500).all()

    return render_template(
        "logs.html",
        logs=movements,
        stock_movements=True
    )


# =========================================================
# PUBLIC ORDERS
# =========================================================

@app.route(
    "/orders",
    methods=["GET", "POST"]
)
def orders():

    medicines = Medicine.query.filter_by(
        active=True
    ).order_by(
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

        try:

            medicine_id = int(
                request.form.get(
                    "medicine_id",
                    ""
                )
            )

            quantity = int(
                request.form.get(
                    "quantity",
                    ""
                )
            )

        except (
            ValueError,
            TypeError
        ):

            flash(
                "Please select a medicine and enter a valid quantity.",
                "danger"
            )

            return redirect(
                url_for("orders")
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
            unit_price *
            quantity
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

    if (
        current_user.is_authenticated
        and admin_required()
    ):

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

    if new_status not in ORDER_STATUSES:

        flash(
            "Invalid order status.",
            "danger"
        )

        return redirect(
            url_for("orders")
        )

    old_status = order.status

    try:

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
                        "Medicine no longer exists."
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

                previous_quantity = int(
                    medicine.quantity
                )

                medicine.quantity -= item.quantity

                add_stock_movement(
                    medicine=medicine,
                    movement_type="Order",
                    quantity=-item.quantity,
                    previous_quantity=previous_quantity,
                    new_quantity=medicine.quantity,
                    reason="Order approved",
                    reference=f"Order #{order.id}"
                )

        elif (
            old_status == "Approved"
            and new_status == "Cancelled"
        ):

            for item in order.items:

                medicine = db.session.get(
                    Medicine,
                    item.medicine_id
                )

                if medicine:

                    previous_quantity = int(
                        medicine.quantity
                    )

                    medicine.quantity += item.quantity

                    add_stock_movement(
                        medicine=medicine,
                        movement_type="Return",
                        quantity=item.quantity,
                        previous_quantity=previous_quantity,
                        new_quantity=medicine.quantity,
                        reason="Approved order cancelled",
                        reference=f"Order #{order.id}"
                    )

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
            "cashier"
        ).strip()

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        if role not in USER_ROLES:

            role = "cashier"

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
            f"User created: {username} ({role})"
        )

        flash(
            "User created successfully.",
            "success"
        )

        return redirect(
            url_for("users")
        )

    return render_template(
        "users.html",
        users=User.query.order_by(
            User.username.asc()
        ).all(),
        add_user_form=True
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
# SUPPLIERS
# =========================================================

@app.route("/suppliers")
@login_required
def suppliers():

    if not can_manage_inventory():

        flash(
            "Access denied.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    suppliers_list = Supplier.query.order_by(
        Supplier.name.asc()
    ).all()

    return render_template(
        "suppliers.html",
        suppliers=suppliers_list
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
@login_required
def reports():

    if current_user.role not in {
        "admin",
        "pharmacist",
        "inventory"
    }:

        flash(
            "You do not have permission to view reports.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    total_inventory_value = db.session.query(
        db.func.coalesce(
            db.func.sum(
                Medicine.quantity *
                Medicine.purchase_price
            ),
            0
        )
    ).scalar()

    total_sales = db.session.query(
        db.func.coalesce(
            db.func.sum(Sale.total_price),
            0
        )
    ).scalar()

    total_units_sold = db.session.query(
        db.func.coalesce(
            db.func.sum(Sale.quantity),
            0
        )
    ).scalar()

    return render_template(
        "reports.html",
        total_inventory_value=total_inventory_value,
        total_sales=total_sales,
        total_units_sold=total_units_sold,
        medicine_count=Medicine.query.filter_by(active=True).count(),
        total_stock=db.session.query(
            db.func.coalesce(db.func.sum(Medicine.quantity), 0)
        ).filter(Medicine.active.is_(True)).scalar(),
        low_stock=Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.reorder_level
        ).count(),
        out_of_stock=Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.quantity <= 0
        ).count(),
        expired=Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.expiry_date.isnot(None),
            Medicine.expiry_date < date.today()
        ).count(),
        expiring_soon=Medicine.query.filter(
            Medicine.active.is_(True),
            Medicine.expiry_date.isnot(None),
            Medicine.expiry_date >= date.today(),
            Medicine.expiry_date <= date.today() + timedelta(days=30)
        ).count()
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
    ).limit(500).all()

    return render_template(
        "logs.html",
        logs=logs_list
    )


# =========================================================
# API - MEDICINE SEARCH
# =========================================================

@app.route("/api/medicines")
@login_required
def medicine_api():

    search = request.args.get(
        "search",
        ""
    ).strip()

    query = Medicine.query.filter_by(
        active=True
    )

    if search:

        term = f"%{search}%"

        query = query.filter(
            db.or_(
                Medicine.name.ilike(term),
                Medicine.barcode.ilike(term),
                Medicine.sku.ilike(term),
                Medicine.generic_name.ilike(term),
                Medicine.brand_name.ilike(term)
            )
        )

    results = query.order_by(
        Medicine.name.asc()
    ).limit(30).all()

    return jsonify([
        medicine_to_dict(
            medicine
        )
        for medicine in results
    ])


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    try:

        return render_template(
            "404.html"
        ), 404

    except Exception:

        return (
            "<h1>404 - Page Not Found</h1>",
            404
        )


@app.errorhandler(500)
def internal_server_error(error):

    try:

        db.session.rollback()

    except Exception:

        pass

    try:

        return render_template(
            "500.html"
        ), 500

    except Exception:

        return (
            "<h1>500 - Internal Server Error</h1>",
            500
        )


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