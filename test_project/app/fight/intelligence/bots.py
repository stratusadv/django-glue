from dandy.llm import BaseLlmBot

from test_project.app.fight.intelligence import prompts
from test_project.app.fight.intelligence import intel


class FightBot(BaseLlmBot):
    instructions_prompt = prompts.fight_instruction_prompt()
    intel_class = intel.FightIntel

    @classmethod
    def process(
            cls,
            user_input: str
    ) -> intel.FightIntel:

        return cls.process_prompt_to_intel(
            prompt=prompts.fight_user_input_prompt(user_input)
        )
