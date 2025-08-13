from dandy.llm import Prompt

def session_data_instruction_prompt():
    return (
        Prompt()
        .title('Session Data Operations')
        .line_break()
        .heading('Purpose')
        .text('This prompt provides instructions for Session Data operations.')
        .line_break()
        .heading('Instructions')
        .ordered_list([
            'Process session data requests',
            'Format session data for display',
            'Handle session data operations',
        ])
        .line_break()
    )

def session_data_user_input_prompt(user_input: str):

    return (
        Prompt()
        .heading('Session Data Request')
        .text('The user wants to perform the following operation:')
        .text('')
        .text(user_input)
        .text('')
    )
