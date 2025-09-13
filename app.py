from flask import Flask, render_template, request, redirect, url_for, send_file
import pandas as pd
import random
import os
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CSV_FILE = os.path.join(UPLOAD_FOLDER, "lotto.csv")


def parse_key(key):
    """Parse key string '1;2;3;4;5/6;7' -> (numbers, stars)."""
    if not key or pd.isna(key):
        return [], []
    try:
        numbers, stars = key.split("/")
        nums = [int(x) for x in numbers.split(";")]
        stars = [int(x) for x in stars.split(";")]
        return nums, stars
    except Exception:
        return [], []


def generate_prediction(df):
    """Generate a prediction based on frequency trends in CSV."""
    number_counts = {i: 0 for i in range(1, 51)}
    star_counts = {i: 0 for i in range(1, 13)}

    for _, row in df.iterrows():
        actual_nums, actual_stars = parse_key(row["Actual"])
        pred_nums, pred_stars = parse_key(row.get("Prediction", ""))

        for n in actual_nums + pred_nums:
            if n in number_counts:
                number_counts[n] += 1
        for s in actual_stars + pred_stars:
            if s in star_counts:
                star_counts[s] += 1

    # Pick most frequent numbers/stars (weighted random choice)
    nums = sorted(random.sample(
        population=list(number_counts.keys()),
        k=5
    ), key=lambda x: number_counts[x], reverse=True)

    stars = sorted(random.sample(
        population=list(star_counts.keys()),
        k=2
    ), key=lambda x: star_counts[x], reverse=True)

    return nums, stars


@app.route("/", methods=["GET", "POST"])
def index():
    df = pd.DataFrame()
    prediction = None

    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)

    if request.method == "POST":
        if "csv_file" in request.files:
            file = request.files["csv_file"]
            if file.filename.endswith(".csv"):
                file.save(CSV_FILE)
                return redirect(url_for("index"))

        if "predict" in request.form:
            if not df.empty:
                nums, stars = generate_prediction(df)
                today = datetime.today().strftime("%Y-%m-%d")
                key = f"{';'.join(map(str, nums))}/{';'.join(map(str, stars))}"
                new_row = {"Date": today, "Actual": "", "Prediction": key}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(CSV_FILE, index=False)
                prediction = key

    return render_template("index.html", tables=df.to_html(classes="data"), prediction=prediction)


@app.route("/download")
def download():
    if os.path.exists(CSV_FILE):
        return send_file(CSV_FILE, as_attachment=True)
    return "No CSV available", 404


if __name__ == "__main__":
    app.run(debug=True)


