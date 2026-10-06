from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.routes.public import TrainingEventRequest


@pytest.mark.parametrize(
    "metadata",
    [
        {"password": "do-not-store-this"},
        {"mfa_code": "123456"},
        {"email": "person@example.test"},
        {"simulation_choice": "do-not-store-this"},
        {"simulation_choice": {"password": "do-not-store-this"}},
    ],
)
def test_public_training_events_reject_private_or_arbitrary_metadata(metadata):
    with pytest.raises(ValidationError):
        TrainingEventRequest.model_validate(
            {"event_type": "submitted_form_boolean", "metadata": metadata}
        )


def test_public_training_events_keep_only_a_categorical_choice():
    event = TrainingEventRequest.model_validate(
        {
            "event_type": "submitted_form_boolean",
            "metadata": {
                "source": "landing_render",
                "channel": "email",
                "simulation_choice": "would_provide_details",
            },
        }
    )
    assert event.metadata == {"simulation_choice": "would_provide_details"}
