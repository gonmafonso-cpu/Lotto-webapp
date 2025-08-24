
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lotto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class HistoricalData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    numbers = db.Column(db.String, nullable=False)
    stars = db.Column(db.String, nullable=False)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    predicted_numbers = db.Column(db.String, nullable=False)
    predicted_stars = db.Column(db.String, nullable=False)
    actual_numbers = db.Column(db.String, nullable=True)
    actual_stars = db.Column(db.String, nullable=True)
    score = db.Column(db.String, nullable=True)

with app.app_context():
    db.create_all()

def generate_prediction():
    nums = random.sample(range(1, 51), 5)
    stars = random.sample(range(1, 13), 2)
    return nums, stars

@app.route("/")
def index():
    predictions = Prediction.query.all()
    return render_template("index.html", predictions=predictions)

@app.route("/add_historical", methods=["POST"])
def add_historical():
    date_str = request.form["date"]
    numbers = request.form["numbers"]
    stars = request.form["stars"]
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    entry = HistoricalData(date=date, numbers=numbers, stars=stars)
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/predict", methods=["POST"])
def predict():
    date_str = request.form["date"]
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    nums, stars = generate_prediction()
    pred = Prediction(date=date, predicted_numbers=",".join(map(str, nums)), predicted_stars=",".join(map(str, stars)))
    db.session.add(pred)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/update_result", methods=["POST"])
def update_result():
    date_str = request.form["date"]
    numbers = request.form["numbers"]
    stars = request.form["stars"]
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    pred = Prediction.query.filter_by(date=date).first()
    if pred:
        pred.actual_numbers = numbers
        pred.actual_stars = stars
        predicted_set = set(pred.predicted_numbers.split(","))
        actual_set = set(numbers.split(","))
        num_matches = len(predicted_set & actual_set)
        star_matches = len(set(pred.predicted_stars.split(",")) & set(stars.split(",")))
        pred.score = f"{num_matches} numbers, {star_matches} stars"
        db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
