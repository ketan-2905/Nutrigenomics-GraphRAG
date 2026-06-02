import os
import chromadb
from sentence_transformers import SentenceTransformer
from src.config import EMBEDDING_MODEL
from src.db.neo4j_client import Neo4jClient


def build_vector_index():
    chroma_path = os.getenv("CHROMA_PATH", "./chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection("graph_evidence")

    model = SentenceTransformer(EMBEDDING_MODEL)

    db = Neo4jClient()
    rows = db.run("""
    MATCH (a)-[r:RELATED]->(b)
    RETURN labels(a)[0] AS source_type,
           a.id AS source,
           r.type AS relation,
           labels(b)[0] AS target_type,
           b.id AS target,
           coalesce(r.evidence, 'No evidence') AS evidence
    LIMIT 1000
    """)
    db.close()

    if not rows:
        print("No graph edges found. Load seed data first.")
        return

    documents = []
    ids = []
    metadatas = []

    for i, row in enumerate(rows):
        text = f"{row['source']} {row['relation']} {row['target']}. Evidence: {row['evidence']}."
        documents.append(text)
        ids.append(f"edge_{i}")
        metadatas.append({
            "source": str(row.get("source", "")),
            "relation": str(row.get("relation", "")),
            "target": str(row.get("target", "")),
            "evidence": str(row.get("evidence", "")),
        })

    embeddings = model.encode(documents).tolist()

    collection.add(
        documents=documents,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas
    )

    print(f"Indexed {len(documents)} graph evidence chunks.")


if __name__ == "__main__":
    build_vector_index()
