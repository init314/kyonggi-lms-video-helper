from unittest import TestCase, main

from services.chunker import split_long_paragraph, split_text_into_chunks


class ChunkerTest(TestCase):
    def test_split_text_into_chunks_preserves_short_text(self) -> None:
        chunks = split_text_into_chunks("첫 문단\n\n두 번째 문단", chunk_size=100, overlap=10)


        self.assertEqual(chunks, ["첫 문단\n\n두 번째 문단"])





    def test_split_text_into_chunks_applies_overlap(self) -> None:
        chunks = split_text_into_chunks("abcdef\n\nghijkl", chunk_size=8, overlap=2)


        self.assertEqual(chunks, ["abcdef", "ef\n\nghijkl"])





    def test_split_long_paragraph_uses_overlap(self) -> None:
        chunks = split_long_paragraph("abcdefghijkl", chunk_size=5, overlap=2)


        self.assertEqual(chunks, ["abcde", "defgh", "ghijk", "jkl"])





    def test_invalid_overlap_rejected(self) -> None:
        with self.assertRaises(ValueError):
            split_text_into_chunks("text", chunk_size=10, overlap=10)


if __name__ == "__main__":
    main()
