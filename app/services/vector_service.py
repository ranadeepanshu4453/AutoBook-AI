# app/services/vector_service.py
import chromadb
from chromadb.utils import embedding_functions

class VectorService:
    def __init__(self):
        # Local persistence without Docker
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="diary_history", 
            embedding_function=self.embedding_fn
        )

    def query_similar_comments(self, text: str, n_results: int = 5):
        return self.collection.query(
            query_texts=[text],
            n_results=n_results
        )

vector_service = VectorService()
