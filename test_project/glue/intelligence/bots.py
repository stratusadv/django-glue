from dandy.llm import BaseLlmBot

from test_project.app.capability.intelligence import prompts
from test_project.app.capability.intelligence import intel


class CapabilityBot(BaseLlmBot):
    instructions_prompt = prompts.capability_instruction_prompt()
    intel_class = intel.CapabilityIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.CapabilityIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.capability_user_input_prompt(user_input)
        )
