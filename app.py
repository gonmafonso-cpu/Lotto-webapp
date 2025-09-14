from flask import Flask, render_template, request
import pandas as pd
import random
from collections import defaultdict

app = Flask(__name__)

CSV_FILE = "lotto_data.csv"

# -----------------------------
# Load historical CSV
# -----------------------------
def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        df = df.fillna("")
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=["Date", "Actual", "Prediction"])

# -----------------------------
# Probability-based prediction
# -----------------------------
def generate_prediction(df):
    number_counts = defaultdict(int)
    star_counts = defaultdict(int)
    co_occurrence = defaultdict(lambda: defaultdict(int))

    # Count frequencies & co-occurrences
    for _, row in df.iterrows():
        if row["Actual"]:
            nums_part, stars_part = row["Actual"].split("/")
            nums = [int(x) for x in nums_part.split(";")]
            stars = [int(x) for x in stars_part.split(";")]

            for n in nums:
                number_counts[n] += 2
            for s in stars:
                star_counts[s] += 2

            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    co_occurrence[nums[i]][nums[j]] += 1
                    co_occurrence[nums[j]][nums[i]] += 1

        if row["Prediction"]:
            try:
                nums_part, stars_part = row["Prediction"].split("/")
                nums = [int(x) for x in nums_part.split(";")]
                stars = [int(x) for x in stars_part.split(";")]

                for n in nums:
                    number_counts[n] += 1
                for s in stars:
                    star_counts[s] += 1
            except:
                pass

    # Normalize counts → probabilities
    def normalize(d, max_val):
        total = sum(d.values()) + max_val  # smoothing
        return {i: (d[i] + 1) / total for i in range(1, max_val + 1)}

    number_probs = normalize(number_counts, 50)
    star_probs = normalize(star_counts, 12)

    # Sample numbers with co-occurrence bias
    chosen_numbers = []
    while len(chosen_numbers) < 5:
        weights = []
        for i in range(1, 51):
            if i in chosen_numbers:
                weights.append(0)
            else:
                base = number_probs[i]
                bonus = sum(co_occurrence[i][n] for n in chosen_numbers)
                weights.append(base + bonus * 0.05)
        chosen = random.choices(range(1, 51), weights=weights, k=1)[0]
        chosen_numbers.append(chosen)

    # Sample stars
    stars = random.choices(range(1, 13), weights=[star_probs[i] for i in range(1, 13)], k=2)

    return sorted(chosen_numbers), sorted(stars)

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    df = load_data()
    return render_template("index.html", records=df.to_dict(orient="records"))

@app.route("/predict", methods=["POST"])
def predict():
    df = load_data()
    nums, stars = generate_prediction(df)
    return render_template("index.html", 
                           records=df.to_dict(orient="records"),
                           prediction={"numbers": nums, "stars": stars})

if __name__ == "__main__":
    app.run(debug=True)

