import argparse
import json
from pathlib import Path

import open_clip
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = False

# Paths relative to this handoff directory.
HANDOFF_DIR = Path(__file__).resolve().parent
CHECKPOINT = HANDOFF_DIR / "models" / "open_clip_model.safetensors"
MODEL_DIR = HANDOFF_DIR.parent
PROJECTION_PATH = MODEL_DIR / "metric_learning_v4_model.pt"
METRICS_PATH = MODEL_DIR / "metric_learning_v4_metrics.json"


class Projection(nn.Module):
    def __init__(self):
        super().__init__()
        self.projection = nn.Linear(512, 128, bias=False)

    def forward(self, x):
        return F.normalize(self.projection(x), p=2, dim=1)


class ImageMatcher:
    def __init__(self, threshold=None):
        for path in (CHECKPOINT, PROJECTION_PATH, METRICS_PATH):
            if not path.is_file():
                raise FileNotFoundError(f"Required file not found: {path}")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        with METRICS_PATH.open("r", encoding="utf-8") as f:
            metrics = json.load(f)

        saved_threshold = metrics.get(
            "threshold_selected_on_validation_by_f1"
        )
        if saved_threshold is None:
            raise KeyError(
                "Validation-selected threshold missing from metrics JSON."
            )

        self.threshold = (
            float(saved_threshold) if threshold is None else float(threshold)
        )

        self.clip, _, self.preprocess = (
            open_clip.create_model_and_transforms(
                model_name="ViT-B-32",
                pretrained=str(CHECKPOINT),
                device=self.device,
            )
        )
        self.clip.eval()

        checkpoint = torch.load(
            PROJECTION_PATH,
            map_location="cpu",
            weights_only=True,
        )

        if checkpoint.get("input_dim") != 512:
            raise ValueError("Unexpected projection input dimension.")
        if checkpoint.get("embedding_dim") != 128:
            raise ValueError("Unexpected projection output dimension.")

        self.projection = Projection().to(self.device)
        self.projection.load_state_dict(checkpoint["state_dict"])
        self.projection.eval()

    def score(self, image_path_1, image_path_2):
        paths = [Path(image_path_1), Path(image_path_2)]

        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f"Image not found: {path}")

        tensors = []
        for path in paths:
            with Image.open(path) as image:
                tensors.append(self.preprocess(image.convert("RGB")))

        batch = torch.stack(tensors).to(self.device)

        with torch.inference_mode():
            features = self.clip.encode_image(batch).float()
            features = features / features.norm(
                dim=-1, keepdim=True
            ).clamp_min(1e-12)

            projected = self.projection(features)
            similarity = (projected[0] * projected[1]).sum().item()

        return {
            "similarity": float(similarity),
            "threshold": self.threshold,
            "predicted_match": bool(similarity >= self.threshold),
            "score_type": "cosine_similarity_not_probability",
            "device": self.device,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Score two images with the trained V4 image matcher."
    )
    parser.add_argument("image1", help="Path to the first image")
    parser.add_argument("image2", help="Path to the second image")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional threshold override; default uses the validation-selected threshold.",
    )
    args = parser.parse_args()

    matcher = ImageMatcher(threshold=args.threshold)
    result = matcher.score(args.image1, args.image2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
