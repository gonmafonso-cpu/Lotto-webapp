from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import os

app = Flask(__name__)

# Use Postgres if available, fallback to SQLite locally
db_url = os.environ.get("DATABASE_URL", "sqlite:///lotto.db")
# Fix Render's postgres:// to postgresql:// for SQLAlchemy compatibility
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- Models ----------

class HistoricalData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    numbers = db.Column(db.String, nullable=False)  # "n1,n2,n3,n4,n5"
    stars = db.Column(db.String, nullable=False)    # "s1,s2"

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    predicted_numbers = db.Column(db.String, nullable=False)  # "n1,n2,n3,n4,n5"
    predicted_stars = db.Column(db.String, nullable=False)    # "s1,s2"
    actual_numbers = db.Column(db.String, nullable=True)
    actual_stars = db.Column(db.String, nullable=True)
    score = db.Column(db.String, nullable=True)

with app.app_context():
    db.create_all()

# ---------- Helpers ----------

def parse_key(key_str: str):
    """
    Parse a key like '1,5,12,20,33;2,7' into (numbers_list, stars_list).
    """
    key_str = (key_str or "").strip()
    if ";" not in key_str:
        raise ValueError("Key must contain a ';' between main numbers and stars. e.g. 1,5,12,20,33;2,7")

    left, right = key_str.split(";", 1)
    nums = [int(x) for x in left.replace(" ", "").split(",") if x]
    stars = [int(x) for x in right.replace(" ", "").split(",") if x]

    if len(nums) != 5:
        raise ValueError("Main numbers must contain exactly 5 integers.")
    if len(set(nums)) != 5:
        raise ValueError("Main numbers must be unique.")
    if not all(1 <= n <= 50 for n in nums):
        raise ValueError("Main numbers must be in 1–50.")

    if len(stars) != 2:
        raise ValueError("Stars must contain exactly 2 integers.")
    if len(set(stars)) != 2:
        raise ValueError("Stars must be unique.")
    if not all(1 <= s <= 12 for s in stars):
        raise ValueError("Stars must be in 1–12.")

    return sorted(nums), sorted(stars)

def format_key(nums, stars):
    return f"{','.join(map(str, nums))};{','.join(map(str, stars))}"

def generate_prediction():
    nums = sorted(random.sample(range(1, 51), 5))
    stars = sorted(random.sample(range(1, 13), 2))
    return nums, stars

# ---------- Routes ----------

@app.route("/")
def index():
    rows = HistoricalData.query.order_by(HistoricalData.date.desc()).all()
    records = []
    for r in rows:
        key = format_key([int(x) for x in r.numbers.split(",")],
                         [int(x) for x in r.stars.split(",")])
        records.append({"date": r.date.isoformat(), "key": key})

    latest = Prediction.query.order_by(Prediction.id.desc()).first()
    predictions = None
    if latest:
        predictions = {
            "date": latest.date.isoformat(),
            "numbers": latest.predicted_numbers,
            "stars": latest.predicted_stars
        }

    return render_template("index.html", records=records, predictions=predictions)

@app.route("/add_historical", methods=["GET", "POST"])
def add_historical():
    if request.method == "GET":
        return redirect(url_for("index"))

    date_str = (request.form.get("date") or "").strip()
    key_str = (request.form.get("key") or "").strip()

    if not date_str or not key_str:
        return "Bad Request: missing 'date' or 'key'", 400

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return "Bad Request: date must be YYYY-MM-DD", 400

    try:
        nums, stars = parse_key(key_str)
    except ValueError as e:
        return f"Bad Request: {e}", 400

    existing = HistoricalData.query.filter_by(date=d).first()
    if existing:
        existing.numbers = ",".join(map(str, nums))
        existing.stars   = ",".join(map(str, stars))
    else:
        db.session.add(HistoricalData(
            date=d,
            numbers=",".join(map(str, nums)),
            stars=",".join(map(str, stars))
        ))

    db.session.commit()
    return redirect(url_for("index"))

@app.route("/predict", methods=["POST"])
def predict():
    date_str = (request.form.get("date") or "").strip()
    if not date_str:
        return "Bad Request: missing 'date'", 400
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return "Bad Request: date must be YYYY-MM-DD", 400

    nums, stars = generate_prediction()

    pred = Prediction.query.filter_by(date=d).first()
    if pred:
        pred.predicted_numbers = ",".join(map(str, nums))
        pred.predicted_stars = ",".join(map(str, stars))
    else:
        db.session.add(Prediction(
            date=d,
            predicted_numbers=",".join(map(str, nums)),
            predicted_stars=",".join(map(str, stars))
        ))

    db.session.commit()

    rows = HistoricalData.query.order_by(HistoricalData.date.desc()).all()
    records = []
    for r in rows:
        key = format_key([int(x) for x in r.numbers.split(",")],
                         [int(x) for x in r.stars.split(",")])
        records.append({"date": r.date.isoformat(), "key": key})

    predictions = {
        "date": d.isoformat(),
        "numbers": ",".join(map(str, nums)),
        "stars": ",".join(map(str, stars))
    }
    return render_template("index.html", records=records, predictions=predictions)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

