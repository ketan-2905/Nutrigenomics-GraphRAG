from src.db.neo4j_client import Neo4jClient


def apply_schema():
    db = Neo4jClient()
    constraints = [
        "CREATE CONSTRAINT snp_id IF NOT EXISTS FOR (s:SNP) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT gene_id IF NOT EXISTS FOR (g:Gene) REQUIRE g.id IS UNIQUE",
        "CREATE CONSTRAINT trait_id IF NOT EXISTS FOR (t:Trait) REQUIRE t.id IS UNIQUE",
        "CREATE CONSTRAINT nutrient_id IF NOT EXISTS FOR (n:Nutrient) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT food_id IF NOT EXISTS FOR (f:Food) REQUIRE f.id IS UNIQUE",
    ]
    for c in constraints:
        db.run(c)
    db.close()
    print("Schema constraints applied.")


if __name__ == "__main__":
    apply_schema()
