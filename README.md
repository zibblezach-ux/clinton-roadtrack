# Clinton RoadTrack MVP

A working MVP road-management tool modeled on key public-works asset-management outputs:
road inventory, segmented roads, good/fair/poor condition tracking, work orders, citizen issue intake, priority scoring, CSV exports, and a public transparency dashboard.

## What this is
This is a demo / MVP. It is not an official county record system until hosted, secured, tested, and adopted by the responsible government body.

## Run locally

1. Install Python 3.11+
2. Open this folder in a terminal
3. Create a virtual environment:

```bash
python -m venv .venv
```

4. Activate it:

Windows:
```bash
.venv\Scripts\activate
```

Mac/Linux:
```bash
source .venv/bin/activate
```

5. Install requirements:

```bash
pip install -r requirements.txt
```

6. Seed sample data:

```bash
flask --app app seed
```

7. Run:

```bash
flask --app app run
```

Then open:
http://127.0.0.1:5000

## Public dashboard
Go to:
http://127.0.0.1:5000/public

## Main features

- Road segment inventory
- Good / Fair / Poor condition ratings
- Traffic level
- Importance tags such as school route, emergency route, farm access
- Simple priority scoring
- Full work orders
- Planned / In Progress / Completed / Deferred status
- Citizen issue submission form
- CSV exports

## Deployment note

This will not run inside Hostinger Website Builder as a normal embedded HTML block.
For a live demo, deploy it to Render, Railway, Fly.io, or Hostinger VPS, then link or iframe it from your website.
