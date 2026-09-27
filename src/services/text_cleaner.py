DEFAULT_FILLERS = ("어...", "음...", "그니까", "뭐랄까", "약간")





def clean_transcript(text: str, fillers: tuple[str, ...] = DEFAULT_FILLERS) -> str:
    cleaned = text


    for filler in fillers:
        cleaned = cleaned.replace(filler, "")


    return cleaned.strip()
