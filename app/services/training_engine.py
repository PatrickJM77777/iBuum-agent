"""
Training Engine V1 orchestration layer.
"""

from app.core.config import get_settings
from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import TrainingRecommendationResponse
from app.services import training_rules


class TrainingEngine:
    """Stateless orchestration service for deterministic training decisions."""

    def evaluate(
        self, request: TrainingRecommendationRequest
    ) -> TrainingRecommendationResponse:
        return training_rules.run_pipeline(request, get_settings().agent_version)


_ENGINE = TrainingEngine()


def evaluate(request: TrainingRecommendationRequest) -> TrainingRecommendationResponse:
    """Module-level entrypoint for route integration."""
    return _ENGINE.evaluate(request)
