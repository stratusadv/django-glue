from dandy.llm import Prompt

def fight_instruction_prompt():
    return (
        Prompt()
        .title('Fight Operations')
        .line_break()
        .heading('Purpose')
        .text('This prompt provides instructions for Fight operations.')
        .line_break()
        .heading('Instructions')
        .ordered_list([
            'Instruction 1',
            'Instruction 2',
            'Instruction 3',
        ])
        .line_break()
    )

def fight_user_input_prompt(user_input: str):

    return (
        Prompt()
        .heading('Fight Request')
        .text('The user wants to perform the following operation:')
        .text('')
        .text(user_input)
        .text('')
    )
