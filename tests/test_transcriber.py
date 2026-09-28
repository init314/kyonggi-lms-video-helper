from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import Mock, patch
import wave

from services.transcriber import (is_amd_rocm_available, iter_audio_chunks,
                                  resolve_model_ref, transcribe_amd_gpu,
                                  validate_model_dir)


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

    def test_detects_rocm_enabled_pytorch_device(self) -> None:
        fake_torch = SimpleNamespace(version=SimpleNamespace(hip="7.2.1"),
                                     cuda=SimpleNamespace(is_available=lambda: True))
        with patch.dict("sys.modules", {"torch": fake_torch}):
            self.assertTrue(is_amd_rocm_available())

    def test_does_not_treat_cuda_or_cpu_torch_as_rocm(self) -> None:
        fake_torch = SimpleNamespace(version=SimpleNamespace(hip=None),
                                     cuda=SimpleNamespace(is_available=lambda: True))
        with patch.dict("sys.modules", {"torch": fake_torch}):
            self.assertFalse(is_amd_rocm_available())

    def test_amd_audio_reader_yields_bounded_timestamped_chunks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "short.wav"
            with wave.open(str(audio_path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 40000)

            chunks = list(iter_audio_chunks(audio_path, chunk_seconds=1))

        self.assertEqual([offset for offset, _ in chunks], [0, 1, 2])
        self.assertEqual([len(samples) for _, samples in chunks], [16000, 16000, 8000])

    def test_amd_transcription_keeps_timestamps_across_audio_chunks(self) -> None:
        fake_torch = SimpleNamespace(float16="float16")
        fake_transformers = SimpleNamespace(AutoModelForSpeechSeq2Seq=object,
                                            AutoProcessor=object, pipeline=object)
        recognize = Mock(side_effect=[
            {"chunks": [{"text": " 첫 문장 ", "timestamp": (0, 2)}]},
            {"chunks": [{"text": " 다음 문장 ", "timestamp": (0, 2)}]},
        ])
        with patch.dict("sys.modules", {"torch": fake_torch, "transformers": fake_transformers}), \
             patch("services.transcriber.load_amd_model", return_value=recognize) as load_model, \
             patch("services.transcriber.iter_audio_chunks", return_value=[(0, [0.0]), (30, [0.0])]):
            transcript = transcribe_amd_gpu("audio.wav", "large-v3-turbo", "ko")

        self.assertEqual(load_model.call_args.args[0], "openai/whisper-large-v3-turbo")
        self.assertIn("[00:00 - 00:02] 첫 문장", transcript)
        self.assertIn("[00:30 - 00:32] 다음 문장", transcript)


if __name__ == "__main__":
    main()
