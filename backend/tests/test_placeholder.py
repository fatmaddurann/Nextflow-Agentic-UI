"""Placeholder — real tests live here as the project grows."""


def test_imports():
    """Verify core modules are importable."""
    from database.models import WorkflowStatus, PipelineType, SeverityLevel
    from api.models.schemas import WorkflowCreateRequest

    assert WorkflowStatus.PENDING == "pending"
    assert PipelineType.RNASEQ == "rnaseq"
    assert SeverityLevel.ERROR == "error"
    assert WorkflowCreateRequest.__name__ == "WorkflowCreateRequest"
