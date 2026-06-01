import os
import requests
import pandas as pd
from datetime import datetime, timezone
from src.config import FDC_API_KEY
from src.db.neo4j_client import Neo4jClient
from src.observability.metrics import RAG_DATASET_ROWS_LOADED_TOTAL

FDC_FOODS_ENV = os.getenv(
    "FDC_FOODS",
    "spinach,lentils,eggs,salmon,almonds,coffee,oats,beans,broccoli,avocado",
)
TARGET_FOODS = [f.strip() for f in FDC_FOODS_ENV.split(",")]
OUTPUT_FILE = "data/processed/food_nutrients.csv"
FDC_BASE = "https://api.nal.usda.gov/fdc/v1"
SOURCE_NAME = "USDA FoodData Central"
SOURCE_URL = "https://fdc.nal.usda.gov"


def fetch_food_nutrients(food_name: str) -> list[dict]:
    if not FDC_API_KEY:
        return []
    resp = requests.get(
        f"{FDC_BASE}/foods/search",
        params={"query": food_name, "api_key": FDC_API_KEY, "pageSize": 3,
                "dataType": "Foundation,SR Legacy"},
        timeout=15,
    )
    resp.raise_for_status()
    foods = resp.json().get("foods", [])
    if not foods:
        return []

    food = foods[0]
    fdc_id = food.get("fdcId", "")
    retrieved_at = datetime.now(timezone.utc).isoformat()

    return [
        {
            "fdc_id": fdc_id,
            "food_name": food_name,
            "nutrient_name": n.get("nutrientName", ""),
            "amount": n.get("value", ""),
            "unit": n.get("unitName", ""),
            "source_name": SOURCE_NAME,
            "source_url": f"{SOURCE_URL}/food-details/{fdc_id}/nutrients",
            "retrieved_at": retrieved_at,
        }
        for n in food.get("foodNutrients", [])[:15]
        if n.get("nutrientName")
    ]


def fetch_all() -> pd.DataFrame:
    if not FDC_API_KEY:
        print("FDC_API_KEY not set. Skipping USDA fetch. Using seed food data only.")
        return pd.DataFrame()

    rows = []
    for food in TARGET_FOODS:
        print(f"  Fetching nutrients for {food}...")
        rows.extend(fetch_food_nutrients(food))

    df = pd.DataFrame(rows)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} food-nutrient rows -> {OUTPUT_FILE}")
    return df


def load_fooddata_to_graph():
    if not os.path.exists(OUTPUT_FILE):
        df = fetch_all()
        if df.empty:
            return
    else:
        df = pd.read_csv(OUTPUT_FILE)

    db = Neo4jClient()
    count = 0

    for _, row in df.iterrows():
        food = str(row.get("food_name", "")).strip().capitalize()
        nutrient = str(row.get("nutrient_name", "")).strip()
        amount = row.get("amount", "")
        unit = str(row.get("unit", "")).strip()
        fdc_id = str(row.get("fdc_id", "")).strip()
        source_url = str(row.get("source_url", SOURCE_URL)).strip()
        retrieved_at = str(row.get("retrieved_at", "")).strip()

        if not food or not nutrient or nutrient == "nan":
            continue

        db.run("MERGE (f:Food {id:$food})", {"food": food})
        db.run("MERGE (n:Nutrient {id:$nutrient})", {"nutrient": nutrient})
        db.run("""
        MATCH (f:Food {id:$food}) MATCH (n:Nutrient {id:$nutrient})
        MERGE (f)-[r:RELATED {type:'CONTAINS'}]->(n)
        SET r.amount=$amount, r.unit=$unit, r.fdc_id=$fdc_id,
            r.source_name=$source_name, r.source_url=$source_url,
            r.retrieved_at=$retrieved_at, r.evidence_level='USDA'
        """, {"food": food, "nutrient": nutrient, "amount": str(amount),
              "unit": unit, "fdc_id": fdc_id, "source_name": SOURCE_NAME,
              "source_url": source_url, "retrieved_at": retrieved_at})
        count += 1

    db.close()
    RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="usda_fooddata").inc(count)
    print(f"Loaded {count} food-nutrient rows into graph.")


if __name__ == "__main__":
    fetch_all()
    load_fooddata_to_graph()
