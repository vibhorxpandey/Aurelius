"""Static methodology auditor — detect p-hacking / data-dredging signals without running code.

This is the safe half of Phase 2: it reads the generated analysis code (and the experiment
design text) and flags known questionable-research-practice patterns via heuristics — no
execution required, no dependencies. The Docker sandbox (``docker_runner``) is the optional,
opt-in half that actually runs the code.

The checks are deliberately conservative and explainable: each finding names the signal, a
severity, and the evidence line. False positives are expected — this surfaces things for a
human/LLM to judge, it does not certify anything on its own.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# (id, severity, human explanation, compiled regex). Severity weights the risk score.
_SIGNAL_WEIGHT = {"high": 30, "medium": 15, "low": 7}

# Correction methods whose presence *clears* the multiple-comparisons concern.
_CORRECTION_RE = re.compile(
    r"bonferroni|holm|benjamini|hochberg|\bfdr\b|multipletests|false[_ ]discovery|"
    r"sidak|tukey|family[- ]wise|p[._]adjust",
    re.IGNORECASE,
)

# Individual statistical-test call sites (used to count multiplicity).
_TEST_CALL_RE = re.compile(
    r"\b(ttest_ind|ttest_rel|ttest_1samp|f_oneway|pearsonr|spearmanr|chi2_contingency|"
    r"mannwhitneyu|wilcoxon|kruskal|ols|logit|corr\(|\.corr\b)",
    re.IGNORECASE,
)

_RULES = [
    (
        "hardcoded_significance_threshold",
        "medium",
        "Hard-coded p-value threshold (e.g. `p < 0.05`) — check it wasn't chosen after seeing results.",
        re.compile(r"p[_ ]*(?:value|val)?\s*[<>]=?\s*0?\.\d+", re.IGNORECASE),
    ),
    (
        "missing_random_seed",
        "medium",
        "Randomness used without a fixed seed — results won't reproduce.",
        None,  # handled specially below
    ),
    (
        "post_hoc_outlier_removal",
        "high",
        "Outlier/row dropping that may be post-hoc (data dredging).",
        re.compile(r"(drop|remove|filter|exclude)[^\n]{0,40}(outlier|> ?3 ?\*|std|z[_ ]?score)", re.IGNORECASE),
    ),
    (
        "optional_stopping",
        "high",
        "Signs of optional stopping — checking significance then collecting more data.",
        re.compile(r"(add|collect|more)\s+data|until\s+.*signif|peek|interim\s+look", re.IGNORECASE),
    ),
    (
        "harking",
        "medium",
        "Hypothesis appears derived from the data (HARKing) rather than pre-specified.",
        re.compile(r"(hypothesi[sz]e|predict).{0,40}(after|based on|from)\s+.*(data|result)", re.IGNORECASE),
    ),
    (
        "selective_reporting",
        "high",
        "Keeping/printing results only when significant (selective reporting).",
        re.compile(r"if\s+p[_ ]*\w*\s*<\s*0?\.\d+\s*:\s*(print|keep|append|report|save)", re.IGNORECASE),
    ),
    (
        "subgroup_dredging",
        "medium",
        "Looping over many variables/subgroups testing significance (data dredging).",
        re.compile(r"for\s+\w+\s+in\s+.*(columns|features|subgroups?|variables?)", re.IGNORECASE),
    ),
]

_RANDOM_USE_RE = re.compile(r"np\.random|numpy\.random|\brandom\.|train_test_split|\.sample\(|shuffle\(", re.IGNORECASE)
_SEED_RE = re.compile(r"random_state\s*=|np\.random\.seed|random\.seed|set_seed|manual_seed|seed\s*=", re.IGNORECASE)


def audit_methodology(code: str, design: str = "") -> Dict[str, Any]:
    """Scan analysis code (+ optional design text) for questionable-research-practice signals.

    Returns {"ok", "findings": [{signal, severity, detail, evidence}], "n_tests",
             "correction_present", "risk_score" (0-100), "risk" (low|medium|high), "summary"}.
    """
    text = code or ""
    findings: List[Dict[str, str]] = []

    for signal, severity, detail, pattern in _RULES:
        if signal == "missing_random_seed":
            if _RANDOM_USE_RE.search(text) and not _SEED_RE.search(text):
                findings.append({"signal": signal, "severity": severity, "detail": detail,
                                 "evidence": _first_match(_RANDOM_USE_RE, text)})
            continue
        m = pattern.search(text)
        if m:
            findings.append({"signal": signal, "severity": severity, "detail": detail,
                             "evidence": _line_of(text, m.start())})

    # Multiple-comparisons: many tests + no correction method anywhere.
    n_tests = len(_TEST_CALL_RE.findall(text))
    correction_present = bool(_CORRECTION_RE.search(text) or _CORRECTION_RE.search(design or ""))
    if n_tests >= 3 and not correction_present:
        findings.append({
            "signal": "multiple_comparisons_uncorrected",
            "severity": "high",
            "detail": f"{n_tests} statistical tests with no multiple-comparisons correction "
                      "(Bonferroni/FDR/etc.) — inflated false-positive risk.",
            "evidence": f"{n_tests} test call(s) detected",
        })

    score = min(100, sum(_SIGNAL_WEIGHT.get(f["severity"], 5) for f in findings))
    risk = "high" if score >= 45 else "medium" if score >= 20 else "low"
    summary = (
        f"{len(findings)} methodology signal(s); risk={risk} (score {score}). "
        + ("No correction for multiple tests. " if (n_tests >= 3 and not correction_present) else "")
    ).strip()

    return {
        "ok": True,
        "findings": findings,
        "n_tests": n_tests,
        "correction_present": correction_present,
        "risk_score": score,
        "risk": risk,
        "summary": summary,
    }


def _line_of(text: str, idx: int) -> str:
    start = text.rfind("\n", 0, idx) + 1
    end = text.find("\n", idx)
    return text[start : end if end != -1 else len(text)].strip()[:160]


def _first_match(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    return _line_of(text, m.start()) if m else ""
