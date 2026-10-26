"""Download US housing data from FRED (no API key needed) and load it into DuckDB.

Sources: US Census Bureau (new residential sales & construction) and Freddie Mac
(mortgage rates), both republished by the St. Louis Fed's FRED service.
"""

import io
import urllib.request

import duckdb
import pandas as pd

DB_PATH = "housing.duckdb"
START = "2000-01-01"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

REGIONS = {"": "US", "NE": "Northeast", "MW": "Midwest", "S": "South", "W": "West"}

#download and basic preprocessing (convert date to datetime, values to numeric, timestamp to date)
def fetch(series_id: str) -> pd.DataFrame:
    with urllib.request.urlopen(FRED_CSV.format(series_id), timeout=30) as resp:
        df = pd.read_csv(io.BytesIO(resp.read()))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED uses "." for missing
    df = df[df["date"] >= START].dropna()
    df["date"] = df["date"].dt.date  # store as DATE, not TIMESTAMP
    return df

#download and combine multiple datasets from diff regions
def regional(prefix: str) -> pd.DataFrame:
    frames = []
    for suffix, region in REGIONS.items(): 
        df = fetch(prefix + suffix) #download dataset for each region
        df["region"] = region
        frames.append(df)
    out = pd.concat(frames)
    return out.rename(columns={"date": "month", "value": "units_thousands_saar"})[
        ["month", "region", "units_thousands_saar"]
    ]


def main() -> None:
    print("Downloading from FRED...")
    #store the datasets in a dict
    tables = { 
        "new_home_sales": regional("HSN1F"),
        "housing_starts": regional("HOUST"),
        "new_home_median_price": fetch("MSPNHSUS").rename(
            columns={"date": "month", "value": "median_price_usd"}
        ),
        "new_home_months_supply": fetch("MSACSR").rename(
            columns={"date": "month", "value": "months_supply"}
        ),
        "mortgage_rates": fetch("MORTGAGE30US").rename(
            columns={"date": "week", "value": "rate_30yr_fixed_pct"}
        ),
    }

    con = duckdb.connect(DB_PATH) #connect to duckdb
    for name, df in tables.items(): #save each db as a table
        con.register("df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
        print(f"  {name}: {len(df):,} rows")
    con.close()
    print(f"Saved {DB_PATH}")


if __name__ == "__main__":
    main()
