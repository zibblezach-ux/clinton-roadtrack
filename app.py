from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import csv
from io import StringIO, TextIOWrapper
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///roadtrack.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ADMIN_KEY = "clinton-2026-secure"

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.args.get("key") != ADMIN_KEY:
            return "Unauthorized", 403
        return f(*args, **kwargs)
    return decorated

@app.before_request
def create_tables():
    db.create_all()

# =========================
# MODELS
# =========================

class Road(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140))
    segment_name = db.Column(db.String(140))
    surface_type = db.Column(db.String(60))
    length_miles = db.Column(db.Float)
    importance = db.Column(db.String(120))
    condition = db.Column(db.String(20))
    traffic_level = db.Column(db.String(20))

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_id = db.Column(db.Integer, db.ForeignKey("road.id"))
    road = db.relationship("Road")

    title = db.Column(db.String(160))
    work_type = db.Column(db.String(80))
    priority = db.Column(db.String(20))

    status = db.Column(db.String(30))
    planned_date = db.Column(db.String(20))
    completed_date = db.Column(db.String(20))

    estimated_cost = db.Column(db.Float)
    actual_cost = db.Column(db.Float)

# =========================
# ROUTES
# =========================

@app.route("/")
def dashboard():
    roads = Road.query.all()
    work_orders = WorkOrder.query.all()

    counts = {
        "roads": len(roads),
        "planned": len([w for w in work_orders if w.status == "Planned"]),
        "completed": len([w for w in work_orders if w.status == "Completed"]),
        "poor": len([r for r in roads if r.condition == "Poor"])
    }

    return render_template("dashboard.html", counts=counts)

@app.route("/roads")
def roads():
    return render_template(
        "roads.html",
        roads=Road.query.all(),
        is_admin=request.args.get("key") == ADMIN_KEY
    )

@app.route("/work-orders")
def work_orders():
    return render_template(
        "work_orders.html",
        work_orders=WorkOrder.query.all(),
        is_admin=request.args.get("key") == ADMIN_KEY
    )

# ✅ PUBLIC VIEW (THIS FIXES YOUR ISSUE)
@app.route("/public")
def public():
    return render_template(
        "public.html",
        roads=Road.query.all(),
        work_orders=WorkOrder.query.all()
    )