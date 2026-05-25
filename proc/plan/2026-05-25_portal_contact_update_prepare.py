#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook


BASE_DIR = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = BASE_DIR / "output/portal-contact-update-20260525"
ANALYSIS_PATH = OUT_DIR / "contact-update-analysis.json"
MIGRATION_SQL = Path(
    "/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/server/prisma/migrations/008_company_contact_fields.sql"
)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def sql_value(value: str) -> str:
    return "NULL" if value == "" else sql_literal(value)


def is_mobile(phone: str) -> bool:
    return clean(phone).startswith("010-") or clean(phone).startswith("010")


def target_tuple(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("targetOfficePhone")),
        clean(row.get("targetMobile1")),
        clean(row.get("targetMobile2")),
        clean(row.get("targetEmail1")),
        clean(row.get("targetEmail2")),
    )


def previous_info_block(row: dict[str, Any]) -> str:
    lines = [
        f"원본: 통계 row {row['excelRow']} / {row.get('fgName') or '-'}",
        f"업체명: {row.get('companyName') or ''}",
        f"상호: {row.get('companyBusinessName') or ''}",
        f"ERP ID: {row.get('companyErpId') or ''}",
        f"유선번호: {row.get('currentPhone') or ''}",
        f"팩스번호: {row.get('currentFax') or ''}",
        f"이메일1: {row.get('currentEmail') or ''}",
        "이메일2: ",
        f"웹사이트: {row.get('currentWebsite') or ''}",
        "모바일1: ",
        "모바일2: ",
    ]
    return "---- AX ----\n" + "\n".join(lines) + "\n------------"


def build_update(row: dict[str, Any]) -> dict[str, Any]:
    current_phone = clean(row.get("currentPhone"))
    current_email = clean(row.get("currentEmail")).lower()
    target_office = clean(row.get("targetOfficePhone"))
    target_mobile1 = clean(row.get("targetMobile1"))
    target_mobile2 = clean(row.get("targetMobile2"))
    target_email1 = clean(row.get("targetEmail1")).lower()
    target_email2 = clean(row.get("targetEmail2")).lower()

    set_values: dict[str, str | None] = {}

    if target_office:
        if target_office != current_phone:
            set_values["phone"] = target_office
    elif target_mobile1:
        if current_phone:
            set_values["phone"] = None
    elif current_phone and is_mobile(current_phone):
        set_values["phone"] = None
        if not target_mobile1:
            target_mobile1 = current_phone

    if target_email1 and target_email1 != current_email:
        set_values["email"] = target_email1
    if target_email2:
        set_values["email2"] = target_email2
    if target_mobile1:
        set_values["mobile1"] = target_mobile1
    if target_mobile2:
        set_values["mobile2"] = target_mobile2

    return {
        "companyUk": row["companyUk"],
        "companyId": row["companyId"],
        "companyName": row["companyName"],
        "excelRow": row["excelRow"],
        "fgName": row["fgName"],
        "taxName": row["taxName"],
        "setValues": set_values,
        "previousInfoBlock": previous_info_block(row) if set_values else "",
    }


def write_xlsx(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "rows"
    ws.append(columns)
    for row in rows:
        ws.append([row.get(col, "") for col in columns])
    for col in ws.columns:
        max_len = max(len(clean(cell.value)) for cell in col[:200])
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 10), 80)
    wb.save(path)


def main() -> None:
    rows = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    matched = [r for r in rows if r.get("companyUk")]

    holds: list[dict[str, Any]] = []
    ready_candidates: list[dict[str, Any]] = []

    grouped = defaultdict(list)
    for row in matched:
        grouped[row["companyUk"]].append(row)
    conflict_uks = set()
    duplicate_same_target_rows = set()
    for company_uk, group in grouped.items():
        non_test = [r for r in group if "발송테스트용" not in clean(r.get("issue2512"))]
        unique_targets = {target_tuple(r) for r in non_test}
        if len(unique_targets) > 1:
            conflict_uks.add(company_uk)
        elif len(non_test) > 1:
            for row in sorted(non_test, key=lambda r: int(r["excelRow"]))[1:]:
                duplicate_same_target_rows.add(row["excelRow"])

    for row in rows:
        hold_reason = ""
        if row["matchStatus"] in {"ambiguous", "unmatched"}:
            hold_reason = row["action"]
        elif "발송테스트용" in clean(row.get("issue2512")):
            hold_reason = "hold_test_row"
        elif row.get("companyUk") in conflict_uks:
            hold_reason = "hold_conflicting_duplicate_company"
        elif row.get("excelRow") in duplicate_same_target_rows:
            hold_reason = "hold_duplicate_same_target"

        if hold_reason:
            hold = dict(row)
            hold["holdReason"] = hold_reason
            holds.append(hold)
            continue

        update = build_update(row)
        if update["setValues"]:
            ready_candidates.append({**row, **update, "setValuesJson": json.dumps(update["setValues"], ensure_ascii=False)})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "contact-update-ready.json").write_text(
        json.dumps(ready_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "contact-update-holds.json").write_text(
        json.dumps(holds, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ready_cols = [
        "excelRow", "companyId", "companyUk", "companyName", "fgName", "taxName",
        "currentPhone", "currentEmail", "targetOfficePhone", "targetMobile1",
        "targetMobile2", "targetEmail1", "targetEmail2", "setValuesJson",
    ]
    hold_cols = [
        "excelRow", "holdReason", "fgName", "taxName", "altName1", "candidateSummary",
        "targetOfficePhone", "targetMobile1", "targetMobile2", "targetEmail1", "targetEmail2",
        "issue2512", "issue2601", "issue2601Feedback",
    ]
    for name, out_rows, cols in [
        ("contact-update-ready", ready_candidates, ready_cols),
        ("contact-update-holds", holds, hold_cols),
    ]:
        with (OUT_DIR / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(out_rows)
        write_xlsx(OUT_DIR / f"{name}.xlsx", out_rows, cols)

    statements = [
        "-- Generated by proc/plan/2026-05-25_portal_contact_update_prepare.py",
        f"-- Generated at {datetime.now().isoformat(timespec='seconds')}",
        f"-- Ready updates: {len(ready_candidates)}",
        f"-- Held rows: {len(holds)}",
        "BEGIN;",
        MIGRATION_SQL.read_text(encoding="utf-8").strip(),
    ]
    for row in ready_candidates:
        set_parts = []
        for field, value in row["setValues"].items():
            set_parts.append(f'"{field}" = {sql_value(value) if value is not None else "NULL"}')
        block = row["previousInfoBlock"]
        marker = f"통계 row {row['excelRow']}"
        set_parts.append(
            '"contactMemo" = CASE '
            f'WHEN "contactMemo" IS NOT NULL AND position({sql_literal(marker)} in "contactMemo") > 0 THEN "contactMemo" '
            f'WHEN COALESCE("contactMemo", \'\') = \'\' THEN {sql_literal(block)} '
            f'ELSE "contactMemo" || E\'\\n\\n\' || {sql_literal(block)} END'
        )
        set_parts.append('"updatedAt" = NOW()')
        statements.append(
            "UPDATE \"Company\"\n"
            "SET " + ",\n    ".join(set_parts) + "\n"
            f"WHERE uk = {sql_literal(row['companyUk'])} AND \"deletedAt\" IS NULL;"
        )
    statements.append("COMMIT;")
    (OUT_DIR / "contact-update-prod.sql").write_text("\n\n".join(statements) + "\n", encoding="utf-8")

    summary = Counter()
    for row in ready_candidates:
        for field in row["setValues"].keys():
            summary[field] += 1
    hold_summary = Counter(row["holdReason"] for row in holds)
    lines = [
        "# Portal contact update apply plan",
        "",
        f"- Ready update rows: {len(ready_candidates)}",
        f"- Hold rows: {len(holds)}",
        "",
        "## Field update counts",
        "",
    ]
    for key, count in summary.most_common():
        lines.append(f"- {key}: {count}")
    lines += ["", "## Hold counts", ""]
    for key, count in hold_summary.most_common():
        lines.append(f"- {key}: {count}")
    lines += [
        "",
        "## Files",
        "",
        "- `contact-update-ready.xlsx`: rows that can be applied",
        "- `contact-update-holds.xlsx`: rows excluded from DB update",
        "- `contact-update-prod.sql`: transaction SQL for prod",
    ]
    (OUT_DIR / "apply-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((OUT_DIR / "apply-plan.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
