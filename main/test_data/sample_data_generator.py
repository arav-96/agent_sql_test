import csv
from pathlib import Path
from datetime import datetime, timedelta
import random

OUTPUT_FILE = Path("data_new.csv")
TARGET_ROWS = 5000

HEADER = [
    "providertaxid",
    "claimnumber",
    "firstdateofservice",
    "lastdateofservice",
    "dischargestatuscode",
    "admitdiagnosiscode",
    "primarydiagnosiscode",
    "primaryprocedurecode",
    "totalpaidamount",
    "lengthofstay",
    "loadmonth",
    "category",
    "selectionreason",
    "subprogramtype",
    "exl_nofinding",
    "exl_finding",
    "drgconditiontype",
    "mdcn",
    "mcc_count",
    "cc_count",
    "selection_month",
]

# Dimensions / categories similar to your schema
CATEGORIES = ["CAT_AUTO_SEL", "CAT_CVA_SEL", "CAT_GEN_EXL"]
DISCHARGE_STATUS = ["01", "02", "03", "04"]
SUBPROGRAMS = ["CVA", "DRG", "GEN"]
DRG_CONDITION = ["MCC", "CC", "OTHER"]
SELECTION_REASONS = ["High cost", "Readmission", "Outlier stay", "Random sample"]

LOADMONTHS = ["202506", "202507"]  # as requested


def random_date_in_month(yyyymm: str) -> datetime:
    year = int(yyyymm[:4])
    month = int(yyyymm[4:])
    start = datetime(year, month, 1)
    # pick a day between 1 and 28 to avoid month-end issues
    day_offset = random.randint(0, 27)
    return start + timedelta(days=day_offset)


def make_row(idx: int, loadmonth: str) -> dict:
    prov_id = f"PRV{random.randint(1000, 9999)}"
    claim_no = f"CLM{loadmonth}{idx:04d}"

    start_dt = random_date_in_month(loadmonth)
    los = random.randint(1, 10)
    end_dt = start_dt + timedelta(days=los - 1)

    category = random.choice(CATEGORIES)
    subprogram = random.choice(SUBPROGRAMS)
    drg_cond = random.choice(DRG_CONDITION)
    discharge = random.choice(DISCHARGE_STATUS)
    sel_reason = random.choice(SELECTION_REASONS)

    # diagnosis / procedure codes (fake but realistic-looking)
    admit_dx = f"I{random.randint(10, 69)}.{random.randint(0, 9)}"
    primary_dx = f"E{random.randint(10, 89)}.{random.randint(0, 9)}"
    primary_proc = f"0{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"

    # findings / audits logic
    exl_find = random.choice([0, 1])
    exl_no_find = 0 if exl_find == 1 else 1

    # severity counts consistent with drgconditiontype
    if drg_cond == "MCC":
        mcc = random.randint(1, 2)
        cc = random.randint(0, 1)
    elif drg_cond == "CC":
        mcc = 0
        cc = random.randint(1, 2)
    else:
        mcc = 0
        cc = 0

    # MDCN – just a small range of integers
    mdcn = random.randint(1, 25)

    # payment correlated with LOS and findings
    base = random.randint(1000, 20000)
    if exl_find:
        base += random.randint(500, 5000)
    total_paid = round(base * (1 + los * 0.05), 2)

    return {
        "providertaxid": prov_id,
        "claimnumber": claim_no,
        "firstdateofservice": start_dt.strftime("%Y-%m-%d"),
        "lastdateofservice": end_dt.strftime("%Y-%m-%d"),
        "dischargestatuscode": discharge,
        "admitdiagnosiscode": admit_dx,
        "primarydiagnosiscode": primary_dx,
        "primaryprocedurecode": primary_proc,
        "totalpaidamount": total_paid,
        "lengthofstay": los,
        "loadmonth": loadmonth,
        "category": category,
        "selectionreason": sel_reason,
        "subprogramtype": subprogram,
        "exl_nofinding": exl_no_find,
        "exl_finding": exl_find,
        "drgconditiontype": drg_cond,
        "mdcn": mdcn,
        "mcc_count": mcc,
        "cc_count": cc,
        "selection_month": loadmonth,
    }


def main():
    rows = []

    coverage_rows_per_month = len(CATEGORIES) * len(DRG_CONDITION) * len(SUBPROGRAMS)
    base_rows_total = TARGET_ROWS - (len(LOADMONTHS) * coverage_rows_per_month)
    if base_rows_total < 0:
        raise ValueError("TARGET_ROWS is too small for required coverage rows.")

    base_rows_per_month = base_rows_total // len(LOADMONTHS)
    extra_rows = base_rows_total % len(LOADMONTHS)

    idx = 1
    for month_index, loadmonth in enumerate(LOADMONTHS):
        month_rows = base_rows_per_month + (1 if month_index < extra_rows else 0)
        for _ in range(month_rows):
            rows.append(make_row(idx, loadmonth))
            idx += 1

    # ensure all combinations of category x drgconditiontype x subprogram exist at least once
    for loadmonth in LOADMONTHS:
        for cat in CATEGORIES:
            for drg in DRG_CONDITION:
                for sub in SUBPROGRAMS:
                    idx += 1
                    row = make_row(idx, loadmonth)
                    row["category"] = cat
                    row["drgconditiontype"] = drg
                    row["subprogramtype"] = sub
                    rows.append(row)

    # write CSV
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
