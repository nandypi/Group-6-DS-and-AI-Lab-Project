'''splits markdown into chunks for embedding'''

def chunk_text(text: str):
    """
    Split markdown into paragraph chunks.
    """

    chunks = []

    paragraphs = text.split("\n\n")

    current = ""

    for para in paragraphs:

        para = para.strip()

        if not para:
            continue

        if len(current) + len(para) < 800:
            current += "\n\n" + para
        else:
            chunks.append(current.strip())
            current = para

    if current:
        chunks.append(current.strip())

    return chunks