import chromadb
from src.config import CHROMA_PATH


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_or_create_collection(client, name="graph_evidence"):
    return client.get_or_create_collection(name)
