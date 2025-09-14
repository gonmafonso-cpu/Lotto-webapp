from flask import Flask, render_template, request, redirect, url_for, send_file
import os, csv, random
from datetime import datetime

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
CSV_PATH = os.path.join(UPLOAD_DIR, "lotto.csv")

# -----------------------------
# Helpers: parse & format keys
# -----------------------------
def parse_key(key: str):
    """'n;n;n;n;n/s;s' -> (list5, list2). Returns ([],[]) if empty/invalid."""
    if not key:
        return [], []
    key = key.strip()
    if "/" not in key:
        return [], []
    left, right = key.split("/", 1)
    try:
        nums = [int(x) for x in left.replace(" ", "").split(";") if x]
        stars = [int(x) for x in right.replace(" ", "").split(";") if x]
    except ValueError:
        return [], []
    return nums, stars

def format_key(nums, stars):
    return f"{';'.join(map(str, nums))}/{';'.join(map(str, stars))}"

# -----------------------------
# CSV I/O (no external libs)
# -----------------------------
def read_rows(path: str):
    """Return rows as list of dicts with fields: Date, Actual, Prediction (typo tolerant)."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            date = (row.get("Date") or row.get("date") or "").strip()
            actual = (row.get("Actual") or row.get("actual") or "").strip()
            prediction = (row.get("Prediction") or row.get("Predictiom") or row.get("prediction") or "").strip()
            out.append({"Date": date, "Actual": actual, "Prediction": prediction})
    return out

def write_rows(path: str, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Date", "Actual", "Prediction"])
        w.writeheader()
        w.writerows(rows)

# -----------------------------
# Probability-driven predictor
# -----------------------------
def build_stats(rows):
    """
    Build frequency counts and co-occurrence matrix.
    Actual gets weight 2, Prediction weight 1.
    """
    num_freq = {i: 0 for i in range(1, 51)}
    star_freq = {i: 0 for i in range(1, 13)}
    # co-occurrence among numbers (1..50)
    co = {i: {j: 0 for j in range(1, 51)} for i in range(1, 51)}

    for r in rows:
        a_nums, a_stars = parse_key(r.get("Actual", ""))
        p_nums, p_stars = parse_key(r.get("Prediction", ""))

        for n in a_nums:
            if 1 <= n <= 50: num_freq[n] += 2
        for n in p_nums:
            if 1 <= n <= 50: num_freq[n] += 1

        for s in a_stars:
            if 1 <= s <= 12: star_freq[s] += 2
        for s in p_stars:
            if 1 <= s <= 12: star_freq[s] += 1

        # co-occurrence only from Actual (more reliable)
        a_nums = [n for n in a_nums if 1 <= n <= 50]
        for i in range(len(a_nums)):
            for j in range(i + 1, len(a_nums)):
                x, y = a_nums[i], a_nums[j]
                if x != y:
                    co[x][y] += 1
                    co[y][x] += 1

    return num_freq, star_freq, co

def normalize_probs(counts: dict, domain_size: int, alpha: float = 1.0):
    """
    Turn counts into a probability mass with Laplace smoothing.
    Returns list of weights aligned to 1..domain_size.
    """
    total = sum(counts.values()) + alpha * domain_size
    if total <= 0:
        return [1.0 / domain_size] * domain_size
    return [ (counts.get(i,0) + alpha) / total for i in range(1, domain_size + 1) ]

def sample_without_replacement(domain, weights, k):
    """
    Sample k unique items using weights with replacement turned off.
    Recompute weights after each pick.
    """
    chosen = []
    available = domain[:]
    current_weights = weights[:]
    for _ in range(k):
        # If all weights are zero, use uniform
        if sum(current_weights) <= 0:
            idx = random.randrange(len(available))
        else:
            idx = random.choices(range(len(available)), weights=current_weights, k=1)[0]
        chosen_item = available.pop(idx)
        chosen.append(chosen_item)
        current_weights.pop(idx)
    return chosen

def probability_based_prediction(rows):
    """
    Numbers: sample 5 without replacement, each step reweight by:
      base_prob + beta * sum(co-occurrence with already-chosen)
    Stars: sample 2 without replacement using star probabilities.
    """
    num_freq, star_freq, co = build_stats(rows)
    base_num_probs = normalize_probs(num_freq, 50, alpha=1.0)
    base_star_probs = normalize_probs(star_freq, 12, alpha=1.0)

    # Numbers with co-occurrence bias
    picked = []
    candidates = list(range(1, 51))
    # Start with a sample by base probabilities
    first = random.choices(candidates, weights=base_num_probs, k=1)[0]
    picked.append(first)
    candidates.remove(first)

    beta = 0.05  # co-occurrence influence factor
    while len(picked) < 5:
        # build weights for remaining candidates
        weights = []
        for c in candidates:
            base = base_num_probs[c - 1]
            bonus = sum(co[c][p] for p in picked) * beta
            weights.append(max(base + bonus, 0.0))
        # if all zero, fall back to uniform
        if sum(weights) <= 0:
            next_pick = random.choice(candidates)
        else:
            next_pick = random.choices(candidates, weights=weights, k=1)[0]
        picked.append(next_pick)
        candidates.remove(next_pick)

    picked = sorted(picked)

    # Stars: just probability sampling without replacement
    star_domain = list(range(1, 13))
    stars = sample_without_replacement(star_domain, base_star_probs[:], 2)
    stars = sorted(stars)

    return picked, stars

# -----------------------------
# Routes
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    rows = read_rows(CSV_PATH)
    return render_template("index.html", rows=rows, new_prediction=None)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("csv_file")
    if not file or not file.filename.lower().endswith(".csv"):
        return "Please choose a .csv file with headers Date,Actual,Prediction", 400
    file.save(CSV_PATH)
    return redirect(url_for("home"))

@app.route("/predict", methods=["POST"])
def predict():
    rows = read_rows(CSV_PATH)
    nums, stars = probability_based_prediction(rows)
    key = format_key(nums, stars)

    # append new row with today's date and the app prediction
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows.append({"Date": today, "Actual": "", "Prediction": key})
    write_rows(CSV_PATH, rows)

    return render_template("index.html", rows=rows, new_prediction=key)

@app.route("/download", methods=["GET"])
def download():
    if not os.path.exists(CSV_PATH):
        return "No CSV found", 404
    return send_file(CSV_PATH, as_attachment=True, download_name="lotto.csv")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
    
