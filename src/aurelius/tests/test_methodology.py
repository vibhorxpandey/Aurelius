"""Static methodology auditor — pure, no deps, no execution."""
from __future__ import annotations

from aurelius.sandbox.methodology import audit_methodology


def test_clean_code_is_low_risk():
    code = (
        "import numpy as np\n"
        "np.random.seed(0)\n"
        "from scipy.stats import ttest_ind\n"
        "t, p = ttest_ind(a, b)\n"
        "print(t, p)\n"
    )
    r = audit_methodology(code)
    assert r["risk"] == "low"
    assert r["n_tests"] >= 1


def test_missing_seed_flagged():
    code = "from sklearn.model_selection import train_test_split\nX_tr, X_te = train_test_split(X)\n"
    r = audit_methodology(code)
    assert any(f["signal"] == "missing_random_seed" for f in r["findings"])


def test_seed_present_not_flagged():
    code = "train_test_split(X, y, random_state=42)\n"
    r = audit_methodology(code)
    assert not any(f["signal"] == "missing_random_seed" for f in r["findings"])


def test_multiple_comparisons_without_correction():
    code = "\n".join(f"t{i}, p{i} = ttest_ind(g{i}, h{i})" for i in range(5))
    r = audit_methodology(code)
    assert any(f["signal"] == "multiple_comparisons_uncorrected" for f in r["findings"])
    assert r["risk"] in ("medium", "high")


def test_correction_clears_multiplicity():
    code = "\n".join(f"t{i}, p{i} = ttest_ind(g{i}, h{i})" for i in range(5))
    code += "\nfrom statsmodels.stats.multitest import multipletests\nmultipletests(pvals, method='fdr_bh')\n"
    r = audit_methodology(code)
    assert r["correction_present"] is True
    assert not any(f["signal"] == "multiple_comparisons_uncorrected" for f in r["findings"])


def test_selective_reporting_and_outlier_removal_high_risk():
    code = (
        "df = df[df.value < 3*df.value.std()]  # drop outliers after seeing results\n"
        "if p_val < 0.05:\n    report(result)\n"
    )
    r = audit_methodology(code)
    signals = {f["signal"] for f in r["findings"]}
    assert "post_hoc_outlier_removal" in signals
    assert "selective_reporting" in signals
    assert r["risk"] == "high"
