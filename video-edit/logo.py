import numpy as np
from PIL import Image
im=np.asarray(Image.open("endcard.png").convert("RGB")).astype(np.float32)
H,W,_=im.shape
R=im[...,0]
yy,xx=np.mgrid[0:H,0:W]
inb=(xx>50)&((xx<532)|((yy>=650)&(xx<552)))&(yy>290)&(yy<740)&~((xx>440)&(yy<374))
alpha=np.clip((150-R)/70,0,1)*inb
# fit background quadratic
bgm=(alpha==0)
def feats(x,y):
    x=x/W;y=y/H
    return np.stack([np.ones_like(x),x,y,x*x,y*y,x*y,x**3,y**3,x*x*y,x*y*y],-1)
F=feats(xx[bgm].astype(float),yy[bgm].astype(float))
bg=np.zeros_like(im)
Fa=feats(xx.astype(float),yy.astype(float))
for c in range(3):
    co,*_=np.linalg.lstsq(F[::7],im[...,c][bgm][::7],rcond=None)
    bg[...,c]=Fa@co
print("bg err",np.abs(bg-im)[bgm].mean())
Image.fromarray(np.clip(bg,0,255).astype(np.uint8)).save("assets/end_bg.png")
# pieces
parts={"text":(yy>=650),"wingL":(yy<398)&(xx>165)&(xx<302),"wingR":(yy<398)&(xx>=302)&(xx<445)}
parts["armL"]=(~parts["text"])&(~parts["wingL"])&(~parts["wingR"])&(xx<302)
parts["armR"]=(~parts["text"])&(~parts["wingL"])&(~parts["wingR"])&(xx>=302)
for k,m in parts.items():
    a=(alpha*m*255).astype(np.uint8)
    rgba=np.dstack([im.astype(np.uint8),a])
    Image.fromarray(rgba).save(f"assets/logo_{k}.png")
full=np.dstack([im.astype(np.uint8),(alpha*255).astype(np.uint8)])
Image.fromarray(full).save("assets/logo_full.png")
# preview
prev=Image.new("RGB",(W*2,H),(255,0,255)); 
prev.paste(Image.fromarray(np.clip(bg,0,255).astype(np.uint8)),(0,0))
cols=[(255,0,0),(0,0,255),(255,200,0),(0,200,200),(120,0,120)]
canvas=Image.new("RGBA",(W,H),(255,255,255,255))
for (k,m),c in zip(parts.items(),cols):
    lay=Image.new("RGBA",(W,H),c+(0,)); a=Image.fromarray((alpha*m*255).astype(np.uint8)); lay.putalpha(a); canvas.alpha_composite(lay)
prev.paste(canvas.convert("RGB"),(W,0)); prev.save("assets/preview_logo.png")
