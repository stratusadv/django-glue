from dandy.llm import BaseLlmBot

from test_project.app.fight.round.intelligence import prompts
from test_project.app.fight.round.intelligence import intel


class RoundBot(BaseLlmBot):
    instructions_prompt = prompts.round_instruction_prompt()
    intel_class = intel.RoundIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.RoundIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.round_user_input_prompt(user_input)
        )
