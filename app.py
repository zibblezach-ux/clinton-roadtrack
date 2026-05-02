from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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
    traffic_level = db.Column(db.String(20))
    importance = db.Column(db.String(120))
    condition = db.Column(db.String(20))

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_id = db.Column(db.Integer, db.ForeignKey("road.id"))
    road = db.relationship("Road")
    title = db.Column(db.String(160))
    status = db.Column(db.String(30))
    planned_date = db.Column(db.String(20))
    completed_date = db.Column(db.String(20))

class CitizenIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_name = db.Column(db.String(140))
    description = db.Column(db.Text)
    status = db.Column(db.String(30))

# =========================
# ROUTES
# =========================

@app.route("/")
def dashboard():
    roads = Road.query.all()
    work_orders = WorkOrder.query.all()
    issues = CitizenIssue.query.all()
    return render_template("dashboard.html", roads=roads, work_orders=work_orders, issues=issues)

@app.route("/roads")
def roads():
    roads = Road.query.all()
    is_admin = request.args.get("key") == ADMIN_KEY
    return render_template("roads.html", roads=roads, is_admin=is_admin)

@app.route("/work-orders")
def work_orders():
    work_orders = WorkOrder.query.all()
    is_admin = request.args.get("key") == ADMIN_KEY
    return render_template("work_orders.html", work_orders=work_orders, is_admin=is_admin)

@app.route("/public")
def public():
    return render_template("public.html")

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

    writer.writerow([])
    writer.writerow(["ISSUES"])
    for i in CitizenIssue.query.all():
        writer.writerow([i.road_name, i.description, i.status])

    return Response(output.getvalue(), mimetype="text/csv")

# =========================
# IMPORT (FIXED)
# =========================

@app.route("/import", methods=["POST"])
@require_admin
def import_data():
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]
    stream = TextIOWrapper(file.stream, encoding="utf-8")
    reader = csv.reader(stream)

    mode = None

    for row in reader:
        if not row:
            continue

        if row[0] == "ROADS":
            mode = "roads"
            continue
        elif row[0] == "WORK_ORDERS":
            mode = "work"
            continue
        elif row[0] == "ISSUES":
            mode = "issues"
            continue

        try:
            if mode == "roads" and len(row) >= 4:
                db.session.add(Road(
                    name=row[0],
                    segment_name=row[1],
                    condition=row[2],
                    traffic_level=row[3]
                ))

            elif mode == "work" and len(row) >= 5:
                road = Road.query.filter_by(name=row[1]).first()
                db.session.add(WorkOrder(
                    title=row[0],
                    road=road,
                    status=row[2],
                    planned_date=row[3],
                    completed_date=row[4]
                ))

            elif mode == "issues" and len(row) >= 3:
                db.session.add(CitizenIssue(
                    road_name=row[0],
                    description=row[1],
                    status=row[2]
                ))

        except Exception:
            continue  # skip bad rows safely

    db.session.commit()

    return redirect(url_for("roads") + f"?key={ADMIN_KEY}")