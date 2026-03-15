"""Placeholder — real tests live here as the project grows."""


def test_imports():
    """Verify core modules are importable."""
    from api.models.schemas import WorkflowCreateRequest
    from database.models import PipelineType, SeverityLevel, WorkflowStatus

    assert WorkflowStatus.PENDING == "pending"
    assert PipelineType.RNASEQ == "rnaseq"
    assert SeverityLevel.ERROR == "error"
    assert WorkflowCreateRequest.__name__ == "WorkflowCreateRequest"
