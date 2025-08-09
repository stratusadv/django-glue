from dandy.llm import BaseLlmBot

from test_project.glue.form.fields.intelligence import prompts
from test_project.glue.form.fields.intelligence import intel


class FieldsBot(BaseLlmBot):
    instructions_prompt = prompts.fields_instruction_prompt()
    intel_class = intel.FieldsIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.FieldsIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.fields_user_input_prompt(user_input)
        )
