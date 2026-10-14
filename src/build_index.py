"""
Add the heat risk index to data/processed/wards.csv.

IPCC framing: risk comes from hazard (how hot), exposure (how many people)
and vulnerability (how badly heat hurts them there).

    hazard        = percentile of land surface temperature
    exposure      = percentile of population density
    vulnerability = mean of percentiles: low green cover, high built-up, poor housing

Two ways to combine them are both written out, so the map can switch:
    risk_score      multiply: a ward must be bad on all three to rank high (default)
    risk_score_add  average:  one very bad ingredient can push a ward up

Run: python src/build_index.py
"""

import pandas as pd

from config import WARDS_CSV


def pct(s):
    """Share of wards this ward is at or above, in (0, 1].

    Percentiles instead of min-max: one extreme ward (Padarayanapura is ~5x the
    median density) can't squash everyone else, and no ward gets exactly 0,
    which would zero its risk under multiplication.
    """
    return s.rank(pct=True)


def build_index(df):
    needed = ["lst_c", "ndvi", "ndbi", "pop_density", "housing_vuln"]
    missing = df[needed].isna().any()
    if missing.any():
        raise SystemExit(f"Missing values in {list(missing[missing].index)}. Run fetch_lst.py and build_wards.py first.")

    df["hazard"] = pct(df["lst_c"])
    df["exposure"] = pct(df["pop_density"])
    # Less green is worse, so rank NDVI from the greenest down.
    df["vulnerability"] = (pct(-df["ndvi"]) + pct(df["ndbi"]) + pct(df["housing_vuln"])) / 3

    h, e, v = df["hazard"], df["exposure"], df["vulnerability"]
    df["risk_score"] = h * e * v
    df["risk_score_add"] = (h + e + v) / 3
    df["risk_rank"] = df["risk_score"].rank(ascending=False, method="first").astype(int)
    df["risk_rank_add"] = df["risk_score_add"].rank(ascending=False, method="first").astype(int)
    return df


def check(df):
    for col in ["hazard", "exposure", "vulnerability", "risk_score", "risk_score_add"]:
        assert df[col].between(0, 1, inclusive="right").all(), f"{col} outside (0, 1]"
    for col in ["risk_rank", "risk_rank_add"]:
        assert sorted(df[col]) == list(range(1, len(df) + 1)), f"{col} is not 1..N"


def main():
    df = build_index(pd.read_csv(WARDS_CSV))
    check(df)
    df.round(4).to_csv(WARDS_CSV, index=False)
    print(f"Risk index written to {WARDS_CSV}\n\nTop 10 wards (multiply):")
    cols = ["risk_rank", "ward_name", "risk_score", "hazard", "exposure", "vulnerability", "risk_rank_add"]
    print(df.nsmallest(10, "risk_rank")[cols].round(2).to_string(index=False))

    top_m = set(df.nsmallest(20, "risk_rank")["ward_id"])
    top_a = set(df.nsmallest(20, "risk_rank_add")["ward_id"])
    print(f"\nTop-20 overlap between multiply and add: {len(top_m & top_a)} of 20")


if __name__ == "__main__":
    main()
