from dotenv import load_dotenv
load_dotenv()

from src.db.neo4j_client import Neo4jClient

db = Neo4jClient()
rows = db.run("MATCH ()-[r]->() RETURN count(r) AS relationships")
print(rows)
db.close()

count = rows[0]["relationships"] if rows else 0
if count < 30:
    raise SystemExit(f"Graph relationship count too low: {count}")
print("Graph relationship count ok:", count)
