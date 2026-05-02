from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import csv
from io import StringIO
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-before-public-use")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///roadtrack.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class Road(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    segment_name = db.Column(db.String(140), nullable=False)
    start_point = db.Column(db.String(200))
    end_point = db.Column(db.String(200))
    surface_type = db.Column(db.String(60), default="Gravel")
    length_miles = db.Column(db.Float, default=0)
    traffic_level = db.Column(db.String(20), default="Medium")
    importance = db.Column(db.String(120))
    condition = db.Column(db.String(20), default="Fair")  # Good/Fair/Poor
    last_inspected = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_id = db.Column(db.Integer, db.ForeignKey("road.id"), nullable=False)
    road = db.relationship("Road", backref="work_orders")
    title = db.Column(db.String(160), nullable=False)
    work_type = db.Column(db.String(80), default="Grading")
    status = db.Column(db.String(30), default="Planned") # Planned/In Progress/Completed/Deferred
    priority = db.Column(db.String(20), default="Medium")
    requested_by = db.Column(db.String(120))
    planned_date = db.Column(db.String(20))
    completed_date = db.Column(db.String(20))
    crew = db.Column(db.String(120))
    materials = db.Column(db.String(200))
    estimated_cost = db.Column(db.Float, default=0)
    actual_cost = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CitizenIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    road_name = db.Column(db.String(140), nullable=False)
    location_detail = db.Column(db.String(220))
    issue_type = db.Column(db.String(80), default="Road condition")
    description = db.Column(db.Text, nullable=False)
    submitter_name = db.Column(db.String(120))
    submitter_contact = db.Column(db.String(160))
    status = db.Column(db.String(30), default="Received")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def score_road(road):
    score = 0
    if road.condition == "Poor": score += 40
    elif road.condition == "Fair": score += 20
    else: score += 5
    if road.traffic_level == "High": score += 30
    elif road.traffic_level == "Medium": score += 15
    else: score += 5
    imp = (road.importance or "").lower()
    for word in ["school", "emergency", "mail", "farm", "market", "business", "bridge"]:
        if word in imp:
            score += 5
    return min(score, 100)

@app.route("/")
def dashboard():
    roads = Road.query.order_by(Road.name, Road.segment_name).all()
    work_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(8).all()
    issues = CitizenIssue.query.order_by(CitizenIssue.created_at.desc()).limit(8).all()
    counts = {
        "roads": Road.query.count(),
        "planned": WorkOrder.query.filter_by(status="Planned").count(),
        "completed": WorkOrder.query.filter_by(status="Completed").count(),
        "issues": CitizenIssue.query.count(),
        "poor": Road.query.filter_by(condition="Poor").count()
    }
    scored = sorted([(r, score_road(r)) for r in roads], key=lambda x: x[1], reverse=True)[:8]
    return render_template("dashboard.html", counts=counts, work_orders=work_orders, issues=issues, scored=scored)

@app.route("/roads")
def roads():
    q = request.args.get("q", "")
    query = Road.query
    if q:
        query = query.filter((Road.name.contains(q)) | (Road.segment_name.contains(q)))
    roads = query.order_by(Road.name, Road.segment_name).all()
    return render_template("roads.html", roads=roads, q=q, score_road=score_road)

@app.route("/roads/new", methods=["GET", "POST"])
def road_new():
    if request.method == "POST":
        road = Road(
            name=request.form["name"],
            segment_name=request.form["segment_name"],
            start_point=request.form.get("start_point"),
            end_point=request.form.get("end_point"),
            surface_type=request.form.get("surface_type"),
            length_miles=float(request.form.get("length_miles") or 0),
            traffic_level=request.form.get("traffic_level"),
            importance=request.form.get("importance"),
            condition=request.form.get("condition"),
            last_inspected=request.form.get("last_inspected"),
            notes=request.form.get("notes"),
        )
        db.session.add(road); db.session.commit()
        flash("Road segment added.")
        return redirect(url_for("roads"))
    return render_template("road_form.html", road=None)

@app.route("/roads/<int:road_id>/edit", methods=["GET", "POST"])
def road_edit(road_id):
    road = Road.query.get_or_404(road_id)
    if request.method == "POST":
        for field in ["name","segment_name","start_point","end_point","surface_type","traffic_level","importance","condition","last_inspected","notes"]:
            setattr(road, field, request.form.get(field))
        road.length_miles = float(request.form.get("length_miles") or 0)
        db.session.commit()
        flash("Road segment updated.")
        return redirect(url_for("roads"))
    return render_template("road_form.html", road=road)

@app.route("/work-orders")
def work_orders():
    work_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).all()
    return render_template("work_orders.html", work_orders=work_orders)

@app.route("/work-orders/new", methods=["GET", "POST"])
def work_order_new():
    roads = Road.query.order_by(Road.name).all()
    if not roads:
        flash("Add a road segment before creating a work order.")
        return redirect(url_for("road_new"))
    if request.method == "POST":
        wo = WorkOrder(
            road_id=int(request.form["road_id"]),
            title=request.form["title"],
            work_type=request.form.get("work_type"),
            status=request.form.get("status"),
            priority=request.form.get("priority"),
            requested_by=request.form.get("requested_by"),
            planned_date=request.form.get("planned_date"),
            completed_date=request.form.get("completed_date"),
            crew=request.form.get("crew"),
            materials=request.form.get("materials"),
            estimated_cost=float(request.form.get("estimated_cost") or 0),
            actual_cost=float(request.form.get("actual_cost") or 0),
            notes=request.form.get("notes"),
        )
        db.session.add(wo); db.session.commit()
        flash("Work order created.")
        return redirect(url_for("work_orders"))
    return render_template("work_order_form.html", roads=roads, wo=None)

@app.route("/work-orders/<int:wo_id>/edit", methods=["GET", "POST"])
def work_order_edit(wo_id):
    wo = WorkOrder.query.get_or_404(wo_id)
    roads = Road.query.order_by(Road.name).all()
    if request.method == "POST":
        wo.road_id = int(request.form["road_id"])
        for field in ["title","work_type","status","priority","requested_by","planned_date","completed_date","crew","materials","notes"]:
            setattr(wo, field, request.form.get(field))
        wo.estimated_cost = float(request.form.get("estimated_cost") or 0)
        wo.actual_cost = float(request.form.get("actual_cost") or 0)
        db.session.commit()
        flash("Work order updated.")
        return redirect(url_for("work_orders"))
    return render_template("work_order_form.html", roads=roads, wo=wo)

@app.route("/issues", methods=["GET", "POST"])
def issues():
    if request.method == "POST":
        issue = CitizenIssue(
            road_name=request.form["road_name"],
            location_detail=request.form.get("location_detail"),
            issue_type=request.form.get("issue_type"),
            description=request.form["description"],
            submitter_name=request.form.get("submitter_name"),
            submitter_contact=request.form.get("submitter_contact"),
        )
        db.session.add(issue); db.session.commit()
        flash("Issue submitted.")
        return redirect(url_for("public"))
    issues = CitizenIssue.query.order_by(CitizenIssue.created_at.desc()).all()
    return render_template("issues.html", issues=issues)

@app.route("/issues/<int:issue_id>/status", methods=["POST"])
def issue_status(issue_id):
    issue = CitizenIssue.query.get_or_404(issue_id)
    issue.status = request.form.get("status")
    db.session.commit()
    return redirect(url_for("issues"))

@app.route("/public")
def public():
    roads = Road.query.order_by(Road.name).all()
    completed = WorkOrder.query.filter_by(status="Completed").order_by(WorkOrder.completed_date.desc()).limit(10).all()
    planned = WorkOrder.query.filter(WorkOrder.status.in_(["Planned","In Progress"])).order_by(WorkOrder.planned_date.asc()).limit(10).all()
    return render_template("public.html", roads=roads, completed=completed, planned=planned, score_road=score_road)

@app.route("/export/<kind>.csv")
def export_csv(kind):
    output = StringIO()
    writer = csv.writer(output)
    if kind == "roads":
        writer.writerow(["name","segment","start","end","surface","length_miles","traffic","importance","condition","last_inspected","score","notes"])
        for r in Road.query.order_by(Road.name).all():
            writer.writerow([r.name,r.segment_name,r.start_point,r.end_point,r.surface_type,r.length_miles,r.traffic_level,r.importance,r.condition,r.last_inspected,score_road(r),r.notes])
    elif kind == "work_orders":
        writer.writerow(["road","segment","title","type","status","priority","planned","completed","crew","materials","estimated_cost","actual_cost","notes"])
        for w in WorkOrder.query.order_by(WorkOrder.created_at.desc()).all():
            writer.writerow([w.road.name,w.road.segment_name,w.title,w.work_type,w.status,w.priority,w.planned_date,w.completed_date,w.crew,w.materials,w.estimated_cost,w.actual_cost,w.notes])
    elif kind == "issues":
        writer.writerow(["road_name","location","issue_type","description","submitter","contact","status","created_at"])
        for i in CitizenIssue.query.order_by(CitizenIssue.created_at.desc()).all():
            writer.writerow([i.road_name,i.location_detail,i.issue_type,i.description,i.submitter_name,i.submitter_contact,i.status,i.created_at])
    else:
        return "Unknown export", 404
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={kind}.csv"})

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialized.")

@app.cli.command("seed")
def seed():
    db.create_all()
    if Road.query.count() == 0:
        sample_roads = [
            Road(name="SW Rogers Road", segment_name="Segment A", start_point="County line", end_point="Hwy junction", surface_type="Gravel", length_miles=2.4, traffic_level="High", importance="school route, mail route", condition="Poor", last_inspected="2026-05-01"),
            Road(name="SE Prairie Lane", segment_name="Segment B", start_point="Farm entrance", end_point="Bridge", surface_type="Gravel", length_miles=1.7, traffic_level="Medium", importance="farm access", condition="Fair", last_inspected="2026-04-22"),
            Road(name="NW Ridge Road", segment_name="North hill", start_point="Old barn", end_point="Creek crossing", surface_type="Gravel", length_miles=3.1, traffic_level="Low", importance="residential", condition="Good", last_inspected="2026-04-10"),
        ]
        db.session.add_all(sample_roads); db.session.commit()
        db.session.add_all([
            WorkOrder(road_id=sample_roads[0].id, title="Grade and add rock to worst washboard section", work_type="Grading/Rock", status="Planned", priority="High", planned_date="2026-05-15", estimated_cost=2800),
            WorkOrder(road_id=sample_roads[1].id, title="Inspect culvert and ditch drainage", work_type="Inspection", status="In Progress", priority="Medium", planned_date="2026-05-10", estimated_cost=450),
            WorkOrder(road_id=sample_roads[2].id, title="Routine grading", work_type="Grading", status="Completed", priority="Low", planned_date="2026-04-15", completed_date="2026-04-17", actual_cost=600),
        ])
        db.session.commit()
    print("Seed data loaded.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
