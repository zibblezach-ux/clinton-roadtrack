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
    condition = db.Column(db.String(20))
    traffic_level = db.Column(db.String(20))

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_id = db.Column(db.Integer, db.ForeignKey("road.id"))
    road = db.relationship("Road")
    title = db.Column(db.String(160))
    status = db.Column(db.String(30))
    planned_date = db.Column(db.String(20))
    completed_date = db.Column(db.String(20))

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
            condition=request.form["condition"],
            traffic_level=request.form["traffic_level"]
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
        r.condition = request.form["condition"]
        r.traffic_level = request.form["traffic_level"]
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
            status=request.form["status"],
            planned_date=request.form["planned_date"],
            completed_date=request.form["completed_date"]
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
        w.status = request.form["status"]
        w.planned_date = request.form["planned_date"]
        w.completed_date = request.form["completed_date"]
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
        writer.writerow([r.name, r.segment_name, r.condition, r.traffic_level])

    writer.writerow([])
    writer.writerow(["WORK_ORDERS"])
    for w in WorkOrder.query.all():
        writer.writerow([w.title, w.road.name if w.road else "", w.status, w.planned_date, w.completed_date])

    return Response(output.getvalue(), mimetype="text/csv")

# =========================
# IMPORT (OVERWRITES DATA)
# =========================

@app.route("/import", methods=["POST"])
@require_admin
def import_data():
    file = request.files["file"]
    reader = csv.reader(TextIOWrapper(file.stream, encoding="utf-8"))

    # 🔥 CLEAR EXISTING DATA
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

        if mode == "r" and len(row) >= 4:
            db.session.add(Road(
                name=row[0],
                segment_name=row[1],
                condition=row[2],
                traffic_level=row[3]
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