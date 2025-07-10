
def get_response(user_input: str) -> str:
    #
    lowered: str = user_input.lower()
    if lowered == '':
        return "Well, you\'re awfully silent..."
