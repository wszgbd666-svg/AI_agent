import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

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

def add_note(note_id: str, text: str):
    collection.add(
        documents=[text],
        ids=[note_id]
    )
    print(f"已添加笔记: {note_id}")

if __name__ == "__main__":
    note_id = input("笔记ID: ")
    text = input("笔记内容: ")
    add_note(note_id, text)