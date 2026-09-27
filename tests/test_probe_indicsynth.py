import io
import shutil
import struct
import wave

import pytest

from scripts.probe_indicsynth import normalise_wav, validate_asset_url


def test_asset_url_must_match_pinned_dataset_revision_and_row():
    asset = ("https://datasets-server.huggingface.co/cached-assets/vdivyasharma/IndicSynth/--/"
             "c0a10386b723717aff682f757bd67f72983f269f/--/Hindi/train/0/audio/audio.wav?Expires=1")
    validate_asset_url(asset, "Hindi", 0)
    with pytest.raises(ValueError, match="asset URL"):
        validate_asset_url(asset.replace("/Hindi/train/0/", "/Hindi/train/1/"), "Hindi", 0)
    with pytest.raises(ValueError, match="asset URL"):
        validate_asset_url(asset.replace("datasets-server.huggingface.co", "example.com"), "Hindi", 0)
    with pytest.raises(ValueError, match="asset URL"):
        validate_asset_url(asset.replace("c0a10386b723717aff682f757bd67f72983f269f", "old-revision"), "Hindi", 0)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is needed for evaluation-only resampling")
def test_normalisation_produces_upload_compatible_pcm_without_saving_audio():
    source = io.BytesIO()
    with wave.open(source, "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x01\x00" * 24000)
    converted, sample_rate, duration = normalise_wav(source.getvalue())
    assert (sample_rate, duration) == (24000, 1.0)
    with wave.open(io.BytesIO(converted), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 16000, 16000)
    samples = struct.pack("<f", 0.1) * 24000
    fmt = b"fmt " + struct.pack("<IHHIIHH", 16, 3, 1, 24000, 96000, 4, 32)
    body = b"WAVE" + fmt + b"data" + struct.pack("<I", len(samples)) + samples
    float_wav = b"RIFF" + struct.pack("<I", len(body)) + body
    converted, sample_rate, duration = normalise_wav(float_wav)
    assert (sample_rate, duration) == (24000, 1.0)
    with wave.open(io.BytesIO(converted), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 16000, 16000)
    with pytest.raises(ValueError, match="RIFF/WAV|WAV chunk"):
        normalise_wav(float_wav[:-1])
