import json
toks=json.load(open("toks.json")); raw=json.load(open("rawseg.json"))
segs=[(a.split('(')[0],b,c) for a,b,c in raw if not a.startswith('<') and not a.startswith('[')]
i=0; END=135.0
for t in toks:
    n=len(t["sp"]); ss=segs[i:i+n]; i+=n
    if ss: t["s"]=ss[0][1]; t["e"]=ss[-1][2]
    else: t["s"]=prev+0.02; t["e"]=min(END,t["s"]+0.35)
    prev=t["e"]
json.dump(toks,open("aligned.json","w"),indent=0)
line=-1
for t in toks:
    if t["line"]!=line: line=t["line"]; print(f'\n{t["s"]:6.2f}',end=" ")
    print(t["d"],end=" ")
print(); print(toks[-1])
