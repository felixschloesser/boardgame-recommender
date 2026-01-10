import logging

from boardgames_api.domain.participants import service
from boardgames_api.domain.participants.records import StudyGroup


def test_assign_random_mode(monkeypatch):
    monkeypatch.delenv("PARTICIPANT_ASSIGNMENT_MODE", raising=False)
    result = service.assign_study_group()

    assert result in {StudyGroup.FEATURES, StudyGroup.REFERENCES}


def test_assign_force_references(monkeypatch):
    monkeypatch.setenv("PARTICIPANT_ASSIGNMENT_MODE", "FORCE_REFERENCES")

    assert service.assign_study_group() == StudyGroup.REFERENCES


def test_assign_force_features(monkeypatch):
    monkeypatch.setenv("PARTICIPANT_ASSIGNMENT_MODE", "force_features")

    assert service.assign_study_group() == StudyGroup.FEATURES


def test_invalid_mode_defaults_to_random(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, service.logger.name)
    monkeypatch.setenv("PARTICIPANT_ASSIGNMENT_MODE", "INVALID")
    monkeypatch.setattr(service.random, "choice", lambda seq: seq[0])

    result = service.assign_study_group()

    assert result == StudyGroup.FEATURES
    assert any("Invalid PARTICIPANT_ASSIGNMENT_MODE" in message for message in caplog.messages)
