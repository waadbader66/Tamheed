"""Real render: short script -> MP4 with audio + video streams. Slow-ish (~15 s)."""
import os, shutil, tempfile
from pathlib import Path
import pytest

os.environ.setdefault("VIDEO_W", "640"); os.environ.setdefault("VIDEO_H", "360"); os.environ.setdefault("VIDEO_FPS", "12")


@pytest.mark.skipif(not shutil.which("ffmpeg") or not (shutil.which("say") or shutil.which("espeak-ng")), reason="needs ffmpeg + a TTS engine")
def test_render_real_mp4():
    from app import video
    f = dict(first="Test", title="Engineer", dept="Electrical Engineering", company="Rimal", stats=[("5", "departments")], priorities=["Safety"],
             dept_short="EE", mission="Power.", role_summary="Builds.", other_depts=["PMO"], people=[{"name": "A B", "title": "Mgr", "tag": "Your manager"}],
             project={"name": "P", "client": "C", "phase": "Design", "background": "B.", "objectives": ["o1", "o2"], "deliverables": ["d1"]},
             responsibilities=[{"title": "R1", "level": "mentoring"}], example={"title": "E", "scenario": "S", "steps": ["s1", "s2"], "deliverable": "D"},
             courses=[{"title": "C1", "priority": "high", "hours": 1}], next=["n1"])
    keys = ["welcome", "company", "department", "team", "project", "responsibilities", "example", "learning", "next"]
    script = {"scenes": [{"key": k, "lines": [{"speaker": "A" if i % 2 else "B", "text": "Hello."}], "visual": f} for i, k in enumerate(keys)]}
    out = Path(tempfile.mkdtemp()) / "v.mp4"
    info = video.render(script, out)
    p = video.probe(out)
    kinds = {s["codec_type"] for s in p["streams"]}
    assert kinds == {"video", "audio"} and float(p["format"]["duration"]) > 5 and info["scenes"] == 9
