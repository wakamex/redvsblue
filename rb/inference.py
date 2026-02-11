from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class _Obs:
    value: float
    party: str
    term_start: date | None
    term_id: str


def _parse_float(s: str) -> float | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _parse_date(s: str) -> date | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return date.fromisoformat(txt[:10])
    except ValueError:
        return None


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.6f}"


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _two_sided_normal_p(z: float | None) -> float | None:
    if z is None:
        return None
    return 2.0 * (1.0 - _normal_cdf(abs(z)))


def _sign(v: float | None) -> int:
    if v is None:
        return 0
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _sample_std(xs: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mu = sum(xs) / float(n)
    var = sum((x - mu) ** 2 for x in xs) / float(n - 1)
    if var < 0.0:
        if var > -1e-12:
            var = 0.0
        else:
            return None
    return math.sqrt(var)


def _rough_mde_abs_two_sample(
    *,
    d_vals: list[float],
    r_vals: list[float],
    alpha_two_sided: float = 0.05,
    power: float = 0.80,
) -> float | None:
    # Normal-approximation MDE for two-sample mean-difference:
    # (z_{1-alpha/2} + z_{power}) * s_pooled * sqrt(1/n_d + 1/n_r)
    # We use fixed z-values for common settings to keep dependencies minimal.
    nd = len(d_vals)
    nr = len(r_vals)
    if nd < 2 or nr < 2:
        return None
    sd = _sample_std(d_vals)
    sr = _sample_std(r_vals)
    if sd is None or sr is None:
        return None
    pooled_var_num = float((nd - 1)) * (sd**2) + float((nr - 1)) * (sr**2)
    pooled_var_den = float((nd - 1) + (nr - 1))
    if pooled_var_den <= 0.0:
        return None
    pooled_sd = math.sqrt(max(0.0, pooled_var_num / pooled_var_den))
    if pooled_sd <= 0.0:
        return 0.0

    # Defaults used in output labels/notes.
    z_alpha = 1.959963984540054 if abs(alpha_two_sided - 0.05) <= 1e-12 else 1.959963984540054
    z_power = 0.8416212335729143 if abs(power - 0.80) <= 1e-12 else 0.8416212335729143
    return (z_alpha + z_power) * pooled_sd * math.sqrt((1.0 / float(nd)) + (1.0 / float(nr)))


def _mat2_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ],
        [
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ],
    ]


def _mat2_inv(a: list[list[float]]) -> list[list[float]] | None:
    det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    if abs(det) <= 1e-12:
        return None
    inv_det = 1.0 / det
    return [
        [a[1][1] * inv_det, -a[0][1] * inv_det],
        [-a[1][0] * inv_det, a[0][0] * inv_det],
    ]


def _ols_nw(
    *,
    y: list[float],
    d: list[int],
    nw_lags: int,
) -> tuple[float | None, float | None, float | None, float | None]:
    # y_t = alpha + beta*D_t + eps_t, where D_t = 1 for Democrat, 0 for Republican.
    n = len(y)
    if n < 3 or n != len(d):
        return None, None, None, None
    s_d = float(sum(d))
    if s_d <= 0.0 or s_d >= float(n):
        return None, None, None, None
    s_y = float(sum(y))
    s_dy = float(sum(float(di) * yi for di, yi in zip(d, y)))

    xtx = [
        [float(n), s_d],
        [s_d, s_d],
    ]
    xtx_inv = _mat2_inv(xtx)
    if xtx_inv is None:
        return None, None, None, None

    # beta = (X'X)^-1 X'y
    alpha = xtx_inv[0][0] * s_y + xtx_inv[0][1] * s_dy
    beta = xtx_inv[1][0] * s_y + xtx_inv[1][1] * s_dy

    u = [yi - (alpha + beta * float(di)) for yi, di in zip(y, d)]
    x_rows = [[1.0, float(di)] for di in d]

    s = [[0.0, 0.0], [0.0, 0.0]]
    for t in range(n):
        ut2 = u[t] * u[t]
        xt = x_rows[t]
        s[0][0] += ut2 * xt[0] * xt[0]
        s[0][1] += ut2 * xt[0] * xt[1]
        s[1][0] += ut2 * xt[1] * xt[0]
        s[1][1] += ut2 * xt[1] * xt[1]

    lag_max = max(0, min(int(nw_lags), n - 1))
    for lag in range(1, lag_max + 1):
        w = 1.0 - (lag / float(lag_max + 1))
        for t in range(lag, n):
            ut = u[t]
            ul = u[t - lag]
            xt = x_rows[t]
            xl = x_rows[t - lag]
            scale = w * ut * ul
            # Add Gamma_l + Gamma_l'
            s[0][0] += scale * (xt[0] * xl[0] + xl[0] * xt[0])
            s[0][1] += scale * (xt[0] * xl[1] + xl[0] * xt[1])
            s[1][0] += scale * (xt[1] * xl[0] + xl[1] * xt[0])
            s[1][1] += scale * (xt[1] * xl[1] + xl[1] * xt[1])

    v = _mat2_mul(_mat2_mul(xtx_inv, s), xtx_inv)
    var_beta = v[1][1]
    if var_beta < 0:
        # Numeric noise on tiny negatives can occur.
        if var_beta > -1e-12:
            var_beta = 0.0
        else:
            return beta, None, None, None
    se_beta = math.sqrt(var_beta)
    if se_beta <= 0.0:
        return beta, se_beta, None, None
    z = beta / se_beta
    p_two = _two_sided_normal_p(z)
    return beta, se_beta, z, p_two


def _load_term_groups(term_metrics_csv: Path) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    with term_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            metric_id = (row.get("metric_id") or "").strip()
            if not metric_id:
                continue
            if (row.get("metric_primary") or "").strip() != "1":
                continue
            party = (row.get("party_abbrev") or "").strip()
            if party not in {"D", "R"}:
                continue
            value = _parse_float(row.get("value") or "")
            if value is None:
                continue

            g = groups.get(metric_id)
            if g is None:
                g = {
                    "metric_id": metric_id,
                    "metric_label": (row.get("metric_label") or metric_id).strip(),
                    "metric_family": (row.get("metric_family") or "").strip(),
                    "agg_kind": (row.get("agg_kind") or "").strip(),
                    "units": (row.get("units") or "").strip(),
                    "obs": [],
                }
                groups[metric_id] = g
            g["obs"].append(
                _Obs(
                    value=value,
                    party=party,
                    term_start=_parse_date(row.get("term_start") or ""),
                    term_id=(row.get("term_id") or "").strip(),
                )
            )
    return groups


def _load_permutation_rows(path: Path | None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if path is None or not path.exists():
        return out
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            mid = (row.get("metric_id") or "").strip()
            if not mid:
                continue
            out[mid] = row
    return out


def _bool_to_flag(v: bool | None) -> str:
    if v is None:
        return ""
    return "1" if v else "0"


def _q_flag(q: float | None, threshold: float) -> bool | None:
    if q is None:
        return None
    return q < threshold


def _p_flag(p: float | None, threshold: float) -> bool | None:
    if p is None:
        return None
    return p < threshold


def write_inference_table(
    *,
    term_metrics_csv: Path,
    permutation_party_term_csv: Path | None,
    out_csv: Path,
    out_md: Path | None,
    nw_lags: int,
) -> None:
    groups = _load_term_groups(term_metrics_csv)
    perm_rows = _load_permutation_rows(permutation_party_term_csv)

    header = [
        "metric_id",
        "metric_label",
        "metric_family",
        "agg_kind",
        "units",
        "n_obs",
        "n_d",
        "n_r",
        "n_clusters_total",
        "n_clusters_d",
        "n_clusters_r",
        "effect_d_minus_r",
        "rough_mde_abs_alpha005_power080",
        "rough_effect_over_mde_abs",
        "hac_nw_lags",
        "hac_nw_se",
        "hac_nw_z",
        "hac_nw_p_two_sided_norm",
        "hac_nw_p_lt_005",
        "hac_nw_p_lt_010",
        "perm_effect_d_minus_r",
        "perm_p_two_sided",
        "perm_q_bh_fdr",
        "perm_tier",
        "perm_q_lt_005",
        "perm_q_lt_010",
        "sig_disagree_005",
        "sig_disagree_010",
        "direction_disagree",
    ]
    rows: list[dict[str, str]] = []

    for metric_id in sorted(groups.keys()):
        g = groups[metric_id]
        obs: list[_Obs] = sorted(
            g["obs"],
            key=lambda x: (
                x.term_start or date.min,
                x.term_id,
            ),
        )
        y = [o.value for o in obs]
        d = [1 if o.party == "D" else 0 for o in obs]
        n_obs = len(obs)
        n_d = sum(1 for x in d if x == 1)
        n_r = n_obs - n_d
        d_vals = [o.value for o in obs if o.party == "D"]
        r_vals = [o.value for o in obs if o.party == "R"]
        d_term_ids = {o.term_id for o in obs if o.party == "D"}
        r_term_ids = {o.term_id for o in obs if o.party == "R"}
        mde_abs = _rough_mde_abs_two_sample(d_vals=d_vals, r_vals=r_vals)
        beta, se, z, p_hac = _ols_nw(y=y, d=d, nw_lags=max(0, int(nw_lags)))
        effect_over_mde = None
        if beta is not None and mde_abs is not None and mde_abs > 0.0:
            effect_over_mde = abs(beta) / mde_abs

        pr = perm_rows.get(metric_id, {})
        p_perm = _parse_float(pr.get("p_two_sided") or "")
        q_perm = _parse_float(pr.get("q_bh_fdr") or "")
        perm_eff = _parse_float(pr.get("observed_diff_d_minus_r") or "")
        perm_tier = (pr.get("evidence_tier") or "").strip()

        perm_005 = _q_flag(q_perm, 0.05)
        perm_010 = _q_flag(q_perm, 0.10)
        hac_005 = _p_flag(p_hac, 0.05)
        hac_010 = _p_flag(p_hac, 0.10)
        disagree_005 = None if perm_005 is None or hac_005 is None else (perm_005 != hac_005)
        disagree_010 = None if perm_010 is None or hac_010 is None else (perm_010 != hac_010)
        dir_disagree = None if _sign(beta) == 0 or _sign(perm_eff) == 0 else (_sign(beta) != _sign(perm_eff))

        rows.append(
            {
                "metric_id": metric_id,
                "metric_label": g["metric_label"],
                "metric_family": g["metric_family"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "n_obs": str(n_obs),
                "n_d": str(n_d),
                "n_r": str(n_r),
                "n_clusters_total": str(len({o.term_id for o in obs if o.term_id})),
                "n_clusters_d": str(len({tid for tid in d_term_ids if tid})),
                "n_clusters_r": str(len({tid for tid in r_term_ids if tid})),
                "effect_d_minus_r": _fmt(beta),
                "rough_mde_abs_alpha005_power080": _fmt(mde_abs),
                "rough_effect_over_mde_abs": _fmt(effect_over_mde),
                "hac_nw_lags": str(max(0, int(nw_lags))),
                "hac_nw_se": _fmt(se),
                "hac_nw_z": _fmt(z),
                "hac_nw_p_two_sided_norm": _fmt(p_hac),
                "hac_nw_p_lt_005": _bool_to_flag(hac_005),
                "hac_nw_p_lt_010": _bool_to_flag(hac_010),
                "perm_effect_d_minus_r": _fmt(perm_eff),
                "perm_p_two_sided": _fmt(p_perm),
                "perm_q_bh_fdr": _fmt(q_perm),
                "perm_tier": perm_tier,
                "perm_q_lt_005": _bool_to_flag(perm_005),
                "perm_q_lt_010": _bool_to_flag(perm_010),
                "sig_disagree_005": _bool_to_flag(disagree_005),
                "sig_disagree_010": _bool_to_flag(disagree_010),
                "direction_disagree": _bool_to_flag(dir_disagree),
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)

    if out_md is None:
        return

    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Inference Table (Primary Metrics)")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}")
    lines.append("")
    lines.append(f"- Term metrics: `{term_metrics_csv}`")
    if permutation_party_term_csv is not None:
        lines.append(f"- Permutation table: `{permutation_party_term_csv}`")
    lines.append(f"- HAC/Newey-West lags: `{max(0, int(nw_lags))}`")
    lines.append("- HAC p-values use a normal approximation for two-sided p-values.")
    lines.append("- Rough MDE uses a two-sample normal approximation (alpha=0.05, power=0.80) and is a scale diagnostic, not a hard decision rule.")
    lines.append("")

    lines.append("| Metric | Family | Effect (D-R) | Rough MDE | |Effect|/MDE | HAC p | Perm q | Perm tier | Disagree@0.05 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---:|")
    for r in sorted(
        rows,
        key=lambda rr: (
            _parse_float(rr.get("perm_q_bh_fdr") or "") if _parse_float(rr.get("perm_q_bh_fdr") or "") is not None else 1e9,
            _parse_float(rr.get("hac_nw_p_two_sided_norm") or "") if _parse_float(rr.get("hac_nw_p_two_sided_norm") or "") is not None else 1e9,
            rr.get("metric_id") or "",
        ),
    ):
        lines.append(
            "| "
            + " | ".join(
                [
                    (r.get("metric_id") or "").replace("|", "\\|"),
                    (r.get("metric_family") or "").replace("|", "\\|"),
                    _fmt(_parse_float(r.get("effect_d_minus_r") or "")),
                    _fmt(_parse_float(r.get("rough_mde_abs_alpha005_power080") or "")),
                    _fmt(_parse_float(r.get("rough_effect_over_mde_abs") or "")),
                    _fmt(_parse_float(r.get("hac_nw_p_two_sided_norm") or "")),
                    _fmt(_parse_float(r.get("perm_q_bh_fdr") or "")),
                    (r.get("perm_tier") or "").replace("|", "\\|"),
                    (r.get("sig_disagree_005") or ""),
                ]
            )
            + " |"
        )

    text = "\n".join(lines) + "\n"
    tmp_md = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp_md.write_text(text, encoding="utf-8")
    tmp_md.replace(out_md)
