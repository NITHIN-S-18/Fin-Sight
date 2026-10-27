from __future__ import annotations

import argparse
import csv
import random
from calendar import monthrange
from datetime import date
from pathlib import Path


PERSONAS = (
    ("student", 0.14, 18000, 0.35),
    ("salaried_professional", 0.42, 70000, 0.12),
    ("high_income_professional", 0.10, 180000, 0.08),
    ("self_employed", 0.12, 95000, 0.22),
    ("gig_worker", 0.10, 42000, 0.32),
    ("retired", 0.07, 48000, 0.10),
    ("financially_stressed", 0.05, 38000, 0.48),
)
COMMITMENTS = (
    ("Netflix", "Subscription", 649),
    ("Spotify", "Subscription", 119),
    ("Amazon Prime", "Subscription", 299),
    ("Cloud Services", "Subscription", 899),
    ("Gym Membership", "Subscription", 1200),
    ("Vehicle EMI", "EMI", 8500),
    ("Device EMI", "EMI", 4200),
    ("Personal Loan", "EMI", 11000),
    ("BNPL Provider", "BNPL", 2600),
)
VARIABLES = (
    ("Groceries", "Groceries"),
    ("Rent", "Rent"),
    ("Utilities", "Utilities"),
    ("Fuel", "Fuel"),
    ("Food Delivery", "Food"),
    ("Shopping", "Shopping"),
    ("Travel", "Travel"),
    ("Healthcare", "Healthcare"),
    ("Education", "Education"),
    ("Miscellaneous", "Miscellaneous"),
)
STATUSES = ("Success", "Failed", "Declined", "Rejected", "Pending")


def _month_start(start_year: int, start_month: int, offset: int) -> tuple[int, int]:
    absolute = start_year * 12 + start_month - 1 + offset
    return absolute // 12, absolute % 12 + 1


def _date_for(rng: random.Random, year: int, month: int, day: int) -> str:
    return date(year, month, min(day, monthrange(year, month)[1])).isoformat()


def _status(rng: random.Random, failure_rate: float) -> str:
    if rng.random() < failure_rate:
        return rng.choice(("Failed", "Declined", "Rejected"))
    if rng.random() < 0.015:
        return "Pending"
    return "Success"


def generate(output_dir: Path, user_count: int = 5000, months: int = 24, seed: int = 20261006) -> dict[str, int]:
    if user_count < 1 or months < 3:
        raise ValueError("user_count must be positive and months must be at least 3")
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    users: list[dict[str, object]] = []
    transactions: list[dict[str, object]] = []
    profiles: list[dict[str, object]] = []
    transaction_id = 1
    start_year, start_month = 2023, 1

    for user_number in range(1, user_count + 1):
        persona, weight, base_income, base_failure = rng.choices(PERSONAS, weights=[p[1] for p in PERSONAS], k=1)[0]
        user_id = f"V3{user_number:05d}"
        income_type = "salary" if "professional" in persona else persona
        capacity = round(base_income * rng.uniform(0.85, 1.15), 2)
        user_transactions: list[dict[str, object]] = []
        active_commitments: list[tuple[str, str, float]] = []
        for month_offset in range(months):
            year, month = _month_start(start_year, start_month, month_offset)
            trend = 1.0 + (month_offset / months) * rng.uniform(-0.08, 0.14)
            stress = max(0.0, base_failure + rng.uniform(-0.03, 0.08) + (month_offset / months) * rng.uniform(-0.02, 0.08))
            income = max(5000.0, capacity * trend * rng.uniform(0.88, 1.12))
            if persona in {"gig_worker", "self_employed"} and rng.random() < 0.25:
                income *= rng.uniform(0.45, 1.7)
            income_row = {
                "transaction_id": f"V3TX{transaction_id:09d}", "user_id": user_id,
                "transaction_date": _date_for(rng, year, month, rng.randint(1, 5)),
                "merchant_name": "Income", "description": f"{income_type} income",
                "amount": round(income, 2), "category": "Income", "transaction_class": "Income",
                "payment_mode": "Bank Transfer", "frequency": "Monthly", "income_flag": "Yes",
                "recurring_flag": "Yes", "autopay_flag": "No", "risk_label": "Low",
                "transaction_status": "Success", "is_new_subscription": "No", "merchant_type": income_type,
                "commitment_type": "",
            }
            transaction_id += 1
            transactions.append(income_row)
            user_transactions.append(income_row)

            if month_offset == 0:
                count = rng.randint(1, 4)
                active_commitments = rng.sample(list(COMMITMENTS), count)
            elif rng.random() < 0.04 and active_commitments:
                active_commitments.pop(rng.randrange(len(active_commitments)))
            elif rng.random() < 0.07 and len(active_commitments) < 5:
                active_commitments.append(rng.choice(COMMITMENTS))

            for merchant, transaction_class, amount in active_commitments:
                row = {
                    "transaction_id": f"V3TX{transaction_id:09d}", "user_id": user_id,
                    "transaction_date": _date_for(rng, year, month, rng.randint(6, 12)),
                    "merchant_name": merchant, "description": f"{merchant} recurring payment",
                    "amount": round(amount * rng.uniform(0.96, 1.04), 2), "category": transaction_class,
                    "transaction_class": transaction_class, "payment_mode": "NetBanking AutoPay" if rng.random() < 0.65 else "UPI",
                    "frequency": "Monthly", "income_flag": "No", "recurring_flag": "Yes",
                    "autopay_flag": "Yes" if rng.random() < 0.65 else "No", "risk_label": "Medium",
                    "transaction_status": _status(rng, stress), "is_new_subscription": "Yes" if month_offset == 0 and transaction_class == "Subscription" else "No",
                    "merchant_type": merchant, "commitment_type": transaction_class,
                }
                transaction_id += 1
                transactions.append(row)
                user_transactions.append(row)

            for _ in range(rng.randint(4, 8)):
                merchant, category = rng.choice(VARIABLES)
                amount = max(80.0, income * rng.uniform(0.004, 0.035))
                if rng.random() < 0.015:
                    amount *= -1
                row = {
                    "transaction_id": f"V3TX{transaction_id:09d}", "user_id": user_id,
                    "transaction_date": _date_for(rng, year, month, rng.randint(10, 28)),
                    "merchant_name": merchant, "description": f"{category} transaction",
                    "amount": round(amount, 2), "category": category, "transaction_class": "Expense",
                    "payment_mode": rng.choice(("UPI", "Card", "NetBanking")), "frequency": "Irregular",
                    "income_flag": "No", "recurring_flag": "No", "autopay_flag": "No",
                    "risk_label": "Low", "transaction_status": _status(rng, stress * 0.7),
                    "is_new_subscription": "No", "merchant_type": category, "commitment_type": "",
                }
                transaction_id += 1
                transactions.append(row)
                user_transactions.append(row)
        users.append({
            "user_id": user_id, "persona": persona, "income_type": income_type,
            "monthly_financial_capacity": round(capacity, 2),
            "age_group": rng.choice(("18-25", "26-35", "36-50", "51-65")),
            "city": rng.choice(("Bengaluru", "Chennai", "Mumbai", "Delhi", "Hyderabad", "Pune")),
        })
        successful = [row for row in user_transactions if row["transaction_status"] == "Success"]
        commitments = sum(float(row["amount"]) for row in successful if row["transaction_class"] in {"Subscription", "EMI", "BNPL"})
        profiles.append({
            "user_id": user_id, "persona": persona, "monthly_financial_capacity": round(capacity, 2),
            "monthly_commitments": round(commitments / months, 2), "exposure_score": round((commitments / months) / capacity * 100, 2),
            "active_subscriptions": sum(row["transaction_class"] == "Subscription" for row in successful),
            "active_emis": sum(row["transaction_class"] == "EMI" for row in successful),
            "active_bnpl": sum(row["transaction_class"] == "BNPL" for row in successful),
            "total_active_commitments": len(active_commitments), "total_transactions": len(user_transactions),
            "transaction_success_rate": round(len(successful) / len(user_transactions), 4),
            "financial_health": "Unknown", "is_leakage_user": "No", "leakage_subscription_count": 0,
            "is_heavy_bnpl_user": "No", "heavy_bnpl_providers": "", "is_heavy_emi_user": "No",
            "heavy_emi_providers": "", "special_scenario": "",
        })

    fields = list(users[0])
    with (output_dir / "users.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(users)
    fields = list(transactions[0])
    with (output_dir / "finsight_ml_dataset_v3.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(transactions)
    fields = list(profiles[0])
    with (output_dir / "user_financial_profile.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(profiles)
    return {"users": len(users), "transactions": len(transactions), "months": months, "seed": seed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a reproducible FinSight ML reference dataset.")
    parser.add_argument("--output-dir", type=Path, default=Path("backend/app/data/ml_dataset_v3"))
    parser.add_argument("--users", type=int, default=5000)
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20261006)
    args = parser.parse_args()
    print(generate(args.output_dir, args.users, args.months, args.seed))


if __name__ == "__main__":
    main()
