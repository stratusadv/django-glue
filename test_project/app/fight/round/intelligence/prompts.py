from dandy.llm import Prompt

def round_instruction_prompt():
    return (
        Prompt()
        .title('Round Operations')
        .line_break()
        .heading('Purpose')
        .text('This prompt provides instructions for Round operations.')
        .line_break()
        .heading('Instructions')
        .ordered_list([
            'Instruction 1',
            'Instruction 2',
            'Instruction 3',
        ])
        .line_break()
    )

def round_user_input_prompt(user_input: str):

    return (
        Prompt()
        .heading('Round Request')
        .text('The user wants to perform the following operation:')
        .text('')
        .text(user_input)
        .text('')
    )
