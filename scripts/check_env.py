from dotenv import load_dotenv
import os

load_dotenv()

required = [
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "REDIS_URL",
    "ENABLE_REDIS_CACHE",
    "ENABLE_SEMANTIC_CACHE",
    "CHROMA_PATH",
    "EMBEDDING_MODEL",
]

recommended_real = [
    "OPENAI_API_KEY",
    "FDC_API_KEY",
    "NCBI_EMAIL",
    "NCBI_API_KEY",
]

print("Required variables:")
missing = []
for k in required:
    ok = bool(os.getenv(k))
    print(f"- {k}: {'yes' if ok else 'NO'}")
    if not ok:
        missing.append(k)

print("\nReal-data / LLM variables:")
for k in recommended_real:
    ok = bool(os.getenv(k))
    print(f"- {k}: {'yes' if ok else 'NO'}")

if missing:
    raise SystemExit(f"Missing required env vars: {missing}")

print("\nAll required env vars present.")
