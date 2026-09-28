"""Readable reports, immutable research runs, and explicit review comparisons."""

from __future__ import annotations

import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import tempfile

from stocks_infer.research import FORMULA_VERSION, FRAMEWORK_VERSION
from stocks_infer.research.engine import research_watchlist
from stocks_infer.research.io import fingerprint, load_bundle, write_json
from stocks_infer.research.models import CompanyResearch, ResearchBundle
from stocks_infer.storage import ParquetSnapshotStore


def _cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _display(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "ratio":
        return f"{value:.1%}"
    if unit == "multiple":
        return f"{value:.2f}x"
    return f"{value:,.2f} {unit}"


def _selected_period_facts(facts, period_type: str):
    grouped = {}
    for fact in facts:
        if fact.period_type != period_type:
            continue
        grouped.setdefault((fact.metric, fact.period_start, fact.period_end), []).append(fact)
    selected = []
    for candidates in grouped.values():
        available = max(fact.available_at for fact in candidates)
        selected.extend(fact for fact in candidates if fact.available_at == available)
    return sorted(selected, key=lambda fact: (fact.period_end, fact.metric, fact.fact_id))


def render_report(result: CompanyResearch, bundle: ResearchBundle, as_of: date) -> str:
    lines = [f"# {result.ticker} — {result.name}", "", f"Evaluation cutoff: {as_of} (end of day). Framework: `{FRAMEWORK_VERSION}`.", "", f"**Framework status:** {result.framework_status}", ""]
    lines.extend(f"- {reason}" for reason in result.framework_reasons)
    lines += ["", "**Research lists:** " + ", ".join(result.lists), "", "## Assessments", ""]
    for assessment in result.assessments:
        lines += [f"### {assessment.dimension.title()}: {assessment.status}", ""]
        lines.extend(f"- {observation}" for observation in assessment.observations)
        lines.append("")
    lines += ["## Questions and limitations", ""]
    lines.extend(f"- {warning}" for warning in result.warnings)
    annual_features = [feature for feature in result.features if feature.period_basis == "annual"]
    ttm_features = [feature for feature in result.features if feature.period_basis == "ttm"]
    lines += ["", "## Annual financial evidence", "", "Annual observations, separate from TTM and peer-relative analysis.", "", "| Period | Feature | Value | Evidence status | Input fact IDs |", "|---|---|---:|---|---|"]
    for f in annual_features:
        cells = (f.period_end, f.name, _display(f.value, f.unit), f.status, ", ".join(f.input_ids))
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines += ["", "### Formulas and unavailable features", ""]
    latest = max((f.period_end for f in annual_features), default=None)
    lines.extend(f"- **{f.name}:** {f.explanation}" for f in annual_features if f.period_end == latest)
    lines += ["", "## Trailing-twelve-month evidence", "", "Each period requires four contiguous normalized quarters. A flow may use annual plus current YTD minus prior comparable YTD when its discrete quarters are incomplete. TTM evidence is informational in this release and does not replace annual assessments.", "", "| Period ending | Feature | Value | Evidence status | Input fact IDs |", "|---|---|---:|---|---|"]
    if ttm_features:
        for f in ttm_features:
            cells = (f.period_end, f.name, _display(f.value, f.unit), f.status, ", ".join(f.input_ids))
            lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
        latest_ttm = max(f.period_end for f in ttm_features)
        lines += ["", "### TTM formulas and unavailable features", ""]
        lines.extend(f"- **{f.name}:** {f.explanation}" for f in ttm_features if f.period_end == latest_ttm)
    else:
        lines.append("| — | — | — | missing | No complete four-quarter window |")
    lines += ["", "## Business thesis", ""]
    if result.thesis:
        t = result.thesis
        lines += [f"Version: {t.version}; authored {t.authored_at}.", "", t.business_description, "", t.opportunity, "", f"Research decision: {t.decision}. Next review: {t.next_review or 'not set'}.", ""]
        for claim in t.claims:
            lines += [f"### {claim.claim_id}: {claim.text}", "", f"Type: {'researcher assumption' if claim.assumption else 'sourced claim'}. Sources: {', '.join(claim.source_ids) or 'none'}.", "", f"Counterargument: {claim.counterargument}", "", f"Watch **{claim.metric}**: {claim.expected_outcome}. Review by {claim.review_on}.", "", f"Invalidation condition: {claim.invalidated_by}", ""]
    else:
        lines += ["No thesis available at this cutoff. Record claims, counterarguments, milestones, and invalidation conditions.", ""]
    lines += ["## Valuation scenarios", ""]
    if result.market:
        lines += [f"Price: {result.market.close:,.2f} {result.currency} on {result.market.price_date}; outstanding shares: {result.market.shares_outstanding:,.0f} dated {result.market.share_count_date}. Source: {result.market.source_id}.", ""]
    if result.valuation:
        lines += ["Values depend on researcher assumptions; no scenario probabilities are assigned.", "", "| Scenario | Value/share | Relative to price | Terminal share of enterprise value |", "|---|---:|---:|---:|"]
        for v in result.valuation:
            lines.append(f"| {v['name']} | {v['per_share']:.2f} {result.currency} | {v['upside']:+.1%} | {_display(v['terminal_share_of_enterprise_value'], 'ratio')} |")
        for v in result.valuation:
            a = v["assumptions"]
            lines += ["", f"### {v['name'].title()} assumptions", "", a["rationale"], "", f"Thesis: {a['thesis_version']}; claims: {', '.join(a['claim_ids'])}; authored {a['authored_at']}.", "", f"Growth by year: {', '.join(f'{g:.1%}' for g in a['revenue_growth'])}.", f"Operating margins by year: {', '.join(f'{m:.1%}' for m in a['operating_margins'])}.", f"Tax: {a['tax_rate']:.1%}; sales/capital: {a['sales_to_capital']:.2f}; discount rate: {a['discount_rate']:.1%}; terminal growth: {a['terminal_growth']:.1%}; terminal ROIC: {a['terminal_roic']:.1%}.", "", "Discount-rate sensitivity: " + "; ".join(f"{s['discount_rate']:.1%} → {s['per_share']:.2f} {result.currency}/share" for s in v["sensitivity"]), ""]
            lines.extend(f"- {warning}" for warning in v["warnings"])
    else:
        lines.append("No valid scenario available. See valuation assessment and framework routing.")
    facts = [f for f in bundle.facts if f.security_id == result.security_id and f.available_at <= as_of]
    source_ids = {f.source_id for f in facts}
    if result.market:
        source_ids.add(result.market.source_id)
    if result.thesis:
        source_ids.update(s for c in result.thesis.claims for s in c.source_ids)
    lines += ["", "## Source documents", ""]
    for source in sorted(bundle.sources, key=lambda s: s.source_id):
        if source.source_id in source_ids:
            lines.append(f"- **{source.source_id}**: {source.title}; published {source.published_at}; retrieved {source.retrieved_at}; accession {source.accession or 'not supplied'}. {source.url}")
    quarter_facts = _selected_period_facts(facts, "quarter")
    quarter_ends = sorted({fact.period_end for fact in quarter_facts})[-12:]
    lines += ["", "### Normalized discrete-quarter facts", "", "Reported quarters are retained directly; derived quarters identify their cumulative input fact IDs in the source concept.", "", "| Quarter | Metric | Value | Available | Fact / source concept |", "|---|---|---:|---|---|"]
    for f in quarter_facts:
        if f.period_end not in quarter_ends:
            continue
        cells = (f"{f.period_start} to {f.period_end}", f.metric, _display(f.value, f.unit), f.available_at, f"{f.fact_id} / {f.source_concept}")
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    ytd_facts = _selected_period_facts(facts, "ytd")
    latest_ytd_ends = sorted({fact.period_end for fact in ytd_facts})[-6:]
    lines += ["", "### Reported year-to-date facts", "", "| YTD interval | Metric | Value | Available | Fact ID |", "|---|---|---:|---|---|"]
    for f in ytd_facts:
        if f.period_end not in latest_ytd_ends:
            continue
        cells = (f"{f.period_start} to {f.period_end}", f.metric, _display(f.value, f.unit), f.available_at, f.fact_id)
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines += ["", "### Reported facts", "", "| Fact ID | Metric | Value | Period | Available | Source / concept |", "|---|---|---:|---|---|---|"]
    for f in sorted(facts, key=lambda f: (f.period_end, f.metric, f.available_at, f.fact_id)):
        cells = (f.fact_id, f.metric, _display(f.value, f.unit), f"{f.period_start or 'instant'} to {f.period_end}", f.available_at, f"{f.source_id} / {f.source_concept}")
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"


def _code_fingerprint() -> str:
    root = Path(__file__).resolve().parents[1]
    return fingerprint({str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.rglob("*.py"))})


def write_research_run(input_path: Path, output_root: Path, as_of: date, run_id: str | None = None) -> Path:
    bundle = load_bundle(input_path)
    results = research_watchlist(bundle, as_of)
    input_hash, code_hash = fingerprint(bundle), _code_fingerprint()
    run_id = run_id or f"{as_of}-{input_hash[:10]}-{code_hash[:8]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
        raise ValueError("run ID must contain only letters, digits, periods, underscores, and hyphens")
    parent = output_root / "research_runs"
    destination = parent / run_id
    if destination.exists():
        raise FileExistsError(f"research run already exists: {destination}")
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".research-", dir=parent) as temporary:
        staging = Path(temporary)
        write_json(staging / "input.json", bundle)
        write_json(staging / "research.json", results)
        features = [(r.security_id, f.period_basis, f.name, f.period_end, f.value, f.unit, f.status, json.dumps(f.input_ids), f.explanation) for r in results for f in r.features]
        ParquetSnapshotStore()._write_rows(staging / "features.parquet", (
            ("security_id", "VARCHAR"), ("period_basis", "VARCHAR"), ("feature", "VARCHAR"), ("period_end", "DATE"),
            ("value", "DOUBLE"), ("unit", "VARCHAR"), ("status", "VARCHAR"),
            ("input_ids_json", "VARCHAR"), ("explanation", "VARCHAR"),
        ), features)
        facts = [(f.fact_id, f.security_id, f.metric, f.value, f.unit, f.period_start, f.period_end, f.period_type, f.available_at, f.source_id, f.source_concept) for f in bundle.facts]
        ParquetSnapshotStore()._write_rows(staging / "facts.parquet", (
            ("fact_id", "VARCHAR"), ("security_id", "VARCHAR"), ("metric", "VARCHAR"),
            ("value", "DOUBLE"), ("unit", "VARCHAR"), ("period_start", "DATE"),
            ("period_end", "DATE"), ("period_type", "VARCHAR"), ("available_at", "DATE"),
            ("source_id", "VARCHAR"), ("source_concept", "VARCHAR"),
        ), facts)
        links = []
        for result in results:
            filename = f"company-{hashlib.sha256(result.security_id.encode()).hexdigest()[:16]}.md"
            (staging / filename).write_text(render_report(result, bundle, as_of), encoding="utf-8")
            links.append(f"- [{result.ticker} — {result.name}]({filename}): {', '.join(result.lists)}")
        (staging / "README.md").write_text(f"# Research review — {as_of}\n\nAnnual plus quarterly/TTM recorded-data workflow. TTM evidence is a separate trend layer; research queues may overlap and rows are sorted by ticker, not investment merit.\n\n" + "\n".join(links) + "\n", encoding="utf-8")
        with (staging / "comparison.csv").open("w", newline="", encoding="utf-8") as output:
            columns = ("security_id", "ticker", "framework_status", "quality", "growth", "resilience", "valuation", "evidence", "base_case_upside", "lists", "warnings")
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for r in results:
                base = next((v for v in r.valuation if v["name"] == "base"), None)
                writer.writerow({"security_id": r.security_id, "ticker": r.ticker, "framework_status": r.framework_status, **{a.dimension: a.status for a in r.assessments}, "base_case_upside": base["upside"] if base else "", "lists": " | ".join(r.lists), "warnings": " | ".join(r.warnings)})
        write_json(staging / "manifest.json", {
            "schema_version": 1, "run_id": run_id, "as_of_date": as_of,
            "framework_version": FRAMEWORK_VERSION, "formula_version": FORMULA_VERSION,
            "valuation_version": "fcff/0.1.0", "code_fingerprint": code_hash,
            "input_fingerprint": input_hash, "input_snapshot": "input.json",
            "evaluated_count": len(results), "ordering": "ticker then security_id; no overall rank",
            "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(staging.iterdir())},
        })
        # Exclusive reservation prevents overwrite, including concurrent runs.
        # A filesystem failure leaves visible, verifiably incomplete artifacts.
        destination.mkdir()
        for path in staging.iterdir():
            path.replace(destination / path.name)
    return destination


def read_verified_run(path: Path):
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if not {"input.json", "research.json"} <= manifest.get("artifacts", {}).keys():
        raise ValueError("research manifest is missing required artifact hashes")
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name:
            raise ValueError("invalid artifact path")
        artifact = path / name
        if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
            raise ValueError(f"artifact missing or changed: {name}")
    return manifest, json.loads((path / "research.json").read_text(encoding="utf-8"))


def compare_runs(before: Path, after: Path) -> dict:
    old_manifest, old = read_verified_run(before)
    new_manifest, new = read_verified_run(after)
    old_by_id, new_by_id = {r["security_id"]: r for r in old}, {r["security_id"]: r for r in new}
    changes = []
    for sid in sorted(old_by_id.keys() | new_by_id.keys()):
        first, second = old_by_id.get(sid), new_by_id.get(sid)
        if first is None or second is None:
            changes.append({"security_id": sid, "changes": ["added_to_watchlist" if first is None else "removed_from_watchlist"]})
            continue
        categories = [label for field, label in (("features", "financial_evidence"), ("market", "market_data"), ("thesis", "thesis"), ("valuation", "valuation_results_or_assumptions"), ("lists", "research_lists"), ("framework_status", "framework_assignment"), ("warnings", "warnings")) if first[field] != second[field]]
        if categories:
            changes.append({"security_id": sid, "ticker": second["ticker"], "changes": categories})
    return {
        "before": old_manifest["run_id"], "after": new_manifest["run_id"],
        "methodology_changed": any(old_manifest.get(k) != new_manifest.get(k) for k in ("framework_version", "formula_version", "valuation_version", "code_fingerprint")),
        "note": "Changed input/result categories, not a causal attribution of investment performance.",
        "companies": changes,
    }
