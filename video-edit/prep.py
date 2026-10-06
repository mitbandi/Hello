import re,json
D=set(l.split()[0].split('(')[0] for l in open("my.dict",encoding="utf8",errors="ignore"))
toks=[];oov=set()
for li,line in enumerate(open("transcript.txt")):
    for t in line.split():
        if '=' in t: disp,sp=t.split('=',1); sp=sp.replace('_',' ')
        else: disp=t; sp=re.sub(r"[^a-z' ]","",t.lower().replace('-',' '))
        sw=sp.split()
        for w in sw:
            if w not in D: oov.add(w)
        toks.append({"d":disp,"sp":sw,"line":li})
print(oov); json.dump(toks,open("toks.json","w"))
