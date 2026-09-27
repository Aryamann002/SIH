import io
import wave

import pytest

from scripts.probe_openslr104 import four_second_clip, select_segments


def test_selects_first_four_second_excerpt_per_speaker_and_keeps_source_group():
    segments = "\n".join((
        "s1_a_0000 a 0 3",
        "s1_a_0001 a 3 8",
        "s1_a_0002 a 8 13",
        "s2_b_0000 b 0 4",
    ))
    speakers = "\n".join((
        "s1_a_0000 s1", "s1_a_0001 s1", "s1_a_0002 s1", "s2_b_0000 s2",
    ))
    assert select_segments(segments, speakers) == [
        {"utterance_id": "s1_a_0001", "source_recording_id": "a", "speaker_id": "s1", "start_seconds": 3.0},
        {"utterance_id": "s2_b_0000", "source_recording_id": "b", "speaker_id": "s2", "start_seconds": 0.0},
    ]
    with pytest.raises(ValueError, match="speaker mapping"):
        select_segments(segments, speakers.replace("s2_b_0000 s2", ""))


def test_four_second_clip_keeps_pcm_format_and_rejects_short_source():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(16000 * 2 * 5))
    with wave.open(io.BytesIO(four_second_clip(buffer.getvalue(), 1.0)), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (
            1, 2, 16000, 64000)
    with pytest.raises(ValueError, match="too short"):
        four_second_clip(buffer.getvalue(), 1.01)
