"""Local Diffusers image inference from an image_brief concept.

Only a local model path is accepted. Missing runtime or weights fail closed.
Generated files carry AI labeling and model/output hashes. Visual quality is not
asserted: it needs human visual review of actual output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import RLock

from .image_brief import brief


class ImageUnavailable(RuntimeError):
    pass


def model_identity(root: Path) -> str:
    if not isinstance(root, Path) or not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ImageUnavailable('absolute local model directory required')
    if not root.is_dir() or not (root / 'model_index.json').is_file():
        raise ImageUnavailable('local Diffusers model unavailable')
    digest = hashlib.sha256(b'atlas-local-diffusers-v1\0')
    count, size = 0, 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ImageUnavailable('model symlinks refused')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ImageUnavailable('regular model files required')
        count += 1
        size += path.stat().st_size
        if count > 1000 or size > 20_000_000_000:
            raise ImageUnavailable('model bounds exceeded')
        digest.update(path.relative_to(root).as_posix().encode()); digest.update(b'\0')
        with path.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        digest.update(b'\0')
    return digest.hexdigest()


class LocalProductImages:
    def __init__(self, model_dir: Path, *, device: str = 'cpu'):
        if device not in ('cpu', 'cuda'):
            raise ValueError('device must be cpu or cuda')
        self.root = model_dir
        self.identity = model_identity(model_dir)
        self.device = device
        self._pipeline = None
        self._lock = RLock()

    def generate(self, concept: dict, output: Path, *, seed: int = 0,
                 width: int = 512, height: int = 512, steps: int = 30) -> dict:
        description = brief(concept)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError('seed out of range')
        if any(type(n) is not int or n % 8 or not 256 <= n <= 1024 for n in (width, height)):
            raise ValueError('dimensions must be multiples of eight from 256 to 1024')
        if type(steps) is not int or not 1 <= steps <= 100:
            raise ValueError('steps out of range')
        if not isinstance(output, Path) or not output.is_absolute() or output.suffix.lower() != '.png':
            raise ValueError('absolute PNG output path required')
        if any(p.is_symlink() for p in (output, *output.parents)):
            raise ValueError('output symlinks refused')
        if not output.parent.is_dir() or output.exists():
            raise ValueError('output parent must exist and output must be new')
        with self._lock:
            if model_identity(self.root) != self.identity:
                raise ImageUnavailable('model identity changed')
            try:
                import torch
                from diffusers import DiffusionPipeline
                if self._pipeline is None:
                    self._pipeline = DiffusionPipeline.from_pretrained(
                        str(self.root), local_files_only=True, trust_remote_code=False,
                        use_safetensors=True, torch_dtype=torch.float32).to(self.device)
                result = self._pipeline(prompt=description['prompt'],
                                        generator=torch.Generator(device=self.device).manual_seed(seed),
                                        width=width, height=height, num_inference_steps=steps)
            except (ImportError, OSError, RuntimeError, ValueError) as exc:
                raise ImageUnavailable('local image inference unavailable') from exc
            images = getattr(result, 'images', None)
            nsfw = getattr(result, 'nsfw_content_detected', None)
            if nsfw is not None and any(nsfw):
                raise ImageUnavailable('image safety check refused')
            if not isinstance(images, list) or len(images) != 1:
                raise ImageUnavailable('one image required')
            from PIL import Image, PngImagePlugin
            image = images[0]
            if not isinstance(image, Image.Image) or image.size != (width, height):
                raise ImageUnavailable('invalid generated image')
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text('AI-generated', 'true')
            metadata.add_text('Model-SHA256', self.identity)
            metadata.add_text('Prompt', description['prompt'])
            # Exclusive create prevents accidental overwrite, including cross-process races.
            try:
                with output.open('xb') as stream:
                    image.save(stream, format='PNG', pnginfo=metadata)
            except Exception:
                # Leave ambiguous partial writes in place rather than deleting another process's file.
                raise ImageUnavailable('image file write failed') from None
            with Image.open(output) as check:
                check.verify()
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            return {'path': str(output), 'sha256': digest, 'model_sha256': self.identity,
                    'ai_generated': True, 'prompt': description['prompt'], 'seed': seed,
                    'width': width, 'height': height, 'steps': steps,
                    'visual_review': 'required', 'realism_validated': False}
