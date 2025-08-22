from dandy.llm import BaseLlmBot

from test_project.app.gorilla.intelligence import prompts
from test_project.app.gorilla.intelligence import intel


class GorillaBot(BaseLlmBot):
    instructions_prompt = prompts.gorilla_instruction_prompt()
    intel_class = intel.GorillaIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.GorillaIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.gorilla_user_input_prompt(user_input)
        )
