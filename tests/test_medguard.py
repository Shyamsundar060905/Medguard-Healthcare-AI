import pytest

from medguard.de_identifier import Deidentifier
from medguard.consent import ConsentManager, ConsentError
from medguard.audit_logging import AccessControl
from medguard.healthcare_agent import HealthcareAIAgent
from medguard.main import MedGuard


def test_deidentify_aadhaar_and_pan():
    deid = Deidentifier()
    text = "Patient Aadhaar: 1234 5678 9012, PAN: ABCDE1234F"
    result = deid.deidentify(text)
    assert "AADHAAR_NUMBER" in result or "PAN_NUMBER" in result


def test_consent_requirements_for_medguard():
    consent = ConsentManager()
    user_id = "patient-007"
    purpose = "healthcare_processing"

    with pytest.raises(ConsentError):
        consent.require_consent(user_id, purpose)

    consent.grant_consent(user_id, purpose)
    assert consent.has_consent(user_id, purpose)

    consent.revoke_consent(user_id, purpose)
    assert not consent.has_consent(user_id, purpose)


def test_access_control_policy():
    acl = AccessControl(allowed_roles=["admin", "doctor", "nurse", "patient"])
    assert acl.check_access("doctor", "recommend")
    assert not acl.check_access("patient", "recommend")


@pytest.mark.parametrize("user_role,should_pass", [
    ("admin", True),
    ("doctor", True),
    ("nurse", False),
    ("patient", False),
])
def test_medguard_workflow_with_healthcare_agent(user_role, should_pass):
    user_id = "patient-123"
    agent = HealthcareAIAgent()
    mg = MedGuard(agent=agent, user_id=user_id, user_role=user_role)

    # Grant consent first
    mg.grant_consent("healthcare_processing")
    
    if should_pass:
        result = mg.run_agent("Patient has fever and cough", task_type="symptom_analysis")
        assert "DPDP" in result and "safe" in result
    else:
        with pytest.raises(PermissionError):
            mg.run_agent("Patient has fever and cough", task_type="symptom_analysis")
