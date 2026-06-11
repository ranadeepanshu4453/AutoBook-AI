from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from app.data.intent_examples import INTENT_EXAMPLES
from app.core.logger import logger
import os

class ConfidenceThresholds:
    HIGH   = 0.75
    MEDIUM = 0.50
    LOW    = 0.35
    REJECT = 0.20


class SemanticIntentService:

    def __init__(self):
        self._model = None
        self._intent_embeddings = {}

    @property
    def model(self):
        if self._model is None:
            model_path = os.getenv("MODEL_PATH", "AI_models/all-MiniLM-L6-v2")
            logger.info(f"Loading sentence transformer from: {model_path}")
            self._model = SentenceTransformer(model_path)
            logger.info("Model loaded successfully")
            self._prepare_embeddings()
        return self._model

    def _prepare_embeddings(self):
        for intent, examples in INTENT_EXAMPLES.items():
            self._intent_embeddings[intent] = self._model.encode(examples)
    
    def reload_embeddings(self, additional_examples: dict[str, list[str]] | None = None) -> None:
        """
        Hot-reload embeddings — merges base INTENT_EXAMPLES with any
        additional learned examples passed in.
        Called by retraining scheduler after a successful retrain cycle.
        No server restart needed.
        """
        _ = self.model  # ensure model is loaded

        merged: dict[str, list[str]] = {}
        for intent, examples in INTENT_EXAMPLES.items():
            merged[intent] = list(examples)

        if additional_examples:
            for intent, examples in additional_examples.items():
                if intent not in merged:
                    merged[intent] = []
                for ex in examples:
                    if ex not in merged[intent]:
                        merged[intent].append(ex)

        new_embeddings = {}
        for intent, examples in merged.items():
            new_embeddings[intent] = self._model.encode(examples)

        # Atomic swap — thread-safe enough for single-process FastAPI
        self._intent_embeddings = new_embeddings
        logger.info(
            f"Embeddings reloaded — {len(new_embeddings)} intents, "
            f"{sum(len(v) for v in new_embeddings.values())} total examples"
        )

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