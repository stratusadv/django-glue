from dandy.llm import BaseLlmBot

from test_project.glue.intelligence import prompts
from test_project.glue.intelligence import intel


class SessionDataBot(BaseLlmBot):
    instructions_prompt = prompts.session_data_instruction_prompt()
    intel_class = intel.SessionDataIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.SessionDataIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.session_data_user_input_prompt(user_input)
        )
