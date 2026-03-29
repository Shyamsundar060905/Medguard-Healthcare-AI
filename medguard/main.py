import uuid
from typing import List, Dict, Any, Optional
import json

from loguru import logger
from swarms import Agent

from medguard.de_identifier import Deidentifier
from medguard.secure_communications import SecureCommunicationAES
from medguard.audit_logging import AccessControl
from medguard.consent import ConsentManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field

import time

class MedGuardInputLog(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    agent_id: str = Field(default="")
    agent_config: Dict[Any, Any] = Field(default={})
    user_id: str = Field(default="")
    user_role: str = Field(default="")
    task: str = Field(default="")
    data_sources: Optional[str] = Field(default=None)
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

class MedGuardInputLogs(BaseModel):
    output: str = Field(default="")
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    cleaned_task: str = Field(default="")
    encrypted_input: str = Field(default="")
    time: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

class MedGuardOutputLog(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    input_config: MedGuardInputLog
    outputs: List[MedGuardInputLogs] = Field(default=[])
    time_stamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class MedGuard:
    """
    A class to manage and ensure HIPAA compliance for large language model (LLM) agents.

    This class initializes with an optional agent or list of agents, and provides methods to run and wrap agents for HIPAA compliance.
    """

    def __init__(
        self,
        agent: Agent = None,
        agents: List[Agent] = None,
        user_id: str = None,
        user_role: str = "patient",
        data_sources: List[str] = None,  # PDFS, CSVs, any medical data sources available
        consent_manager: ConsentManager = None,
        *args,
        **kwargs,
    ):
        """
        Initialize MedGuard with an optional agent or list of agents.

        :param agent: A single Agent instance to be managed.
        :param agents: A list of Agent instances to be managed.
        :param user_id: The identifier of the user initiating requests.
        :param user_role: Role of the user (doctor, nurse, patient, admin).
        :param data_sources: List of data source descriptors.
        :param consent_manager: Optional consent manager.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        """
        self.agent = agent
        self.agents = agents
        self.user_id = user_id or "anonymous"
        self.user_role = user_role.lower() if user_role else "patient"
        self.data_sources = data_sources
        self.key = SecureCommunicationAES(roles=["admin", "doctor", "nurse", "patient"])
        self.deidentifer = Deidentifier()
        self.acl = AccessControl(allowed_roles=["admin", "doctor", "nurse", "patient"])
        self.consent_manager = consent_manager or ConsentManager()

        self.logs = MedGuardOutputLog(
            input_config=MedGuardInputLog(
                agent_id=getattr(agent, "id", "") if agent else "",
                agent_config=getattr(agent, "to_dict", lambda: {})() if agent else {},
                user_id=self.user_id,
                user_role=self.user_role,
                task="",
                data_sources=data_sources,
            ),
            outputs=[],
        )

    def run_agent(self, task: str, *args, purpose: str = "healthcare_processing", **kwargs):
        """
        Run the MedGuard instance with the initialized agent(s) ensuring HIPAA/DPDP compliance.
        """
        self.logs.input_config.task = task

        # Require role-based action & patient consent before processing
        if not self.acl.check_access(self.user_role, "recommend"):
            raise PermissionError(f"Role {self.user_role} is not permitted to run AI workflows.")

        self.consent_manager.require_consent(self.user_id, purpose)

        logger.info("Running MedGuard instance with compliance checks...")

        # De-identify sensitive information in the task before encryption
        deidentified_task = self.deidentifer.deidentify(task)
        logger.info(f"De-identified task: {deidentified_task}")

        # Encrypt the de-identified task for secure transmission
        encrypted_task = self.key.encrypt(deidentified_task, self.user_role)
        logger.info("Encrypted task")

        # Decrypt the task for processing by the agent
        decrypted_task = self.key.decrypt(encrypted_task, self.user_role)
        logger.info(f"Decrypted task: {decrypted_task}")

        # Run the task with the agent
        output = self.agent.run(decrypted_task, *args, **kwargs)
        logger.info(f"Agent output: {output}")

        # De-identify sensitive information in the output before returning
        deidentified_output = self.deidentifer.deidentify(output)
        logger.info(f"De-identified output: {deidentified_output}")

        # Update the logs for audit/trace
        self.logs.outputs.append(
            MedGuardInputLogs(
                output=output,
                cleaned_task=deidentified_task,
                encrypted_input=json.dumps(encrypted_task),
            )
        )

        return deidentified_output

    def grant_consent(self, purpose: str) -> None:
        """Grant consent for this user to perform a specific purpose."""
        self.consent_manager.grant_consent(self.user_id, purpose)
        logger.info(f"Consent granted for user {self.user_id} for purpose: {purpose}")

    def revoke_consent(self, purpose: str) -> None:
        """Revoke previously granted consent."""
        self.consent_manager.revoke_consent(self.user_id, purpose)
        logger.info(f"Consent revoked for user {self.user_id} for purpose: {purpose}")

    def wrap_agent(self, agent: Agent):
        """
        Wrap a given agent with MedGuard for HIPAA compliance.

        :param agent: The Agent instance to be wrapped for HIPAA compliance.
        """
        self.agent = agent
        logger.info(
            f"Agent wrapped with MedGuard for HIPAA compliance: {agent.agent_name}"
        )

    def run_agent_concurrently(
        self, tasks: List[str], *args, **kwargs
    ):
        """
        Run multiple tasks concurrently with the initialized agent(s) ensuring HIPAA compliance.

        :param tasks: A list of tasks to be processed concurrently.
        """

        results = []

        with ThreadPoolExecutor() as executor:
            future_to_task = {
                executor.submit(
                    self.run_agent, task, *args, **kwargs
                ): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(
                        f"Task {task} generated an exception: {e}"
                    )

        return results
