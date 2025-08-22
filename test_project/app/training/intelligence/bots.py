from dandy.llm import BaseLlmBot

from test_project.app.training.intelligence import prompts
from test_project.app.training.intelligence import intel


class TrainingBot(BaseLlmBot):
    instructions_prompt = prompts.training_instruction_prompt()
    intel_class = intel.TrainingIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.TrainingIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.training_user_input_prompt(user_input)
        )
