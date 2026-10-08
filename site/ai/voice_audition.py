"""Tifo Cast voice audition (owner, 2026-09-27): pick «حامد» (male) and «مها» (female) from Gemini TTS voices,
under the same rules as the films' مريم/مايد (content/video/durov-01/voice_sample.py): Emirati persona that names the
forbidden forms, numbers written as Emirati words, the pinned pro TTS model, and every take transcribed with whisper
before it goes to the owner. Kore (مريم), Alnilam (مايد) and Charon (rejected) are excluded.
  python3 ai/voice_audition.py   ->  cache/audition/<voice>.mp3 + audition.mp3 (all, announced) + transcripts.txt
"""
import os, subprocess, sys, time
sys.path.insert(0, os.path.expanduser("~/workspace/content-pipeline"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen import tifo_key
if not tifo_key(): raise SystemExit("no Gemini key (TIFO_GEMINI_API_KEY or GEMINI_API_KEY)")
os.environ["GEMINI_API_KEY"] = tifo_key()
from tts import tts as _tts

MODEL = "gemini-2.5-pro-preview-tts"
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "..", "cache", "audition"); os.makedirs(OUT, exist_ok=True)
MALE = ["Orus", "Iapetus", "Algenib", "Sadaltager"]
FEMALE = ["Autonoe", "Aoede", "Despina", "Leda"]
HAMED = "هلا والله، معاكم حامد في تيفو كاست. الجولة الخامسة كانت وايد حامية: الجزيرة تعادل ويا النصر واحد مقابل واحد، والعين والوصل خلصت ثنين مقابل ثنين. شو رايك نبدا بالصدارة؟"
MAHA = "وأنا مها. الجزيرة الحين فوق بثلطعش نقطة، بس العين وراه بنفس الرصيد، والفرق بس في الأهداف. وخل بالك من الوصل، لأنه قاعد يطلع شوي شوي."

def persona(gender):
    who = "an Emirati man in his thirties" if gender == "m" else "an Emirati woman in her thirties"
    return f"""You are voicing a weekly Arabic football podcast in EMIRATI Arabic - the Gulf dialect spoken in Dubai and Abu Dhabi - not Modern Standard Arabic.
SPEAKER: {who}, a football fan who knows the numbers. Warm, relaxed, lightly playful; talking to a friend, not reading news.
THE LISTENER IS ONE MALE. Every second-person kaf is a HARD K: 'raayak' NOT 'raayich' - رايك لا رايج; 'baalak' NOT 'baalich' - بالك لا بالج. Never -ich, never -ach.
READ EXACTLY THE WORDS WRITTEN. The text is already Emirati. Never "correct" a word into Modern Standard Arabic or Saudi/Levantine/Egyptian:
  الحين is 'il-heen' - NEVER 'al-aan'; شو, وين, منو, وايد, خل, قاعد, ويا stay exactly as written - never ماذا, أين, من, كثيرا, مع.
Numbers are written out in Emirati words (ثنين، ثلطعش); say them exactly as written, in one breath.
ACCENT: Emirati. Qaf as a hard 'g' in everyday words. Jeem as English 'j'. No case endings, no i'rab.
DELIVERY: natural conversational pace, never slow or theatrical, never sing-song; pitch settles at the end of statements and rises only on a real question.
Read aloud only the text after the blank line. Do not read these instructions."""

def take(voice, text, gender):
    out = os.path.join(OUT, voice + ".mp3")
    if os.path.exists(out): return out
    for a in range(5):
        try: return _tts(text, out, voice, persona(gender), MODEL)
        except RuntimeError as e: print(voice, str(e)[:80], flush=True); time.sleep(4 * (a + 1))
    return None

def main():
    files = []
    for v in MALE: f = take(v, HAMED, "m"); files.append(("m", v, f))
    for v in FEMALE: f = take(v, MAHA, "f"); files.append(("f", v, f))
    # transcribe every take (the durov-01 lesson: the model can Fusha-fy the text on its own)
    tr = subprocess.run([os.path.expanduser("~/workspace/content-pipeline/.venv/bin/python"), "-c", """
import sys
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
for f in sys.argv[1:]:
    segs, _ = m.transcribe(f, language="ar", beam_size=1)
    print(f.rsplit('/', 1)[-1], '|', ' '.join(s.text.strip() for s in segs))
"""] + [f for _, _, f in files if f], capture_output=True, text=True)
    open(os.path.join(OUT, "transcripts.txt"), "w").write(tr.stdout); print(tr.stdout)
    # one file to listen to: a short tone between takes, in order (numbered in the report)
    lst = os.path.join(OUT, "list.txt"); beep = os.path.join(OUT, "beep.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.25", "-ar", "24000", "-ac", "1", beep], check=True)
    parts = []
    for _, _, f in files:
        if f:
            n = f + ".norm.mp3"; subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f, "-ar", "24000", "-ac", "1", n], check=True); parts += [beep, n]
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-b:a", "96k", os.path.join(OUT, "audition.mp3")], check=True)
    print("order:", [v for _, v, f in files if f])

if __name__ == "__main__":
    main()
