"""Tifo Cast audio with Gemini TTS (owner, 2026-09-27): «حامد» = Orus, «مها» = Aoede, the owner's picks from the audition
(ai/voice_audition.py). Same rules as the films' مريم/مايد: an Emirati persona that names the forbidden forms, the pinned
pro TTS model, numbers already written as Emirati words (gen.spoken), and every line transcribed with whisper; a line
whose transcript shows a Fusha/foreign form is re-taken (up to 3 takes), and the cleanest take is kept.
  python3 ai/cast_voice.py cache/ai/podcast/<week>.json   ->  same path .mp3
"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_audition import persona, MODEL, _tts

VOICES = {"hamed": ("Orus", "m"), "maha": ("Aoede", "f")}   # owner, 2026-09-27: «حامد اول صوت ريال ومها ثاني صوت حرمة»
BAD = re.compile(r"\bالآن\b|\bماذا\b|\bأين\b|\bلماذا\b|\bكثيرا\b|\bوش\b|عليج|\bلج\b|رايج")
WHISPER = os.path.expanduser("~/workspace/content-pipeline/.venv/bin/python")

def transcribe(files):
    code = "import sys\nfrom faster_whisper import WhisperModel\nm = WhisperModel('small', device='cpu', compute_type='int8')\nfor f in sys.argv[1:]:\n    s, _ = m.transcribe(f, language='ar', beam_size=1)\n    print(f + '\\t' + ' '.join(x.text.strip() for x in s))"
    out = subprocess.run([WHISPER, "-c", code] + files, capture_output=True, text=True).stdout
    return dict(l.split("\t", 1) for l in out.strip().splitlines() if "\t" in l)

def synth(path):
    ep = json.load(open(path)); base = os.path.abspath(path)[:-5]; work = base + "_lines"; os.makedirs(work, exist_ok=True); report = []
    for i, l in enumerate(ep["lines"]):
        voice, g = VOICES[l["who"]]; text = l.get("spoken") or l["text"]; best = None
        for take in range(2):   # TTS quota is 100/day, shared with the films
            f = os.path.join(work, f"{i:02d}_{take}.wav")
            for a in range(0 if os.path.exists(f) else 4):   # resumable: keep takes already paid for
                try: _tts(text, f, voice, persona(g), MODEL); break
                except RuntimeError as e: print(i, str(e)[:60], flush=True); time.sleep(4 * (a + 1))
            if not os.path.exists(f): continue
            tr = transcribe([f]).get(f, ""); bad = BAD.findall(tr)
            if best is None or len(bad) < best[2]: best = (f, tr, len(bad))
            if not bad: break
        report.append({"line": i, "who": l["who"], "take": best and best[0], "transcript": best and best[1], "flags": best and best[2]})
    gap = os.path.join(work, "gap.wav"); subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.35", "-c:a", "pcm_s24le", gap], check=True)
    lst = os.path.join(work, "list.txt"); open(lst, "w").write("".join(f"file '{r['take']}'\nfile '{gap}'\n" for r in report if r["take"]))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-af", "loudnorm=I=-16:TP=-1.5", "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", base + ".mp3"], check=True)
    ep["voices"] = {"hamed": "Gemini Orus", "maha": "Gemini Aoede"}; ep["tts_model"] = MODEL; ep["qa"] = report
    json.dump(ep, open(path, "w"), ensure_ascii=False, indent=1)
    print(json.dumps([(r["line"], r["who"], r["flags"]) for r in report]))
    return base + ".mp3"

if __name__ == "__main__":
    print(synth(sys.argv[1]))
