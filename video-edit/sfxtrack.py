import numpy as np, wave
SR=48000; DUR=146.5; N=int(DUR*SR)
def load(n):
    w=wave.open(f"assets/{n}.wav"); x=np.frombuffer(w.readframes(w.getnframes()),np.int16).reshape(-1,2).astype(np.float32)/32768; return x
S={n:load(n) for n in ['whoosh','swish','pop','tick','impact','riser','shimmer','ding']}
out=np.zeros((N,2),np.float32)
def put(n,t,g):
    x=S[n]; s=int(t*SR); e=min(N,s+len(x)); out[s:e]+=x[:e-s]*g
segs=[(2.35,11.55),(11.55,20.0),(24.15,31.3),(38.55,49.65),(56.8,68.9),(68.9,79.95),(88.95,97.35),(97.35,111.75),(119.7,127.7),(127.7,132.0)]
starts={s for s,e in segs}; ends={e for s,e in segs}
for s,e in segs:
    put('whoosh',s-0.15,0.32 if s not in ends else 0.22)
    if e not in starts: put('swish',e-0.05,0.25)
put('impact',0.12,0.45); put('swish',0.95,0.18)
for t in [3.0,4.3,6.9,7.8,12.4,13.4,14.4,24.8,26.6,44.5,45.5,54.5,57.9,59.1,79.0,85.8,97.5,102.4,108.0,108.6,109.6,112.0,123.85,124.25,124.6]:
    put('pop',t,0.22)
for t in [10.2,76.3,99.4,104.7,129.6]: put('impact',t-0.02,0.3)
for a,b in [(63.9,65.0),(14.6,15.4)]:
    for t in np.arange(a,b,0.07): put('tick',t,0.12)
for t0 in [91.7,92.9,94.7]:
    for t in np.arange(t0+0.1,t0+1.0,0.06): put('tick',t,0.1)
    put('ding',t0+1.0,0.16)
for k in range(10): put('pop',129.5+k*0.07,0.1)
put('whoosh',134.75,0.35); put('riser',139.6,0.3); put('impact',141.0,0.35); put('shimmer',141.35,0.25); put('whoosh',141.3,0.15)
w=wave.open("assets/sfx_track.wav","wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(out,-1,1)*32767).astype(np.int16).tobytes()); w.close()
print(np.abs(out).max())
