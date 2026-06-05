from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from app.data.intent_examples import INTENT_EXAMPLES


class SemanticIntentService:

    def __init__(self):
        self._model = None
        self._intent_embeddings = {}

    @property
    def model(self):
        if self._model is None:
            import sys
            print("Loading sentence transformer model...", flush=True)
            sys.stdout.flush()
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            self._prepare_embeddings()
            print("Model loaded ✓", flush=True)
        return self._model

    def _prepare_embeddings(self):
        for intent, examples in INTENT_EXAMPLES.items():
            self._intent_embeddings[intent] = self._model.encode(examples)

    def detect_intent(self, query: str):
        # triggers lazy load on first call
        _ = self.model

        query_embedding = self._model.encode([query])
        best_intent = None
        best_score  = 0

        for intent, embeddings in self._intent_embeddings.items():
            similarities = cosine_similarity(query_embedding, embeddings)
            score = float(np.max(similarities))
            if score > best_score:
                best_score  = score
                best_intent = intent

        return {
            "intent":     best_intent,
            "confidence": best_score,
        }


semantic_intent_service = SemanticIntentService()