import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from src.config import MASTER_CSV, ERROR_LOG, DEBUG_LOG, OUTPUT_DIR

REPORT_PATH = OUTPUT_DIR / "summary_report.csv"

# ---------------- LOAD DATA ---------------- #
df = pd.read_csv(MASTER_CSV)

print("\n========== DATA LOADED ==========")
print(df.head())

# ---------------- BASIC OVERVIEW ---------------- #
print("\n========== BASIC OVERVIEW ==========")
print("Total rows:", len(df))
print("Total columns:", len(df.columns))
print("Total unique URLs:", df["URL"].nunique())
print("Total categories:", df["Method"].nunique())
print("\nCategory distribution:")
print(df["Method"].value_counts())

# ---------------- HERO DATA SUMMARY ---------------- #
print("\n========== HERO DATA SUMMARY ==========")
hero_cols = [c for c in df.columns if c.startswith("hero_")]

for col in hero_cols:
    print(f"\nTop values in {col}:")
    print(df[col].value_counts().head())

# ---------------- QUICK GUIDE SUMMARY ---------------- #
print("\n========== QUICK GUIDE SUMMARY ==========")
quick_cols = [c for c in df.columns if c.startswith("quick_")]
print("Non-null counts in quick guide fields:")
print(df[quick_cols].notnull().sum().sort_values(ascending=False))

# ---------------- TEXT SIZE ANALYSIS ---------------- #
print("\n========== TEXT SIZE ANALYSIS ==========")
text_cols = df.select_dtypes(include="object").columns

df["total_text_length"] = df[text_cols].fillna("").apply(
    lambda row: sum(len(str(v)) for v in row), axis=1
)

print("Top 10 pages with most text:")
print(df[["URL", "total_text_length"]].sort_values(
    "total_text_length", ascending=False
).head(10))

plt.figure()
df["total_text_length"].plot(kind="hist", bins=20)
plt.title("Distribution of Page Text Length")
plt.xlabel("Total Text Characters")
plt.ylabel("Frequency")
plt.tight_layout()
plt.show()

# ---------------- MISSING DATA CHECK ---------------- #
print("\n========== MISSING DATA ==========")
missing = df.isna().sum().sort_values(ascending=False)
print(missing[missing > 0])

# ---------------- SUMMARY REPORT ---------------- #
summary = pd.DataFrame({
    "Total URLs": [df["URL"].nunique()],
    "Total Rows": [len(df)],
    "Total Categories": [df["Method"].nunique()],
    # "Average Scrape Time": [df["scrape_time_seconds"].mean()],
    # "Max Scrape Time": [df["scrape_time_seconds"].max()],
    "Average Text Length": [df["total_text_length"].mean()]
})

summary.to_csv(REPORT_PATH, index=False)

print("\n========== SUMMARY REPORT ==========")
print(summary)
print(f"\nSaved summary report to {REPORT_PATH}")
