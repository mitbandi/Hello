import sherpa_onnx, numpy as np, wave, json
w=wave.open("audio16.wav","rb"); a=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
sr=16000; d="models/sherpa-onnx-whisper-small.en/small.en-"
rec=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=d+"encoder.int8.onnx",decoder=d+"decoder.int8.onnx",tokens=d+"tokens.txt",language="en",task="transcribe",num_threads=4,tail_paddings=2000)
# energy per 10ms
hop=160; e=np.array([np.sqrt(np.mean(a[i:i+hop]**2)+1e-12) for i in range(0,len(a)-hop,hop)])
es=np.convolve(e,np.ones(15)/15,'same')
cuts=[0]; t=0
while True:
    lo=cuts[-1]+1000; hi=cuts[-1]+1600   # 10-16s
    if hi>=len(es): break
    cuts.append(lo+int(np.argmin(es[lo:hi])))
cuts.append(len(es))
out=[]
for s,e2 in zip(cuts,cuts[1:]):
    st=rec.create_stream(); st.accept_waveform(sr,a[s*hop:e2*hop]); rec.decode_stream(st)
    txt=st.result.text.strip(); print(f"[{s/100:.2f}-{e2/100:.2f}] {txt}",flush=True)
    out.append({"start":s/100,"end":e2/100,"text":txt})
json.dump(out,open("chunks.json","w"),indent=1)
