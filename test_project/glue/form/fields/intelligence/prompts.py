from dandy.llm import Prompt

def fields_instruction_prompt():
    return (
        Prompt()
        .title('Fields Operations')
        .line_break()
        .heading('Purpose')
        .text('This prompt provides instructions for Fields operations.')
        .line_break()
        .heading('Instructions')
        .ordered_list([
            'Instruction 1',
            'Instruction 2',
            'Instruction 3',
        ])
        .line_break()
    )

def fields_user_input_prompt(user_input: str):

    return (
        Prompt()
        .heading('Fields Request')
        .text('The user wants to perform the following operation:')
        .text('')
        .text(user_input)
        .text('')
    )
