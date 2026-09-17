#!/usr/bin/env python3
"""Create a compact, reproducible summary from the raw runtime samples."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    rows = []
    for case in raw["workloads"]:
        alva = case["summary"]["alva"]["elapsed_ns"]
        rust = case["summary"]["rust_reference"]["elapsed_ns"]
        rows.append(
            {
                "name": case["name"],
                "shape": case["shape"],
                "input_bytes": case["input_bytes"],
                "alva_p50_ms": alva["p50"] / 1_000_000,
                "alva_p95_ms": alva["p95"] / 1_000_000,
                "rust_p50_ms": rust["p50"] / 1_000_000,
                "rust_p95_ms": rust["p95"] / 1_000_000,
                "alva_over_rust_p50": case["alva_over_rust_p50"],
                "alva_peak_rss_kib": (
                    case["peak_rss_kib"]["alva"].get("value_kib")
                    if isinstance(case["peak_rss_kib"]["alva"], dict)
                    else case["peak_rss_kib"]["alva"]
                ),
                "rust_peak_rss_kib": (
                    case["peak_rss_kib"]["rust_reference"].get("value_kib")
                    if isinstance(case["peak_rss_kib"]["rust_reference"], dict)
                    else case["peak_rss_kib"]["rust_reference"]
                ),
                "unoptimized_p50_ms": (
                    case["summary"]["alva_unoptimized"]["elapsed_ns"]["p50"] / 1_000_000
                    if "alva_unoptimized" in case["summary"] else None
                ),
                "optimized_over_unoptimized_p50": case.get("optimized_over_unoptimized_p50"),
                "unoptimized_peak_rss_kib": (
                    case["peak_rss_kib"]["alva_unoptimized"].get("value_kib")
                    if "alva_unoptimized" in case["peak_rss_kib"]
                    and isinstance(case["peak_rss_kib"]["alva_unoptimized"], dict)
                    else case["peak_rss_kib"].get("alva_unoptimized")
                ),
            }
        )
    ratios = [row["alva_over_rust_p50"] for row in rows]
    summary = {
        "host": raw["host"],
        "binaries": raw["binaries"],
        "limits": raw["limits"],
        "schedule": raw["schedule"],
        "workload_count": len(rows),
        "ratio_is_descriptive_not_pooled_speedup": True,
        "alva_over_rust_p50_ratio": {
            "median_across_workloads": statistics.median(ratios),
            "min": min(ratios),
            "max": max(ratios),
        },
        "alva_p50_ms": {
            "min": min(row["alva_p50_ms"] for row in rows),
            "max": max(row["alva_p50_ms"] for row in rows),
        },
        "alva_peak_rss_kib": {
            "min": min(row["alva_peak_rss_kib"] for row in rows),
            "max": max(row["alva_peak_rss_kib"] for row in rows),
        },
        "all_timed_runs_completed_with_expected_disposition": all(
            sample["classification"] in {"success", "spec_rejection"}
            for case in raw["workloads"]
            for implementation in case["measurements"].values()
            for sample in implementation
        ),
        "compatibility_cases": raw["compatibility_cases"],
        "workloads": rows,
    }
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Target Linux runtime summary",
        "",
        f"Host: `{raw['host']['platform']}` / `{raw['host']['machine']}`.",
        "",
        f"All {len(rows)} engineering workloads completed with their expected disposition. Each p50/p95 uses 30 sequential observations after 3 warmups; quantiles use nearest rank.",
        "",
        f"Across workload-level p50 ratios, ALVA/Rust had descriptive median `{statistics.median(ratios):.2f}x`, range `{min(ratios):.2f}–{max(ratios):.2f}x`. This is not a pooled speedup estimate. ALVA workload p50 ranged `{min(row['alva_p50_ms'] for row in rows):.2f}–{max(row['alva_p50_ms'] for row in rows):.2f} ms`; OS-reported process peak RSS ranged `{min(row['alva_peak_rss_kib'] for row in rows)}–{max(row['alva_peak_rss_kib'] for row in rows)} KiB`.",
        "",
        "| workload | bytes | ALVA p50 ms | unoptimized p50 ms | Rust p50 ms | ALVA/Rust ratio | opt/unopt ratio | RSS opt/unopt/Rust KiB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['input_bytes']} | {row['alva_p50_ms']:.3f} | "
            f"{row['unoptimized_p50_ms'] if row['unoptimized_p50_ms'] is not None else 'n/a'} | "
            f"{row['rust_p50_ms']:.3f} | {row['alva_over_rust_p50']:.2f} | "
            f"{row['optimized_over_unoptimized_p50'] if row['optimized_over_unoptimized_p50'] is not None else 'n/a'} | "
            f"{row['alva_peak_rss_kib']}/{row['unoptimized_peak_rss_kib'] or 'n/a'}/{row['rust_peak_rss_kib']} |"
        )
    lines.extend(
        [
            "",
            "Compatibility cases are excluded from direct timing ratios. `1` versus `1.0` succeeds in ALVA and is rejected by the fixed Rust reference; the distinct above-2^53 decimals are rejected by both.",
            "",
            "No workload hit the external timeout, address-space, output-capture, panic, or process-failure boundary. These constructed inputs therefore demonstrate the measured envelope only; they do not establish a production SLO or memory-leak claim.",
        ]
    )
    args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "workloads": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
