from pocketsphinx import Decoder
import wave,json,difflib
toks=json.load(open("toks.json"))
words=[w for t in toks for w in t["sp"]]
d=Decoder(dict="my.dict",lm=None,beam=1e-100,wbeam=1e-80,pbeam=1e-100)
d.set_align_text(" ".join(words))
w=wave.open("audio16.wav","rb")
d.start_utt(); d.process_raw(w.readframes(w.getnframes()),full_utt=True); d.end_utt()
raw=[(s.word,s.start_frame/100,s.end_frame/100) for s in d.seg()]
json.dump(raw,open("rawseg.json","w"))
segs=[(a.split('(')[0],b,c) for a,b,c in raw if not a.startswith('<') and not a.startswith('[')]
print(len(segs),len(words))
sm=difflib.SequenceMatcher(a=words,b=[s[0] for s in segs],autojunk=False)
for op in sm.get_opcodes():
    if op[0]!='equal': print(op, words[op[1]:op[2]], [s[0] for s in segs[op[3]:op[4]]])
