"""Rule-based candidate ↔ role match scoring.

Score is 0–100 with the following weighting:
  - Skills overlap        50 pts   (Jaccard on tokenized skills, with bonus for full coverage)
  - Experience alignment  20 pts   (overlap of experience buckets)
  - Location fit          15 pts   (substring or "remote" match)
  - Salary fit            15 pts   (candidate expectation within the company's budget range)

Each component degrades gracefully when input data is missing — missing data on
either side returns a neutral (0.5 × weight) score for that component so we don't
penalise candidates for fields the company didn't fill.
"""
import re
from typing import Iterable

_EXP_BUCKETS = [
    (0, 1), (1, 3), (3, 5), (5, 8), (8, 12), (12, 60),
]


def _tokens(text: str) -> set:
    if not text:
        return set()
    parts = re.split(r"[,/;|]| and ", text.lower())
    out = set()
    for p in parts:
        p = re.sub(r"[^a-z0-9+#.\- ]", " ", p).strip()
        if not p:
            continue
        # add full phrase and individual tokens longer than 2 chars
        out.add(p)
        for w in p.split():
            if len(w) > 2:
                out.add(w)
    return out


def _exp_to_range(value: str):
    """Parse '3–5 years' / '5+ years' / '8 years' → (low, high)."""
    if not value:
        return None
    s = value.lower().replace("–", "-").replace("—", "-")
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if not nums:
        return None
    if "+" in s:
        return (nums[0], 60)
    if len(nums) == 1:
        n = nums[0]
        # snap to nearest bucket
        for lo, hi in _EXP_BUCKETS:
            if lo <= n <= hi:
                return (lo, hi)
        return (n, n)
    return (min(nums), max(nums))


def _overlap_ratio(a, b) -> float:
    if not a or not b:
        return 0.0
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    if hi <= lo:
        return 0.0
    span_a = max(1, a[1] - a[0])
    return min(1.0, (hi - lo) / span_a)


def _parse_salary(value: str):
    """Parse '₹28L' / '20-30L' / '2500000' → (low_in_inr, high_in_inr)."""
    if not value:
        return None
    s = value.lower().replace(",", "").replace("₹", "").replace("inr", "").replace("rs", "")
    s = s.replace("–", "-").replace("—", "-").replace("to", "-")
    has_l = "l" in s  # lakhs
    has_cr = "cr" in s
    nums = re.findall(r"\d+\.?\d*", s)
    if not nums:
        return None
    vals = [float(x) for x in nums]
    if has_cr:
        vals = [v * 1e7 for v in vals]
    elif has_l:
        vals = [v * 1e5 for v in vals]
    elif max(vals) < 200:  # assume lakhs if small number
        vals = [v * 1e5 for v in vals]
    if len(vals) == 1:
        return (vals[0] * 0.85, vals[0] * 1.15)
    return (min(vals), max(vals))


def score_candidate(candidate, company) -> dict:
    """Return {'score': int, 'breakdown': {...}, 'reasons': [str]}."""
    reasons = []

    # ---- Skills (50 pts) ----
    cand_skills = _tokens(candidate.skills or "") | _tokens(candidate.preferred_role or "")
    req_skills = _tokens(company.skills_required or "") | _tokens(company.required_role or "")
    if not req_skills:
        skill_score = 25  # neutral when company didn't list
        skill_pct = 0.5
        reasons.append("No required skills listed — neutral match")
    elif not cand_skills:
        skill_score = 0
        skill_pct = 0.0
        reasons.append("Candidate has no skills listed")
    else:
        matched = cand_skills & req_skills
        # weight by required-side coverage (how many of the company's needs the candidate covers)
        skill_pct = len(matched) / max(1, len(req_skills))
        skill_score = round(min(1.0, skill_pct * 1.1) * 50)
        if matched:
            sample = sorted(list(matched))[:5]
            reasons.append(f"Matches {len(matched)}/{len(req_skills)} required skills ({', '.join(sample)})")
        else:
            reasons.append("No skill overlap")

    # ---- Experience (20 pts) ----
    cand_exp = _exp_to_range(candidate.experience or "")
    req_exp = _exp_to_range(company.experience_required or "")
    if not req_exp:
        exp_score = 10
        exp_pct = 0.5
    elif not cand_exp:
        exp_score = 6
        exp_pct = 0.3
        reasons.append("Candidate experience not specified")
    else:
        exp_pct = _overlap_ratio(cand_exp, req_exp)
        exp_score = round(exp_pct * 20)
        if exp_pct >= 0.8:
            reasons.append(f"Experience aligned ({candidate.experience} ↔ {company.experience_required})")
        elif exp_pct == 0:
            reasons.append(f"Experience gap ({candidate.experience} vs required {company.experience_required})")

    # ---- Location (15 pts) ----
    cand_loc = (candidate.location or "").lower()
    # company doesn't have a location field; use additional_notes / hiring_timeline fallback skip
    # Treat 'remote' as a wildcard match
    if not cand_loc:
        loc_score = 7
        loc_pct = 0.5
    elif "remote" in cand_loc:
        loc_score = 15
        loc_pct = 1.0
        reasons.append("Open to remote")
    else:
        # company location proxy: scan additional_notes for city names in candidate location
        notes = (company.additional_notes or "").lower()
        city = cand_loc.split(",")[0].strip()
        if city and city in notes:
            loc_score = 15
            loc_pct = 1.0
            reasons.append(f"Location match · {city.title()}")
        else:
            loc_score = 8
            loc_pct = 0.5  # neutral — company didn't specify

    # ---- Salary (15 pts) ----
    cand_sal = _parse_salary(candidate.salary_expectation or "")
    req_sal = _parse_salary(company.budget or "")
    if not req_sal:
        sal_score = 7
        sal_pct = 0.5
    elif not cand_sal:
        sal_score = 7
        sal_pct = 0.5
    else:
        overlap = _overlap_ratio(cand_sal, req_sal)
        if overlap >= 0.5:
            sal_score = 15
            sal_pct = 1.0
            reasons.append("Salary expectation within budget")
        elif overlap > 0:
            sal_score = 9
            sal_pct = 0.6
            reasons.append("Salary expectation partially within budget")
        else:
            # check direction
            if cand_sal[0] > req_sal[1]:
                reasons.append("Salary expectation above budget")
                sal_score = 3
                sal_pct = 0.2
            else:
                reasons.append("Salary expectation below budget")
                sal_score = 12
                sal_pct = 0.8

    total = skill_score + exp_score + loc_score + sal_score
    total = max(0, min(100, total))

    return {
        "score": total,
        "breakdown": {
            "skills": skill_score,
            "experience": exp_score,
            "location": loc_score,
            "salary": sal_score,
        },
        "percentages": {
            "skills": round(skill_pct * 100),
            "experience": round(exp_pct * 100),
            "location": round(loc_pct * 100),
            "salary": round(sal_pct * 100),
        },
        "reasons": reasons,
    }


def rank_candidates(candidates: Iterable, company, limit: int = 20):
    out = []
    for c in candidates:
        s = score_candidate(c, company)
        s["candidate_id"] = c.id
        s["candidate"] = {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "preferred_role": c.preferred_role,
            "experience": c.experience,
            "location": c.location,
            "salary_expectation": c.salary_expectation,
            "skills": c.skills,
            "status": c.status,
            "is_shortlisted": c.is_shortlisted,
        }
        out.append(s)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]
