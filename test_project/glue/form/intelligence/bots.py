from dandy.llm import BaseLlmBot

from test_project.glue.form.intelligence import prompts
from test_project.glue.form.intelligence import intel


class FormBot(BaseLlmBot):
    instructions_prompt = prompts.form_instruction_prompt()
    intel_class = intel.FormIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.FormIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.form_user_input_prompt(user_input)
        )
