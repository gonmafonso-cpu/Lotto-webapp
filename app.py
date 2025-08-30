from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lotto.db'
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
    Parse a key like '1,5,12,20,33|2,7' into (numbers_list, stars_list).
    Validates counts, ranges, and uniqueness.
    """
    if "|" not in key_str:
        raise ValueError("Key must contain a '|' separating main numbers and stars, e.g. 1,5,12,20,33|2,7")

    left, right = key_str.split("|", 1)
    nums = [int(x) for x in left.replace(" ", "").split(",") if x != ""]
    stars = [int(x) for x in right.replace(" ", "").split(",") if x != ""]

    if len(nums) != 5:
        raise ValueError("Main numbers must contain exactly 5 integers.")
    if len(set(nums)) != 5:
        raise ValueError("Main numbers must be unique.")
    if not all(1 <= n <= 50 for n in nums):
        raise ValueError("Main numbers must be in the range 1–50.")

    if len(stars) != 2:
        raise ValueError("Stars must contain exactly 2 integers.")
    if len(set(stars)) != 2:
        raise ValueError("Stars must be unique.")
    if not all(1 <= s <= 12 for s in stars):
        raise ValueError("Stars must be in the range 1–12.")

    # Store sorted for consistency
    nums = sorted(nums)
    stars = sorted(stars)
    return nums, stars

def format_key(nums, stars):
    """Format back to 'n1,n2,n3,n4,n5|s1,s2' (no spaces)."""
    return f"{','.join(map(str, nums))}|{','.join(map(str, stars))}"

def generate_prediction():
    """Simple random generator (5 from 1–50, 2 from 1–12)."""
    nums = sorted(random.sample(range(1, 51), 5))
    stars = sorted(random.sample(range(1, 13), 2))
    return nums, stars

# ---------- Routes ----------

@app.route("/")
def index():
    # Build records for the table in the template: [{date: 'YYYY-MM-DD', key: '...|...'}, ...]
    rows = HistoricalData.query.order_by(HistoricalData.date.desc()).all()
    records = []
    for r in rows:
        key = format_key([int(x) for x in r.numbers.split(",")], [int(x) for x in r.stars.split(",")])
        records.append({"date": r.date.isoformat(), "key": key})

    # Show latest prediction (if any)
    latest_pred = Prediction.query.order_by(Prediction.id.desc()).first()
    predictions = None
    if latest_pred:
        predictions = {
            "date": latest_pred.date.isoformat(),
            "numbers": latest_pred.predicted_numbers,
            "stars": latest_pred.predicted_stars
        }

    return render_template("index.html", records=records, predictions=predictions)

@app.route("/add_historical", methods=["POST"])
def add_historical():
    date_str = request.form.get("date", "").strip()
    key_str = request.form.get("key", "").strip
