"""
Predict ward land surface temperature from physical features, then explain
each ward's prediction with SHAP. Writes lst_pred and shap_* into wards.csv.

Spatial cross-validation: neighbouring wards are alike, so a random split
would test on near-copies of the training data and flatter the score. We cut
the city into 5 regions (KMeans on ward centroids) and always test on a region
the model has not seen.

Run: python src/model.py
"""

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, cross_val_predict

from config import METRIC_CRS, PROCESSED, WARDS_CSV, WARDS_GEOJSON

FEATURES = ["ndvi", "ndbi", "pop_density"]
TARGET = "lst_c"
SEED = 0


def trees(monotonic_cst=None):
    # Small and shallow on purpose: 198 rows overfit easily.
    return HistGradientBoostingRegressor(
        max_depth=2, learning_rate=0.05, max_iter=200, min_samples_leaf=10,
        monotonic_cst=monotonic_cst, random_state=SEED,
    )


MODELS = {
    "linear": LinearRegression(),
    "boosted_trees": trees(),
    # Physics as a rule: more green can only cool, more built-up or people only heat.
    "boosted_trees_physics": trees(monotonic_cst=[-1, 1, 1]),
}

# Chosen for physically consistent explanations, not lowest error. Without the
# constraint, NDVI and NDBI (r = -0.81) trade credit and most low-green wards get
# "green cover cools you", which is backwards. Costs ~0.04 C of MAE.
CHOSEN = "boosted_trees_physics"


def spatial_groups(ward_ids, k=5):
    g = gpd.read_file(WARDS_GEOJSON)
    c = g.set_index(g["WARD_NO"].astype(int)).to_crs(METRIC_CRS).centroid.loc[ward_ids]
    xy = np.column_stack([c.x, c.y])
    return KMeans(n_clusters=k, n_init=10, random_state=SEED).fit_predict(xy)


def evaluate(X, y, groups):
    cv = GroupKFold(n_splits=len(set(groups)))
    scores = {}
    for name, model in MODELS.items():
        pred = cross_val_predict(model, X, y, cv=cv, groups=groups)
        scores[name] = {"r2": r2_score(y, pred), "mae_c": mean_absolute_error(y, pred)}
    return pd.DataFrame(scores).T


def main():
    df = pd.read_csv(WARDS_CSV)
    if df[FEATURES + [TARGET]].isna().any().any():
        raise SystemExit("Missing satellite or census values. Run fetch_lst.py and build_wards.py first.")
    X, y = df[FEATURES], df[TARGET]

    scores = evaluate(X, y, spatial_groups(df["ward_id"]))
    print("Spatial cross-validation (5 regions):")
    print(scores.round(3).to_string())
    print(f"\nUsing {CHOSEN} (see the note on CHOSEN)")

    model = MODELS[CHOSEN].fit(X, y)
    # Tree SHAP (path-dependent) is exact for tree models; the interventional
    # mode drifts by ~0.02 C on gradient boosting, failing the check below.
    explainer = shap.TreeExplainer(model) if CHOSEN != "linear" else shap.Explainer(model, X)
    sv = explainer(X)

    df["lst_pred"] = model.predict(X)
    for i, f in enumerate(FEATURES):
        df[f"shap_{f}"] = sv.values[:, i]
    # SHAP's promise: base value + contributions = the model's prediction.
    assert np.allclose(sv.base_values + sv.values.sum(axis=1), df["lst_pred"], atol=1e-3)

    df.round(4).to_csv(WARDS_CSV, index=False)
    print(f"Wrote lst_pred and shap_* columns to {WARDS_CSV}")

    shap.plots.beeswarm(sv, show=False)
    plt.title("What drives ward surface temperature (SHAP, °C)")
    plt.tight_layout()
    plt.savefig(PROCESSED / "shap_summary.png", dpi=150)
    print(f"Saved {PROCESSED / 'shap_summary.png'}")

    top = df[[f"shap_{f}" for f in FEATURES]].abs().idxmax(axis=1).value_counts()
    print("\nMain driver per ward:\n" + top.to_string())


if __name__ == "__main__":
    main()
