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
# APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)


# =========================================================
# DATABASE
# =========================================================

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
# PUBLIC ORDER
# =========================================================

class Order(db.Model):

    __tablename__ = "orders"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    customer_name = db.Column(
        db.String(120),
        nullable=False
    )

    customer_phone = db.Column(
        db.String(50),
        nullable=False
    )

    customer_address = db.Column(
        db.String(255),
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
# LOGIN USER
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    return db.session.get(
        User,
        int(user_id)
    )


# =========================================================
# ACTIVITY LOG HELPER
# =========================================================

def log_activity(action):

    if not current_user.is_authenticated:
        return

    log = ActivityLog(
        user_id=current_user.id,
        action=action
    )

    db.session.add(log)

    db.session.commit()


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

        if not initial_password:

            print(
                "WARNING: INITIAL_ADMIN_PASSWORD is not set."
            )

            return

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


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def index():

    medicine_count = Medicine.query.count()

    total_stock = (
        db.session.query(
            db.func.sum(
                Medicine.quantity
            )
        ).scalar()
        or 0
    )

    sales_count = Sale.query.count()

    today = datetime.utcnow().date()

    today_sales = (
        db.session.query(
            db.func.sum(
                Sale.total_price
            )
        )
        .filter(
            db.func.date(
                Sale.sale_date
            ) == today
        )
        .scalar()
        or 0
    )

    low_stock = Medicine.query.filter(
        Medicine.quantity <= 10
    ).order_by(
        Medicine.quantity.asc()
    ).limit(10).all()

    recent_sales = Sale.query.order_by(
        Sale.sale_date.desc()
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

    if search:

        medicines = Medicine.query.filter(
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
            Medicine.name.asc()
        ).all()

    else:

        medicines = Medicine.query.order_by(
            Medicine.name.asc()
        ).all()

    return render_template(
        "medicines.html",
        medicines=medicines,
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
                    0
                )
            )

            purchase_price = float(
                request.form.get(
                    "purchase_price",
                    0
                )
            )

            selling_price = float(
                request.form.get(
                    "selling_price",
                    0
                )
            )

        except ValueError:

            flash(
                "Invalid number.",
                "danger"
            )

            return redirect(
                url_for("add_medicine")
            )

        expiry_date = None

        expiry = request.form.get(
            "expiry_date",
            ""
        )

        if expiry:

            try:

                expiry_date = datetime.strptime(
                    expiry,
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

        if not name:

            flash(
                "Medicine name is required.",
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
            category=category,
            barcode=barcode or None,
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

        medicine.name = request.form.get(
            "name",
            ""
        ).strip()

        medicine.category = request.form.get(
            "category",
            ""
        ).strip()

        barcode = request.form.get(
            "barcode",
            ""
        ).strip()

        if barcode:

            existing = Medicine.query.filter(
                Medicine.barcode == barcode,
                Medicine.id != medicine.id
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

        medicine.barcode = (
            barcode or None
        )

        try:

            medicine.quantity = int(
                request.form.get(
                    "quantity",
                    0
                )
            )

            medicine.purchase_price = float(
                request.form.get(
                    "purchase_price",
                    0
                )
            )

            medicine.selling_price = float(
                request.form.get(
                    "selling_price",
                    0
                )
            )

        except ValueError:

            flash(
                "Invalid number.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_medicine",
                    id=id
                )
            )

        expiry = request.form.get(
            "expiry_date",
            ""
        )

        if expiry:

            try:

                medicine.expiry_date = datetime.strptime(
                    expiry,
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

        else:

            medicine.expiry_date = None

        db.session.commit()

        log_activity(
            f"Edited medicine: {medicine.name}"
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
        medicine_id=id
    ).first():

        flash(
            "This medicine cannot be deleted.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    if OrderItem.query.filter_by(
        medicine_id=id
    ).first():

        flash(
            "This medicine cannot be deleted because it has order history.",
            "danger"
        )

        return redirect(
            url_for("medicines")
        )

    name = medicine.name

    db.session.delete(
        medicine
    )

    db.session.commit()

    log_activity(
        f"Deleted medicine: {name}"
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
def sales():

    if request.method == "POST":

        if not current_user.is_authenticated:

            flash(
                "Please log in to record a sale.",
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

        except (
            TypeError,
            ValueError
        ):

            flash(
                "Invalid sale information.",
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
                "Not enough stock.",
                "danger"
            )

            return redirect(
                url_for("sales")
            )

        total = (
            medicine.selling_price
            * quantity
        )

        medicine.quantity -= quantity

        sale = Sale(
            medicine_id=medicine.id,
            quantity=quantity,
            total_price=total,
            sold_by=current_user.id
        )

        db.session.add(sale)

        db.session.commit()

        log_activity(
            f"Recorded sale: {medicine.name} x {quantity}"
        )

        flash(
            "Sale recorded successfully.",
            "success"
        )

        return redirect(
            url_for("sales")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    if search:

        medicines = Medicine.query.filter(
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
        ).all()

    else:

        medicines = Medicine.query.order_by(
            Medicine.name.asc()
        ).all()

    recent_sales = Sale.query.order_by(
        Sale.sale_date.desc()
    ).limit(10).all()

    return render_template(
        "sales.html",
        medicines=medicines,
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

        print(
            "DELETE SALE ERROR:",
            type(e).__name__,
            str(e)
        )

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

    # -----------------------------------------------------
    # CREATE PUBLIC ORDER
    # -----------------------------------------------------

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
                    "medicine_id"
                )
            )

            quantity = int(
                request.form.get(
                    "quantity"
                )
            )

        except (
            TypeError,
            ValueError
        ):

            flash(
                "Please select a medicine and enter a valid quantity.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        # Customer name
        if not customer_name:

            flash(
                "Please enter your name.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        # Customer phone
        if not customer_phone:

            flash(
                "Please enter your phone number.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        # Customer address
        if not customer_address:

            flash(
                "Please enter your address.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        # Quantity
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

        if medicine.quantity <= 0:

            flash(
                "This medicine is currently out of stock.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        if quantity > medicine.quantity:

            flash(
                f"Only {medicine.quantity} available in stock.",
                "danger"
            )

            return redirect(
                url_for("orders")
            )

        total = (
            medicine.selling_price
            * quantity
        )

        # Stock is NOT reduced when customer places order.
        # Stock is reduced when admin approves it.

        order = Order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            status="Pending",
            total_price=total
        )

        db.session.add(order)

        db.session.flush()

        item = OrderItem(
            order_id=order.id,
            medicine_id=medicine.id,
            quantity=quantity,
            unit_price=medicine.selling_price,
            total_price=total
        )

        db.session.add(item)

        db.session.commit()

        return redirect(
            url_for(
                "orders",
                success=order.id
            )
        )

    # -----------------------------------------------------
    # AVAILABLE MEDICINES
    # -----------------------------------------------------

    medicines = Medicine.query.filter(
        Medicine.quantity > 0
    ).order_by(
        Medicine.name.asc()
    ).all()

    # -----------------------------------------------------
    # ADMIN ORDERS
    # -----------------------------------------------------

    all_orders = []

    if (
        current_user.is_authenticated
        and current_user.role == "admin"
    ):

        all_orders = Order.query.order_by(
            Order.created_at.desc()
        ).all()

    success_order = request.args.get(
        "success"
    )

    return render_template(
        "orders.html",
        medicines=medicines,
        orders=all_orders,
        success_order=success_order
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

    if current_user.role != "admin":

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

    # -----------------------------------------------------
    # APPROVE
    # -----------------------------------------------------

    if new_status == "Approved":

        if order.status != "Pending":

            flash(
                "Only pending orders can be approved.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        # Check stock BEFORE changing anything
        for item in order.items:

            medicine = db.session.get(
                Medicine,
                item.medicine_id
            )

            if not medicine:

                flash(
                    "A medicine in this order no longer exists.",
                    "danger"
                )

                return redirect(
                    url_for("orders")
                )

            if medicine.quantity < item.quantity:

                flash(
                    f"Not enough stock for {medicine.name}.",
                    "danger"
                )

                return redirect(
                    url_for("orders")
                )

        # Reduce stock
        for item in order.items:

            medicine = db.session.get(
                Medicine,
                item.medicine_id
            )

            medicine.quantity -= item.quantity

        order.status = "Approved"

    # -----------------------------------------------------
    # COMPLETED
    # -----------------------------------------------------

    elif new_status == "Completed":

        if order.status != "Approved":

            flash(
                "Only approved orders can be completed.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        order.status = "Completed"

    # -----------------------------------------------------
    # CANCELLED
    # -----------------------------------------------------

    elif new_status == "Cancelled":

        if order.status == "Approved":

            flash(
                "An approved order cannot be cancelled.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        if order.status == "Completed":

            flash(
                "A completed order cannot be cancelled.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        order.status = "Cancelled"

    # -----------------------------------------------------
    # PENDING
    # -----------------------------------------------------

    elif new_status == "Pending":

        if order.status != "Cancelled":

            flash(
                "Only cancelled orders can be returned to pending.",
                "warning"
            )

            return redirect(
                url_for("orders")
            )

        order.status = "Pending"

    db.session.commit()

    log_activity(
        f"Order #{order.id}: {old_status} -> {new_status}"
    )

    flash(
        f"Order #{order.id} updated to {new_status}.",
        "success"
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

    users = User.query.order_by(
        User.username.asc()
    ).all()

    return render_template(
        "users.html",
        users=users
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
        )

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger"
            )

            return redirect(
                url_for("add_user")
            )

        if User.query.filter_by(
            username=username
        ).first():

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
            "danger"
        )

        return redirect(
            url_for("users")
        )

    if user.role == "admin":

        flash(
            "Admin users cannot be deleted.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    if Sale.query.filter_by(
        sold_by=user.id
    ).first():

        flash(
            "This user cannot be deleted because they have sales history.",
            "danger"
        )

        return redirect(
            url_for("users")
        )

    username = user.username

    db.session.delete(user)

    db.session.commit()

    log_activity(
        f"Deleted user: {username}"
    )

    flash(
        "User deleted successfully.",
        "success"
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# LOGS
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

    logs = ActivityLog.query.order_by(
        ActivityLog.timestamp.desc()
    ).limit(200).all()

    return render_template(
        "logs.html",
        logs=logs
    )


# =========================================================
# ERRORS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def internal_error(error):

    db.session.rollback()

    return render_template(
        "500.html"
    ), 500


# =========================================================
# START
# =========================================================

with app.app_context():

    initialize_database()


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
