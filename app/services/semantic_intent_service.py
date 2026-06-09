from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from app.data.intent_examples import INTENT_EXAMPLES
from app.core.logger import logger


class ConfidenceThresholds:
    HIGH   = 0.75
    MEDIUM = 0.50
    LOW    = 0.35
    REJECT = 0.35


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

    def _get_tier(self, score: float) -> str:
        if score >= ConfidenceThresholds.HIGH:   return "HIGH"
        if score >= ConfidenceThresholds.MEDIUM: return "MEDIUM"
        if score >= ConfidenceThresholds.LOW:    return "LOW"
        return "REJECT"

    def detect_intent(self, query: str):
        _ = self.model  # trigger lazy load

        query_embedding = self._model.encode(query, convert_to_numpy=True).reshape(1, -1)
        best_intent, best_score = None, 0
        scores = {}

        for intent, embeddings in self._intent_embeddings.items():
            score = float(np.max(cosine_similarity(query_embedding, embeddings)))
            scores[intent] = round(score, 4)
            if score > best_score:
                best_score  = score
                best_intent = intent

        tier = self._get_tier(best_score)

        # Log top 3 competing intents
        top_3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        logger.info(f"Intent scores for '{query}': {top_3}")
        logger.info(f"Intent: {best_intent} | Score: {best_score:.4f} | Tier: {tier}")

        return {
            "intent":     best_intent,
            "confidence": best_score,
            "tier":       tier,
            "all_scores": scores,
        }


semantic_intent_service = SemanticIntentService()