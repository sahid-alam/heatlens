"""
Add the heat risk index to data/processed/wards.csv.

IPCC framing: risk comes from hazard (how hot), exposure (how many people)
and vulnerability (how badly heat hurts them there).

    hazard        = normalised land surface temperature
    exposure      = normalised population density
    vulnerability = mean of low green cover, high built-up, poor housing

Run: python src/build_index.py
"""

import pandas as pd

from config import WARDS_CSV

# Open team decision: multiply or add. Multiplying means a ward needs all three
# to rank high (a hot but empty ward scores low); adding lets one factor dominate.
COMBINE = "multiply"


def minmax(s):
    # ponytail: plain min-max, one extreme ward stretches the scale;
    # clip to the 2nd-98th percentile first if that shows up.
    return (s - s.min()) / (s.max() - s.min())


def combine(h, e, v, how=COMBINE):
    return h * e * v if how == "multiply" else (h + e + v) / 3


def build_index(df):
    needed = ["lst_c", "ndvi", "ndbi", "pop_density", "housing_vuln"]
    missing = df[needed].isna().any()
    if missing.any():
        raise SystemExit(f"Missing values in {list(missing[missing].index)}. Run fetch_lst.py and build_wards.py first.")

    df["hazard"] = minmax(df["lst_c"])
    df["exposure"] = minmax(df["pop_density"])
    df["vulnerability"] = (1 - minmax(df["ndvi"]) + minmax(df["ndbi"]) + df["housing_vuln"]) / 3
    df["risk_score"] = minmax(combine(df["hazard"], df["exposure"], df["vulnerability"]))
    df["risk_rank"] = df["risk_score"].rank(ascending=False, method="first").astype(int)
    return df


def check(df):
    for col in ["hazard", "exposure", "vulnerability", "risk_score"]:
        assert df[col].between(0, 1).all(), f"{col} outside 0-1"
    assert sorted(df["risk_rank"]) == list(range(1, len(df) + 1)), "rank is not 1..N"


def main():
    df = build_index(pd.read_csv(WARDS_CSV))
    check(df)
    df.round(4).to_csv(WARDS_CSV, index=False)
    print(f"Risk index ({COMBINE}) written to {WARDS_CSV}\n\nTop 10 wards:")
    cols = ["risk_rank", "ward_name", "risk_score", "hazard", "exposure", "vulnerability"]
    print(df.nsmallest(10, "risk_rank")[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
