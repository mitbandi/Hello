import numpy as np, wave
SR=48000; DUR=147.0; N=int(DUR*SR); t=np.arange(N)/SR
BPM=100; beat=60/BPM; bar=4*beat
def midi(m): return 440*2**((m-69)/12)
prog=[[57,60,64],[53,57,60],[48,52,55],[55,59,62]]  # Am F C G
out=np.zeros((N,2))
def lp(x,fc):
    X=np.fft.rfft(x,axis=0); f=np.fft.rfftfreq(len(x),1/SR)
    X*= (1/(1+(f/fc)**4))[:,None] if x.ndim==2 else 1/(1+(f/fc)**4)
    return np.fft.irfft(X,n=len(x),axis=0)
rng=np.random.default_rng(3)
nb=int(DUR/bar)+1
pad=np.zeros((N,2))
for b in range(nb):
    ch=prog[b%4]; s=int(b*bar*SR); e=min(N,int((b+1)*bar*SR+0.6*SR))
    if s>=N: break
    tt=np.arange(e-s)/SR; L=(e-s)/SR
    en=np.minimum(1,tt/0.6)*np.minimum(1,np.maximum(0,(L-tt))/0.6)
    for m in ch+[ch[0]-12]:
        for det,side in [(-0.08,0),(0.08,1)]:
            f=midi(m)*2**(det/12)
            ph=rng.uniform(0,6.28)
            saw=2*((f*tt+ph/6.28)%1)-1
            pad[s:e,side]+=saw*en*0.12
pad=lp(pad,1400)
# arpeggio pluck (8th notes)
arp=np.zeros(N); step=beat/2
for k in range(int(DUR/step)):
    b=int(k*step/bar); ch=prog[b%4]; m=[ch[0]+12,ch[1]+12,ch[2]+12,ch[1]+12][k%4]
    s=int(k*step*SR); n=int(0.5*SR); e=min(N,s+n); tt=np.arange(e-s)/SR
    arp[s:e]+=np.sin(2*np.pi*midi(m)*tt)*np.exp(-tt*7)*0.25+np.sin(4*np.pi*midi(m)*tt)*np.exp(-tt*12)*0.08
# soft kick on beats + sub bass
kick=np.zeros(N); bass=np.zeros(N)
for k in range(int(DUR/beat)):
    s=int(k*beat*SR); n=int(0.35*SR); e=min(N,s+n); tt=np.arange(e-s)/SR
    kick[s:e]+=np.sin(2*np.pi*np.cumsum(50+80*np.exp(-tt*35))/SR)*np.exp(-tt*9)*0.5
for b in range(nb):
    s=int(b*bar*SR); e=min(N,int((b+1)*bar*SR)); 
    if s>=N: break
    tt=np.arange(e-s)/SR
    bass[s:e]+=np.sin(2*np.pi*midi(prog[b%4][0]-24)*tt)*0.35*np.minimum(1,tt/0.05)*np.exp(-tt*0.3)
# arrangement: intensity curve
def ramp(a,b,v0,v1): 
    x=np.clip((t-a)/(b-a),0,1); return v0+(v1-v0)*x
arp_g=np.where(t<9,0.3,1.0)
kick_g=np.where((t>40)&(t<134),1,0)*np.clip((t-40)/2,0,1)
fade=np.clip((DUR-t)/2.5,0,1)*np.clip(t/1.0,0,1)
mix=pad.copy()
mix[:,0]+=arp*arp_g*0.9+kick*kick_g*0.6+bass*0.8
mix[:,1]+=np.roll(arp,int(0.012*SR))*arp_g*0.9+kick*kick_g*0.6+bass*0.8
mix*=fade[:,None]
mix/=np.max(np.abs(mix))*1.1
w=wave.open("assets/music.wav","wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((mix*32767).astype(np.int16).tobytes()); w.close()
