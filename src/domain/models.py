from dataclasses import dataclass
from pathlib import Path

from config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL_REF,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OVERLAP,
)


@dataclass(frozen=True)
class ConversionOptions:
    output_dir: Path = DEFAULT_OUTPUT_DIR
    model_ref: str = DEFAULT_MODEL_REF
    language: str = DEFAULT_LANGUAGE
    chunk_size: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_OVERLAP





@dataclass(frozen=True)
class ConversionResult:
    output_dir: Path
    transcript_path: Path
    cleaned_path: Path
    chunk_paths: tuple[Path, ...]
    prompt_paths: tuple[Path, ...]
    timestamp: str





    @property
    def prompt_count(self) -> int:
        return len(self.prompt_paths)
