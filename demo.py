from medguard.main import MedGuard
from medguard.healthcare_agent import HealthcareAIAgent  # your agent

# Create AI agent
agent = HealthcareAIAgent()

# Create MedGuard system
mg = MedGuard(
    agent=agent,
    user_id="patient-001",
    user_role="patient"
)

# Give consent
mg.grant_consent("healthcare_processing")

# Run task
result = mg.run_agent(
    "Patient John, Aadhaar 123456789012, has fever and cough",
    task_type="symptom_analysis"
)

print("\nFINAL SAFE OUTPUT:")
print(result)