"""Pretrained CLIP image encoder (CPU by default)."""
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Union
import numpy as np
from PIL import Image
import torch

DEFAULT_MODEL = "openai/clip-vit-base-patch32"
PathLike = Union[str, os.PathLike]


class ClipImageEncoder:
    """Load CLIP once, reuse for every image. CPU-first, eval mode, no grad."""

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 device: str | None = None, cache_dir: str | None = None):
        self.model_name = model_name
        self.cache_dir = cache_dir or os.environ.get(
            "LOSTFOUND_MODEL_CACHE", None)
        # CPU by default; allow cuda only if available and requested.
        if device is None:
            device = "cpu"
        if device.startswith("cuda") and not torch.cuda.is_available():
            print("[vision] CUDA requested but not available. Using CPU.")
            device = "cpu"
        self.device = device
        self._model = None
        self._processor = None
        self._dim: int | None = None
        self._load()

    def _load(self) -> None:
        """Download/load model once. Clear error if offline."""
        try:
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as exc:
            raise ImportError(
                "transformers/torch not installed. Run: "
                "pip install -r requirements.txt"
            ) from exc
        try:
            print(f"[vision] Loading CLIP model '{self.model_name}' "
                  f"on {self.device} ... (first run downloads ~350MB)")
            kwargs = {"trust_remote_code": False}
            if self.cache_dir:
                Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
                kwargs["cache_dir"] = self.cache_dir
            self._processor = CLIPProcessor.from_pretrained(
                self.model_name, **kwargs)
            self._model = CLIPModel.from_pretrained(self.model_name, **kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Could not load CLIP model '{self.model_name}'.\n"
                f"Reason: {exc}\n"
                f"Fixes:\n"
                f"  1. Check internet (first download needs it).\n"
                f"  2. Check model name spelling.\n"
                f"  3. Set cache dir: set LOSTFOUND_MODEL_CACHE=C:\\models\\clip\n"
                f"  4. Pre-download with: huggingface-cli download {self.model_name}"
            ) from exc
        self._model.to(self.device)
        self._model.eval()  # inference only, disable dropout etc.
        for p in self._model.parameters():
            p.requires_grad_(False)
        # embedding size e.g. 512 for ViT-B/32
        try:
            self._dim = int(self._model.config.projection_dim)
        except Exception:
            self._dim = 512

    @property
    def embedding_dim(self) -> int:
        return int(self._dim or 512)

    def _load_pil(self, image_path: PathLike) -> Image.Image:
        p = Path(str(image_path).strip().strip('"').strip("'"))
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Image not found: {p}")
        try:
            img = Image.open(p).convert("RGB")
        except Exception as exc:
            raise ValueError(
                f"Unable to decode image (corrupt?): {p} ({exc})") from exc
        return img

    @torch.no_grad()
    def encode_image(self, image_path: PathLike) -> np.ndarray:
        """Return L2-normalised float32 embedding, shape (dim,)."""
        if self._model is None or self._processor is None:
            raise RuntimeError("Model not loaded.")
        pil = self._load_pil(image_path)
        inputs = self._processor(images=pil, return_tensors="pt")
        pixel = inputs["pixel_values"].to(self.device)
        feats = self._model.get_image_features(pixel_values=pixel)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True).clamp(min=1e-12)
        return feats[0].detach().cpu().numpy().astype(np.float32)

    @torch.no_grad()
    def encode_images(self, paths: List[PathLike]) -> np.ndarray:
        """Batch encode -> array shape (N, dim), L2-normalised."""
        if self._model is None or self._processor is None:
            raise RuntimeError("Model not loaded.")
        pils = [self._load_pil(p) for p in paths]
        if not pils:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        inputs = self._processor(images=pils, return_tensors="pt", padding=True)
        pixel = inputs["pixel_values"].to(self.device)
        feats = self._model.get_image_features(pixel_values=pixel)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True).clamp(min=1e-12)
        return feats.detach().cpu().numpy().astype(np.float32)

