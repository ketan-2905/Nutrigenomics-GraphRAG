import pandas as pd
from src.db.neo4j_client import Neo4jClient


def load_seed_data():
    db = Neo4jClient()

    snps = pd.read_csv("data/seed/seed_snps.csv")
    genes = pd.read_csv("data/seed/seed_genes.csv")
    traits = pd.read_csv("data/seed/seed_traits.csv")
    nutrients = pd.read_csv("data/seed/seed_nutrients.csv")
    foods = pd.read_csv("data/seed/seed_foods.csv")
    edges = pd.read_csv("data/seed/seed_edges.csv")

    for _, row in snps.iterrows():
        db.run("""
        MERGE (s:SNP {id:$snp_id})
        SET s.gene=$gene, s.variant=$variant, s.description=$description
        """, {"snp_id": row["snp_id"], "gene": row["gene"],
              "variant": row["variant"], "description": row["description"]})

    for _, row in genes.iterrows():
        db.run("""
        MERGE (g:Gene {id:$gene})
        SET g.full_name=$full_name, g.biological_role=$biological_role
        """, row.to_dict())

    for _, row in traits.iterrows():
        db.run("""
        MERGE (t:Trait {id:$trait_name})
        SET t.trait_id=$trait_id, t.category=$category
        """, row.to_dict())

    for _, row in nutrients.iterrows():
        db.run("""
        MERGE (n:Nutrient {id:$nutrient_name})
        SET n.nutrient_id=$nutrient_id, n.role=$role
        """, row.to_dict())

    for _, row in foods.iterrows():
        db.run("""
        MERGE (f:Food {id:$food_name})
        SET f.food_id=$food_id, f.nutrients=$nutrients
        """, row.to_dict())

    # Use generic RELATED relationship since APOC may not be available
    for _, row in edges.iterrows():
        db.run("""
        MATCH (a {id:$source})
        MATCH (b {id:$target})
        MERGE (a)-[r:RELATED {type:$relation}]->(b)
        SET r.evidence=$evidence
        """, row.to_dict())

    print("Seed data loaded successfully.")
    db.close()


if __name__ == "__main__":
    load_seed_data()
