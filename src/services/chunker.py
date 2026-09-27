def split_text_into_chunks(
    text: str,
    chunk_size: int = 8000,
    overlap: int = 500,
) -> list[str]:
    """Split long transcript text into GPT-sized chunks."""
    validate_chunk_options(chunk_size, overlap)


    if not text:
        return []


    paragraphs = [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]
    chunks: list[str] = []
    current_chunk = ""


    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""


            chunks.extend(split_long_paragraph(paragraph, chunk_size, overlap))
            continue


        if len(current_chunk) + len(paragraph) + 2 <= chunk_size:
            current_chunk += paragraph + "\n\n"
            continue


        previous_chunk = current_chunk.strip()


        if previous_chunk:
            chunks.append(previous_chunk)


        overlap_text = previous_chunk[-overlap:] if overlap > 0 else ""
        current_chunk = f"{overlap_text}\n\n{paragraph}\n\n"


    if current_chunk.strip():
        chunks.append(current_chunk.strip())


    return chunks





def split_long_paragraph(
    paragraph: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Force-split a paragraph that is longer than a single chunk."""
    validate_chunk_options(chunk_size, overlap)


    result: list[str] = []
    start = 0


    while start < len(paragraph):
        end = start + chunk_size
        chunk = paragraph[start:end].strip()


        if chunk:
            result.append(chunk)


        if end >= len(paragraph):
            break


        start = end - overlap


    return result





def validate_chunk_options(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size는 1 이상이어야 합니다.")


    if overlap < 0:
        raise ValueError("overlap은 0 이상이어야 합니다.")


    if overlap >= chunk_size:
        raise ValueError("overlap은 chunk_size보다 작아야 합니다.")
