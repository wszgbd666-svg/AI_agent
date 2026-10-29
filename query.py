import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="shibing624/text2vec-base-chinese"
)

client = chromadb.PersistentClient(
    path="./chroma_db",
    settings=Settings(anonymized_telemetry=False)
)
collection = client.get_or_create_collection(
    name="my_notes",
    embedding_function=embedding_fn
)

def retrieve(query: str, n_results: int = 3):
    results = collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []

def ask_deepseek(query: str, context: list):
    context_text = "\n".join(context)
    prompt = f"根据以下笔记内容回答问题:\n\n{context_text}\n\n问题: {query}"

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }
    resp = requests.post(API_URL, headers=headers, json=payload)
    return resp.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    q = input("你的问题: ")
    context = retrieve(q)
    answer = ask_deepseek(q, context)
    print("\n回答:", answer)