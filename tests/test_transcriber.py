from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from services.transcriber import resolve_model_ref, validate_model_dir


class TranscriberTest(TestCase):
    def test_validate_model_dir_accepts_required_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_dir = Path(temp_dir)
            (model_dir / "config.json").write_text("{}", encoding="utf-8")
            (model_dir / "model.bin").write_bytes(b"model")


            self.assertEqual(validate_model_dir(model_dir), model_dir)





    def test_validate_model_dir_rejects_missing_model_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_dir = Path(temp_dir)
            (model_dir / "config.json").write_text("{}", encoding="utf-8")


            with self.assertRaises(FileNotFoundError):
                validate_model_dir(model_dir)





    def test_resolve_model_ref_allows_cached_model_name(self) -> None:
        self.assertEqual(resolve_model_ref("small"), "small")





    def test_resolve_model_ref_rejects_empty_value(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model_ref("")


if __name__ == "__main__":
    main()
