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
# DASHBOARD
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

# =========================
# ROADS
# =========================

@app.route("/roads")
def roads():
    return render_template(
        "roads.html",
        roads=Road.query.all(),
        is_admin=request.args.get("key") == ADMIN_KEY
    )

@app.route("/roads/new", methods=["GET","POST"])
@require_admin
def road_new():
    if request.method == "POST":
        db.session.add(Road(
            name=request.form["name"],
            segment_name=request.form["segment_name"],
            surface_type=request.form.get("surface_type"),
            length_miles=float(request.form.get("length_miles") or 0),
            importance=request.form.get("importance"),
            condition=request.form.get("condition"),
            traffic_level=request.form.get("traffic_level")
        ))
        db.session.commit()
        return redirect(url_for("roads") + "?key=" + ADMIN_KEY)
    return render_template("road_form.html")

@app.route("/roads/<int:id>/edit", methods=["GET","POST"])
@require_admin
def road_edit(id):
    r = Road.query.get_or_404(id)
    if request.method == "POST":
        r.name = request.form["name"]
        r.segment_name = request.form["segment_name"]
        r.surface_type = request.form.get("surface_type")
        r.length_miles = float(request.form.get("length_miles") or 0)
        r.importance = request.form.get("importance")
        r.condition = request.form.get("condition")
        r.traffic_level = request.form.get("traffic_level")
        db.session.commit()
        return redirect(url_for("roads") + "?key=" + ADMIN_KEY)
    return render_template("road_form.html", road=r)

# =========================
# WORK ORDERS
# =========================

@app.route("/work-orders")
def work_orders():
    return render_template(
        "work_orders.html",
        work_orders=WorkOrder.query.all(),
        is_admin=request.args.get("key") == ADMIN_KEY
    )

@app.route("/work-orders/new", methods=["GET","POST"])
@require_admin
def work_order_new():
    if request.method == "POST":
        road = Road.query.get(request.form["road_id"])

        db.session.add(WorkOrder(
            title=request.form["title"],
            road=road,
            work_type=request.form.get("work_type"),
            priority=request.form.get("priority"),
            status=request.form.get("status"),
            planned_date=request.form.get("planned_date"),
            completed_date=request.form.get("completed_date"),
            estimated_cost=float(request.form.get("estimated_cost") or 0),
            actual_cost=float(request.form.get("actual_cost") or 0)
        ))

        db.session.commit()
        return redirect(url_for("work_orders") + "?key=" + ADMIN_KEY)

    return render_template("work_order_form.html", roads=Road.query.all())

@app.route("/work-orders/<int:id>/edit", methods=["GET","POST"])
@require_admin
def work_order_edit(id):
    w = WorkOrder.query.get_or_404(id)

    if request.method == "POST":
        w.title = request.form["title"]
        w.work_type = request.form.get("work_type")
        w.priority = request.form.get("priority")
        w.status = request.form.get("status")
        w.planned_date = request.form.get("planned_date")
        w.completed_date = request.form.get("completed_date")
        w.estimated_cost = float(request.form.get("estimated_cost") or 0)
        w.actual_cost = float(request.form.get("actual_cost") or 0)

        db.session.commit()
        return redirect(url_for("work_orders") + "?key=" + ADMIN_KEY)

    return render_template("work_order_form.html", wo=w, roads=Road.query.all())

# =========================
# EXPORT
# =========================

@app.route("/export/all.csv")
@require_admin
def export_all():
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["ROADS"])
    for r in Road.query.all():
        writer.writerow([
            r.name or "",
            r.segment_name or "",
            r.surface_type or "",
            r.length_miles or 0,
            r.importance or "",
            r.condition or "",
            r.traffic_level or ""
        ])

    writer.writerow([])
    writer.writerow(["WORK_ORDERS"])
    for w in WorkOrder.query.all():
        writer.writerow([
            w.title or "",
            w.road.name if w.road else "",
            w.status or "",
            w.planned_date or "",
            w.completed_date or ""
        ])

    return Response(output.getvalue(), mimetype="text/csv")

# =========================
# IMPORT
# =========================

@app.route("/import", methods=["POST"])
@require_admin
def import_data():
    file = request.files["file"]
    reader = csv.reader(TextIOWrapper(file.stream, encoding="utf-8"))

    WorkOrder.query.delete()
    Road.query.delete()
    db.session.commit()

    mode = None

    for row in reader:
        if not row:
            continue

        if row[0] == "ROADS":
            mode = "r"
            continue
        elif row[0] == "WORK_ORDERS":
            mode = "w"
            continue

        if mode == "r" and len(row) >= 7:
            db.session.add(Road(
                name=row[0],
                segment_name=row[1],
                surface_type=row[2],
                length_miles=float(row[3] or 0),
                importance=row[4],
                condition=row[5],
                traffic_level=row[6]
            ))

        elif mode == "w" and len(row) >= 5:
            road = Road.query.filter_by(name=row[1]).first()
            db.session.add(WorkOrder(
                title=row[0],
                road=road,
                status=row[2],
                planned_date=row[3],
                completed_date=row[4]
            ))

    db.session.commit()
    return redirect(url_for("roads") + "?key=" + ADMIN_KEY)

# =========================
# PUBLIC
# =========================

@app.route("/public")
def public():
    return render_template(
        "public.html",
        roads=Road.query.all(),
        work_orders=WorkOrder.query.all()
    )