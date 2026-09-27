import io
import shutil
import wave

import pytest

from scripts.probe_monsoon import select_rows, validate_asset_url
from scripts.evaluate_audio import wav_prefix
from scripts.probe_indicsynth import normalise_wav


def test_selects_one_four_second_clip_per_speaker_across_blocks():
    batches = [
        [{"row_idx": 0, "row": {"id": "a", "speaker_id": 1, "audio_length_s": 3}},
         {"row_idx": 1, "row": {"id": "b", "speaker_id": 1, "audio_length_s": 5}},
         {"row_idx": 2, "row": {"id": "c", "speaker_id": 2, "audio_length_s": 6}}],
        [{"row_idx": 100, "row": {"id": "d", "speaker_id": 1, "audio_length_s": 7}},
         {"row_idx": 101, "row": {"id": "e", "speaker_id": 3, "audio_length_s": 4}}],
    ]
    assert [item["row_idx"] for item in select_rows(batches, 2, 1)] == [1, 101]
    with pytest.raises(ValueError, match="eligible"):
        select_rows(batches, 2, 2)


def test_asset_is_bound_to_dataset_revision_and_row():
    dataset = "VoiceArena/MonsoonASR-Open-ASR-leaderboard-en-IN"
    revision = "bc1da7b42ef6e2853123c97bf6d22067e4802d11"
    asset = ("https://datasets-server.huggingface.co/cached-assets/" + dataset
             + "/--/" + revision + "/--/default/test/10/audio/audio.wav?Expires=1")
    validate_asset_url(asset, dataset, revision, 10)
    with pytest.raises(ValueError, match="asset URL"):
        validate_asset_url(asset.replace("/test/10/", "/test/11/"), dataset, revision, 10)
    with pytest.raises(ValueError, match="asset URL"):
        validate_asset_url(asset.replace(revision, "older"), dataset, revision, 10)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is needed for dataset normalization")
def test_44100_hz_source_becomes_exact_four_second_upload_clip():
    source = io.BytesIO()
    with wave.open(source, "wb") as wav:
        wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x01\x00" * (44100 * 5))
    normalized, rate, duration = normalise_wav(source.getvalue())
    clip = wav_prefix(normalized, 4)
    assert (rate, duration) == (44100, 5.0)
    with wave.open(io.BytesIO(clip), "rb") as wav:
        assert (wav.getframerate(), wav.getnframes()) == (16000, 64000)
