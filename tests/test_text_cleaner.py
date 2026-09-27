from unittest import TestCase, main

from services.text_cleaner import clean_transcript


class TextCleanerTest(TestCase):
    def test_clean_transcript_removes_default_fillers(self) -> None:
        cleaned = clean_transcript("어... 오늘은 그니까 운영체제를 약간 배웁니다.")


        self.assertEqual(cleaned, "오늘은  운영체제를  배웁니다.")


if __name__ == "__main__":
    main()
