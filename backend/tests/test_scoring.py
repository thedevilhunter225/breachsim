from __future__ import annotations

from app.models.enums import EventType
from app.services.scoring import WEIGHTS


def test_scoring_weights_are_explainable():
    assert WEIGHTS[EventType.CLICKED_LINK] == 20
    assert WEIGHTS[EventType.SUBMITTED_FORM_BOOLEAN] == 40
    assert WEIGHTS[EventType.CLICKED_REPORT] == -25
