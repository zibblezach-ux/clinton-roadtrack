from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import csv
from io import StringIO
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///roadtrack.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# 🔒 ADMIN KEY
ADMIN_KEY = "clinton-2026-secure"

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.args.get("key")
        if key != ADMIN_KEY:
            return "Unauthorized", 403
        return f(*args, **kwargs)
    return decorated

# 🔧 ENSURE DATABASE EXISTS (RENDER FIX)
@app.before_request
def create_tables():
    db.create_all()

# =========================
# MODELS
# =========================

class Road(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    segment_name = db.Column(db.String(140), nullable=False)
    surface_type = db.Column(db.String(60))
    length_miles = db.Column(db.Float)
    traffic_level = db.Column(db.String(20))
    importance = db.Column(db.String(120))
    condition = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_id = db.Column(db.Integer, db.ForeignKey("road.id"))
    road = db.relationship("Road")
    title = db.Column(db.String(160))
    work_type = db.Column(db.String(80))
    status = db.Column(db.String(30))
    priority = db.Column(db.String(20))
    planned_date = db.Column(db.String(20))
    completed_date = db.Column(db.String(20))
    estimated_cost = db.Column(db.Float)
    actual_cost = db.Column(db.Float)

class CitizenIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_name = db.Column(db.String(140))
    description = db.Column(db.Text)
    status = db.Column(db.String(30), default="Received")

# =========================
# PRIORITY SCORING
# =========================

def score_road(r):
    score = 0

    if r.condition == "Poor":
        score += 40
    elif r.condition == "Fair":
        score += 20
    else:
        score += 5

    if r.traffic_level == "High":
        score += 30
    elif r.traffic_level == "Medium":
        score += 15
    else:
        score += 5

    if r.importance:
        score += 10

    return score

# =========================
# DASHBOARD
# =========================

@app.route("/")
def dashboard():
    roads = Road.query.all()
    work_orders = WorkOrder.query.all()
    issues = CitizenIssue.query.all()

    counts = {
        "roads": len(roads),
        "planned": len([w for w in work_orders if w.status == "Planned"]),
        "completed": len([w for w in work_orders if w.status == "Completed"]),
        "issues": len(issues),
        "poor": len([r for r in roads if r.condition == "Poor"])
    }

    scored = sorted([(r, score_road(r)) for r in roads], key=lambda x: x[1], reverse=True)

    return render_template(
        "dashboard.html",
        counts=counts,
        work_orders=work_orders,
        issues=issues,
        scored=scored
    )

# =========================
# ROADS
# =========================

@app.route("/roads")
def roads():
    roads = Road.query.all()
    return render_template("roads.html", roads=roads, score_road=score_road)

@app.route("/roads/new", methods=["GET", "POST"])
@require_admin
def road_new():
    if request.method == "POST":
        r = Road(
            name=request.form["name"],
            segment_name=request.form["segment_name"],
            surface_type=request.form.get("surface_type"),
            length_miles=float(request.form.get("length_miles") or 0),
            traffic_level=request.form.get("traffic_level"),
            importance=request.form.get("importance"),
            condition=request.form.get("condition")
        )
        db.session.add(r)
        db.session.commit()
        return redirect(url_for("roads") + f"?key={ADMIN_KEY}")

    return render_template("road_form.html")

@app.route("/roads/<int:road_id>/edit", methods=["GET", "POST"])
@require_admin
def road_edit(road_id):
    r = Road.query.get_or_404(road_id)

    if request.method == "POST":
        r.name = request.form["name"]
        r.segment_name = request.form["segment_name"]
        r.surface_type = request.form.get("surface_type")
        r.length_miles = float(request.form.get("length_miles") or 0)
        r.traffic_level = request.form.get("traffic_level")
        r.importance = request.form.get("importance")
        r.condition = request.form.get("condition")

        db.session.commit()
        return redirect(url_for("roads") + f"?key={ADMIN_KEY}")

    return render_template("road_form.html", road=r)

# =========================
# WORK ORDERS
# =========================

@app.route("/work-orders")
def work_orders():
    work_orders = WorkOrder.query.all()
    return render_template("work_orders.html", work_orders=work_orders)

@app.route("/work-orders/new", methods=["GET", "POST"])
@require_admin
def work_order_new():
    roads = Road.query.all()

    if request.method == "POST":
        w = WorkOrder(
            road_id=request.form["road_id"],
            title=request.form["title"],
            work_type=request.form.get("work_type"),
            status=request.form.get("status"),
            priority=request.form.get("priority"),
            planned_date=request.form.get("planned_date"),
            completed_date=request.form.get("completed_date"),
            estimated_cost=float(request.form.get("estimated_cost") or 0),
            actual_cost=float(request.form.get("actual_cost") or 0)
        )
        db.session.add(w)
        db.session.commit()
        return redirect(url_for("work_orders") + f"?key={ADMIN_KEY}")

    return render_template("work_order_form.html", roads=roads)

@app.route("/work-orders/<int:wo_id>/edit", methods=["GET", "POST"])
@require_admin
def work_order_edit(wo_id):
    w = WorkOrder.query.get_or_404(wo_id)
    roads = Road.query.all()

    if request.method == "POST":
        w.road_id = request.form["road_id"]
        w.title = request.form["title"]
        w.work_type = request.form.get("work_type")
        w.status = request.form.get("status")
        w.priority = request.form.get("priority")
        w.planned_date = request.form.get("planned_date")
        w.completed_date = request.form.get("completed_date")
        w.estimated_cost = float(request.form.get("estimated_cost") or 0)
        w.actual_cost = float(request.form.get("actual_cost") or 0)

        db.session.commit()
        return redirect(url_for("work_orders") + f"?key={ADMIN_KEY}")

    return render_template("work_order_form.html", roads=roads, wo=w)

# =========================
# PUBLIC VIEW
# =========================

@app.route("/public")
def public():
    roads = Road.query.all()
    completed = WorkOrder.query.filter_by(status="Completed").all()
    planned = WorkOrder.query.filter(WorkOrder.status != "Completed").all()

    return render_template(
        "public.html",
        roads=roads,
        completed=completed,
        planned=planned,
        score_road=score_road
    )

# =========================
# EXPORT
# =========================

@app.route("/export/<kind>.csv")
def export_csv(kind):
    output = StringIO()
    writer = csv.writer(output)

    if kind == "roads":
        writer.writerow(["name", "segment", "condition", "traffic", "score"])
        for r in Road.query.all():
            writer.writerow([
                r.name,
                r.segment_name,
                r.condition,
                r.traffic_level,
                score_road(r)
            ])

    return Response(output.getvalue(), mimetype="text/csv")