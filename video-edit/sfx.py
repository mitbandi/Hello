import numpy as np, wave
SR=48000
def save(name,x):
    x=np.asarray(x,np.float32); x=x/ (np.max(np.abs(x))+1e-9)*0.9
    if x.ndim==1: x=np.stack([x,x],1)
    w=wave.open(f"assets/{name}.wav","wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x*32767).astype(np.int16).tobytes()); w.close()
rng=np.random.default_rng(1)
def bandnoise(n,f0,f1,q=6):
    # sweeping resonant filter on white noise (state variable)
    x=rng.standard_normal(n); y=np.zeros(n); low=band=0.0
    f=np.geomspace(f0,f1,n)
    for i in range(n):
        F=2*np.sin(np.pi*f[i]/SR); high=x[i]-low-band/q*2; band+=F*high; low+=F*band; y[i]=band
    return y
def env(n,a,r):
    t=np.arange(n)/SR; e=np.minimum(1,t/a)*np.exp(-np.maximum(0,t-a)/r); return e
# whoosh
n=int(0.7*SR); t=np.arange(n)/SR
e=np.sin(np.pi*np.clip(t/0.7,0,1))**2
wL=bandnoise(n,300,4000)*e; wR=np.roll(wL,200)
save("whoosh",np.stack([wL*np.linspace(1,0.4,n),wR*np.linspace(0.4,1,n)],1))
# soft whoosh reverse (swish in)
save("swish",bandnoise(int(0.4*SR),3000,600)*np.sin(np.pi*np.linspace(0,1,int(0.4*SR)))**1.5)
# pop
n=int(0.12*SR);t=np.arange(n)/SR
f=900*np.exp(-t*30)+300; pop=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*40)
save("pop",pop)
# tick
n=int(0.03*SR);t=np.arange(n)/SR
save("tick",(np.sin(2*np.pi*2400*t)+0.5*rng.standard_normal(n))*np.exp(-t*250))
# impact/boom
n=int(1.6*SR);t=np.arange(n)/SR
f=110*np.exp(-t*4)+38; boom=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*2.8)
boom+=bandnoise(n,2500,200,2)*np.exp(-t*12)*0.5
save("impact",boom)
# riser
n=int(1.5*SR);t=np.arange(n)/SR
r=bandnoise(n,200,6000,8)*(t/1.5)**2
r+=0.3*np.sin(2*np.pi*np.cumsum(np.geomspace(100,800,n))/SR)*(t/1.5)**3
save("riser",r)
# shimmer (logo)
n=int(2.5*SR);t=np.arange(n)/SR; s=np.zeros(n)
for k,fr in enumerate([1318.5,1567.98,1975.5,2637]):
    d=int(k*0.08*SR); s[d:]+=np.sin(2*np.pi*fr*t[:n-d])*np.exp(-t[:n-d]*2.2)
save("shimmer",s)
# ding/notification (for stats)
n=int(0.8*SR);t=np.arange(n)/SR
save("ding",(np.sin(2*np.pi*1046.5*t)+0.5*np.sin(2*np.pi*1568*t))*np.exp(-t*6))
