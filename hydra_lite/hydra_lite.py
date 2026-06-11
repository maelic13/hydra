#!/usr/bin/env python3
import sys,time

FILES="abcdefgh"; RANKS="12345678"; START="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
VAL={"P":100,"N":320,"B":330,"R":500,"Q":900,"K":0}
PST=[
(0,0,0,0,0,0,0,0,5,10,10,-20,-20,10,10,5,5,-5,-10,0,0,-10,-5,5,0,0,0,20,20,0,0,0,5,5,10,25,25,10,5,5,10,10,20,30,30,20,10,10,50,50,50,50,50,50,50,50,0,0,0,0,0,0,0,0),
(-50,-40,-30,-30,-30,-30,-40,-50,-40,-20,0,5,5,0,-20,-40,-30,5,10,15,15,10,5,-30,-30,0,15,20,20,15,0,-30,-30,5,15,20,20,15,5,-30,-30,0,10,15,15,10,0,-30,-40,-20,0,0,0,0,-20,-40,-50,-40,-30,-30,-30,-30,-40,-50),
(-20,-10,-10,-10,-10,-10,-10,-20,-10,5,0,0,0,0,5,-10,-10,10,10,10,10,10,10,-10,-10,0,10,10,10,10,0,-10,-10,5,5,10,10,5,5,-10,-10,0,5,10,10,5,0,-10,-10,0,0,0,0,0,0,-10,-20,-10,-10,-10,-10,-10,-10,-20),
(0,0,0,5,5,0,0,0,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,5,10,10,10,10,10,10,5,0,0,0,0,0,0,0,0),
(-20,-10,-10,-5,-5,-10,-10,-20,-10,0,5,0,0,0,0,-10,-10,5,5,5,5,5,0,-10,0,0,5,5,5,5,0,-5,-5,0,5,5,5,5,0,-5,-10,0,5,5,5,5,0,-10,-10,0,0,0,0,0,0,-10,-20,-10,-10,-5,-5,-10,-10,-20)]
KMG=(20,30,10,0,0,10,30,20,20,20,0,0,0,0,20,20,-10,-20,-20,-20,-20,-20,-20,-10,-20,-30,-30,-40,-40,-30,-30,-20,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30)
KEG=(-50,-30,-30,-30,-30,-30,-30,-50,-30,-30,0,0,0,0,-30,-30,-30,-10,20,30,30,20,-10,-30,-30,-10,30,40,40,30,-10,-30,-30,-10,30,40,40,30,-10,-30,-30,-10,20,30,30,20,-10,-30,-30,-20,-10,0,0,-10,-20,-30,-50,-40,-30,-20,-20,-30,-40,-50)
PI="PNBRQK"
def _ps(pc,sq):
    """White-perspective material+PST for piece pc at square sq (king uses KMG always)."""
    X=pc.upper();w=pc.isupper();si=sq if w else sq^56
    v=VAL.get(X,0)+(KMG[si] if X=="K" else PST[PI.index(X)][si])
    return v if w else -v
NDIR=[17,15,10,6,-17,-15,-10,-6]
BDIR=[9,7,-9,-7]; RDIR=[8,-8,1,-1]; QDIR=BDIR+RDIR
KDIR=[8,-8,1,-1,9,7,-9,-7]
MATE=30000
ZMASK=(1<<64)-1
# Tunable search/eval constants — overridden by ca_uci_persistent.py for SPSA.
# The submitted file ships with these values hard-coded.
SEARCH_TIME=4.3; BOOK_PLY=8; TT_MAX_ENTRIES=25000; ASPIRATION_WINDOW=45
RFP_MARGIN=90; FP_MARGIN=160; NULL_MIN_DEPTH=3; NULL_REDUCTION=3
LMR_MIN_DEPTH=3; LMR_DEPTH=2; QDELTA_MARGIN=220
def zp(pc,i): return ((ord(pc)*6364136223846793005)^((i+1)*1442695040888963407))&ZMASK

class P:
    __slots__=("b","w","c","e","h","f","k","z","score")
    def __init__(self,b,w,c,e,h,f):
        self.b=b; self.w=w; self.c=c; self.e=e; self.h=h; self.f=f
        self.k=[b.index("K") if "K" in b else -1,b.index("k") if "k" in b else -1]
        z=0; sc=0
        for i,x in enumerate(b):
            if x!=".": z^=zp(x,i); sc+=_ps(x,i)
        self.z=z; self.score=sc

def sq(s): return FILES.index(s[0])+8*RANKS.index(s[1])
def sn(i): return FILES[i&7]+RANKS[i>>3]
def col(p): return p.isupper()
def mine(p,w): return p!="." and p.isupper()==w
def enemy(p,w): return p!="." and p.isupper()!=w
def ok(i): return 0<=i<64
def same(a,b): return abs((a&7)-(b&7))<=2
def key(p): return (p.z,p.w,p.c,p.e)

def fen(s):
    a=s.split(); b=["."]*64; r=7; f=0
    for ch in a[0]:
        if ch=="/": r-=1; f=0
        elif ch.isdigit(): f+=int(ch)
        else: b[f+8*r]=ch; f+=1
    return P(b,a[1]=="w",a[2] if a[2]!="-" else "",-1 if a[3]=="-" else sq(a[3]),int(a[4]),int(a[5]))

def fen3(p):
    return ("".join(p.b),p.w,p.c)

def attacked(p,s,byw):
    b=p.b; f=s&7
    for d in ((-7,-9) if byw else (7,9)):
        t=s+d
        if ok(t) and abs((t&7)-f)==1 and b[t]==("P" if byw else "p"): return True
    for d in NDIR:
        t=s+d
        if ok(t) and same(s,t) and b[t]==("N" if byw else "n"): return True
    for d in BDIR:
        t=s+d
        while ok(t) and abs((t&7)-((t-d)&7))==1:
            q=b[t]
            if q!=".":
                if q==("B" if byw else "b") or q==("Q" if byw else "q"): return True
                break
            t+=d
    for d in RDIR:
        t=s+d
        while ok(t) and (d in (8,-8) or abs((t&7)-((t-d)&7))==1):
            q=b[t]
            if q!=".":
                if q==("R" if byw else "r") or q==("Q" if byw else "q"): return True
                break
            t+=d
    for d in KDIR:
        t=s+d
        if ok(t) and abs((t&7)-f)<=1 and b[t]==("K" if byw else "k"): return True
    return False

def incheck(p,w): return p.k[0 if w else 1]>=0 and attacked(p,p.k[0 if w else 1],not w)

def add(ms,fr,to,pr="",fl=0):
    ms.append((fr,to,pr,fl))

def pseudo(p,caps=False):
    b=p.b; w=p.w; ms=[]
    for i,x in enumerate(b):
        if not mine(x,w): continue
        X=x.upper(); r=i>>3; f=i&7
        if X=="P":
            d=8 if w else -8; st=1 if w else 6; prom=6 if w else 1
            one=i+d
            if ok(one) and b[one]==".":
                if r==prom:
                    for pr in ("q" if caps else "qrbn"): add(ms,i,one,pr)
                elif not caps:
                    add(ms,i,one)
                    two=i+2*d
                    if r==st and b[two]==".": add(ms,i,two)
            for cd in (d+1,d-1):
                t=i+cd
                if ok(t) and abs((t&7)-f)==1 and (enemy(b[t],w) or t==p.e):
                    fl=1 if t==p.e and b[t]=="." else 0
                    if r==prom:
                        for pr in "qrbn": add(ms,i,t,pr,fl)
                    else: add(ms,i,t,"",fl)
        elif X=="N":
            for d in NDIR:
                t=i+d
                if ok(t) and same(i,t) and not mine(b[t],w) and (not caps or b[t]!="."): add(ms,i,t)
        elif X in "BRQ":
            for d in (BDIR if X=="B" else RDIR if X=="R" else QDIR):
                t=i+d
                while ok(t) and (d in (8,-8) or abs((t&7)-((t-d)&7))==1):
                    if mine(b[t],w): break
                    if b[t]!=".":
                        add(ms,i,t); break
                    if not caps: add(ms,i,t)
                    t+=d
        elif X=="K":
            for d in KDIR:
                t=i+d
                if ok(t) and abs((t&7)-f)<=1 and not mine(b[t],w) and (not caps or b[t]!="."): add(ms,i,t)
            if not caps and not incheck(p,w):
                if w and "K" in p.c and b[5]==b[6]=="." and not attacked(p,5,False) and not attacked(p,6,False): add(ms,4,6,"",2)
                if w and "Q" in p.c and b[3]==b[2]==b[1]=="." and not attacked(p,3,False) and not attacked(p,2,False): add(ms,4,2,"",2)
                if (not w) and "k" in p.c and b[61]==b[62]=="." and not attacked(p,61,True) and not attacked(p,62,True): add(ms,60,62,"",2)
                if (not w) and "q" in p.c and b[59]==b[58]==b[57]=="." and not attacked(p,59,True) and not attacked(p,58,True): add(ms,60,58,"",2)
    return ms

def make(p,m):
    fr,to,pr,fl=m; b=p.b; pc=b[fr]; cap=b[to]; oc,oe,oh,ow,oz=p.c,p.e,p.h,p.w,p.z; okg=p.k[:]
    oscore=p.score; epcap=-1; rook=None
    z=oz^zp(pc,fr)
    if cap!=".": z^=zp(cap,to)
    b[fr]="."; p.e=-1
    if fl==1:
        epcap=to+(-8 if pc.isupper() else 8); cap=b[epcap]; b[epcap]="."; z^=zp(cap,epcap)
    np=pr.upper() if pr and pc.isupper() else pr if pr else pc
    # Incremental score delta (cap/epcap/np all determined; board already cleared at fr/epcap)
    sc=_ps(np,to)-_ps(pc,fr)
    if epcap>=0: sc-=_ps(cap,epcap)
    elif cap!=".": sc-=_ps(cap,to)
    b[to]=np; z^=zp(np,to)
    if pc=="K": p.k[0]=to; p.c=p.c.replace("K","").replace("Q","")
    elif pc=="k": p.k[1]=to; p.c=p.c.replace("k","").replace("q","")
    if fl==2:
        if to==6: rook=(7,5); b[5]="R"; b[7]="."; z^=zp("R",7)^zp("R",5); sc+=_ps("R",5)-_ps("R",7)
        elif to==2: rook=(0,3); b[3]="R"; b[0]="."; z^=zp("R",0)^zp("R",3); sc+=_ps("R",3)-_ps("R",0)
        elif to==62: rook=(63,61); b[61]="r"; b[63]="."; z^=zp("r",63)^zp("r",61); sc+=_ps("r",61)-_ps("r",63)
        else: rook=(56,59); b[59]="r"; b[56]="."; z^=zp("r",56)^zp("r",59); sc+=_ps("r",59)-_ps("r",56)
    p.score=oscore+sc
    if fr==0 or to==0: p.c=p.c.replace("Q","")
    if fr==7 or to==7: p.c=p.c.replace("K","")
    if fr==56 or to==56: p.c=p.c.replace("q","")
    if fr==63 or to==63: p.c=p.c.replace("k","")
    if pc.upper()=="P" and abs(to-fr)==16: p.e=(fr+to)//2
    p.h=0 if pc.upper()=="P" or cap!="." else p.h+1
    if not p.w: p.f+=1
    p.w=not p.w; p.z=z
    return (fr,to,pc,cap,oc,oe,oh,ow,okg,epcap,rook,oz,oscore)

def unmake(p,u):
    fr,to,pc,cap,oc,oe,oh,ow,okg,epcap,rook,oz,oscore=u; b=p.b
    p.c=oc; p.e=oe; p.h=oh; p.w=ow; p.k=okg; p.z=oz; p.score=oscore
    b[fr]=pc; b[to]=cap
    if epcap>=0:
        b[epcap]=cap; b[to]="."
    if rook:
        rf,rt=rook; b[rf]=b[rt]; b[rt]="."
    if not p.w: p.f-=1

def legal(p,caps=False):
    w=p.w; out=[]
    for m in pseudo(p,caps):
        u=make(p,m)
        if not incheck(p,w): out.append(m)
        unmake(p,u)
    return out

def uci(m):
    s=sn(m[0])+sn(m[1])
    return s+(m[2] if m[2] else "")

def parseuci(p,s):
    for m in legal(p):
        if uci(m)==s: return m
    return None

def center(i):
    return 14-abs((i&7)*2-7)-abs((i>>3)*2-7)

def mob(p,i,X,w):
    b=p.b; n=0
    if X=="N":
        for d in NDIR:
            t=i+d
            if ok(t) and same(i,t) and not mine(b[t],w): n+=1
    elif X in "BRQ":
        for d in (BDIR if X=="B" else RDIR if X=="R" else QDIR):
            t=i+d
            while ok(t) and (d in (8,-8) or abs((t&7)-((t-d)&7))==1):
                if mine(b[t],w): break
                n+=1
                if b[t]!=".": break
                t+=d
    return n

def evalp(p):
    phase=sum(VAL[x.upper()] for x in p.b if x!="." and x.upper()!="K")
    sc=0; bishops=[0,0]; pawns=[0]*16
    for i,x in enumerate(p.b):
        if x=="." : continue
        w=x.isupper(); X=x.upper(); r=i>>3; rr=r if w else 7-r; c=center(i); v=VAL[X]
        if X=="P": pawns[(0 if w else 8)+(i&7)]+=1
    for i,x in enumerate(p.b):
        if x=="." : continue
        w=x.isupper(); X=x.upper(); r=i>>3; rr=r if w else 7-r; f=i&7; c=center(i); si=i if w else i^56; v=VAL[X]
        v+=(KMG[si] if phase>2200 else KEG[si]) if X=="K" else PST[PI.index(X)][si]
        if X=="P":
            side=0 if w else 8; oside=8-side
            iso=not ((f and pawns[side+f-1]) or (f<7 and pawns[side+f+1]))
            dbl=pawns[side+f]>1
            passed=True
            for ff in (f-1,f,f+1):
                if 0<=ff<8:
                    for j,y in enumerate(p.b):
                        if (j&7)==ff and y==("p" if w else "P") and ((j>>3)>r if w else (j>>3)<r): passed=False
            v+=rr*10+c+(rr*rr*3 if passed else 0)-(14 if iso else 0)-(12 if dbl else 0)
            if (f and p.b[i-1]==x) or (f<7 and p.b[i+1]==x): v+=8
        elif X=="N":
            v+=c*10+mob(p,i,X,w)*4
            if rr>=3:
                prot=(i-7 if w else i+7, i-9 if w else i+9)
                if any(ok(t) and abs((t&7)-f)==1 and p.b[t]==("P" if w else "p") for t in prot): v+=18
        elif X=="B": v+=c*5+mob(p,i,X,w)*4; bishops[0 if w else 1]+=1
        elif X=="R":
            own=pawns[(0 if w else 8)+f]; opp=pawns[(8 if w else 0)+f]
            v+=rr*2+mob(p,i,X,w)*2+(18 if not own and not opp else 9 if not own else 0)
        elif X=="Q": v+=c*2+mob(p,i,X,w)-(18 if phase>5000 and rr>1 else 0)
        elif X=="K":
            shield=0
            for ff in (f-1,f,f+1):
                t=ff+8*(1 if w else 6)
                if 0<=ff<8 and ok(t) and p.b[t]==("P" if w else "p"): shield+=1
            v+=(c*7 if phase<1800 else -c*7)+shield*10
        sc+=v if w else -v
    if bishops[0]>=2: sc+=35
    if bishops[1]>=2: sc-=35
    return sc if p.w else -sc

def quiet(p,m): return p.b[m[1]]=="." and not m[2] and m[3]!=1

def mscore(p,m,tt=None,ks=(),hist={}):
    if tt==m: return 10000000
    fr,to,pr,fl=m; a=p.b[fr].upper(); c=p.b[to].upper()
    if fl==1: c="P"
    s=(VAL.get(c,0)*10-VAL.get(a,0)) if c!="." else 0
    if c!="." and VAL.get(c,0)+80<VAL.get(a,0) and attacked(p,to,not p.w): s-=550
    if pr: s+=VAL[pr.upper()]+800
    if m in ks: s+=700
    s+=hist.get((fr,to,pr),0)
    if a=="P" and (to>>3 in (0,7)): s+=900
    if a in "NB" and fr in (1,2,5,6,57,58,61,62): s+=18
    s+=center(to)-center(fr)
    return s

def order(p,ms,pv=None,ks=(),hist={}):
    if pv in ms: ms.remove(pv); return [pv]+sorted(ms,key=lambda m:mscore(p,m,None,ks,hist),reverse=True)
    return sorted(ms,key=lambda m:mscore(p,m,pv,ks,hist),reverse=True)

class TMO(Exception): pass

def search(p,rep,sec=4.0):
    end=time.perf_counter()+sec; nodes=0; best=None; pv=None; TT={}; hist={}; killers=[[None,None] for _ in range(64)]
    def chk():
        nonlocal nodes
        nodes+=1
        if nodes&255==0 and time.perf_counter()>end: raise TMO
    def nmove():
        u=(p.w,p.e,p.h); p.w=not p.w; p.e=-1; p.h+=1; return u
    def unnull(u):
        p.w,p.e,p.h=u
    def store(h,d,v,fl,bm):
        if len(TT)>TT_MAX_ENTRIES: TT.clear()
        TT[h]=(d,v,fl,bm)
    def q(a,b):
        chk()
        h=key(p)
        if rep.get(h,0)>=3 or p.h>=100: return 0
        stand=evalp(p)
        if stand>=b: return b
        if stand>a: a=stand
        ms=pseudo(p,True)
        for m in order(p,ms,None,(),hist):
            if stand+VAL.get(p.b[m[1]].upper(),0)+QDELTA_MARGIN<a and not m[2]: continue
            u=make(p,m)
            if incheck(p,not p.w): unmake(p,u); continue
            k=key(p); rep[k]=rep.get(k,0)+1
            try:
                v=-q(-b,-a)
            finally:
                rep[k]-=1; unmake(p,u)
            if v>=b: return b
            if v>a: a=v
        return a
    def ab(d,a,b,ply):
        chk()
        h=key(p); a0=a
        if rep.get(h,0)>=3 or p.h>=100: return 0
        inc=incheck(p,p.w)
        if d<=0 and not inc: return q(a,b)
        e=TT.get(h)
        if e and e[0]>=d:
            _,v,fl,bm=e
            if fl==0: return v
            if fl==1 and v<=a: return v
            if fl==2 and v>=b: return v
        static=evalp(p)
        if d<=2 and not inc and static-RFP_MARGIN*d>=b: return static
        if d>=NULL_MIN_DEPTH and not inc and static>=b and abs(static)<9000:
            u=nmove()
            try: v=-ab(d-NULL_REDUCTION,-b,-b+1,ply+1)
            finally: unnull(u)
            if v>=b: return b
        ms=pseudo(p)
        if inc: d+=1
        bm=e[3] if e else None; bestm=None; cnt=0
        for m in order(p,ms,bm,killers[ply],hist):
            if cnt>0 and d<=2 and not inc and quiet(p,m) and static+FP_MARGIN*d<=a: continue
            u=make(p,m)
            if incheck(p,not p.w): unmake(p,u); continue
            cnt+=1
            k=key(p); rep[k]=rep.get(k,0)+1
            try:
                if cnt>1 and d>=LMR_MIN_DEPTH and quiet(p,m) and not inc:
                    v=-ab(d-LMR_DEPTH,-a-1,-a,ply+1)
                    if v>a: v=-ab(d-1,-a-1,-a,ply+1)
                elif cnt>1:
                    v=-ab(d-1,-a-1,-a,ply+1)
                else:
                    v=-ab(d-1,-b,-a,ply+1)
                if cnt>1 and v>a and v<b: v=-ab(d-1,-b,-a,ply+1)
            finally:
                rep[k]-=1; unmake(p,u)
            if v>a: a=v; bestm=m
            if v>=b:
                if quiet(p,m):
                    if killers[ply][0]!=m: killers[ply]=[m,killers[ply][0]]
                    hk=(m[0],m[1],m[2]); hist[hk]=hist.get(hk,0)+d*d
                store(h,d,b,2,m); return b
        if cnt==0: return -MATE+ply if inc else 0
        store(h,d,a,0 if a>a0 else 1,bestm)
        return a
    try:
        window=ASPIRATION_WINDOW
        for d in range(1,64):
            alpha=-MATE if d<4 else score-window if 'score' in locals() else -MATE
            beta=MATE if d<4 else score+window if 'score' in locals() else MATE
            while True:
                a=alpha; bm=None
                for m in order(p,legal(p),pv,(),hist):
                    u=make(p,m); k=key(p); rep[k]=rep.get(k,0)+1
                    try:
                        v=-ab(d-1,-beta,-a,1)
                    finally:
                        rep[k]-=1; unmake(p,u)
                    if v>a: a=v; bm=m
                if a<=alpha and alpha>-MATE: alpha-=window*2; window*=2; continue
                if a>=beta and beta<MATE: beta+=window*2; window*=2; continue
                break
            score=a
            if bm: best=bm; pv=bm
            if time.perf_counter()>end: break
    except TMO:
        pass
    return best or (legal(p)[0] if legal(p) else None)

def build(line):
    a=line.strip().split(); p=fen(" ".join(a[:6])); rep={key(p):1}
    if "moves" not in a[6:]: return p,rep,[]
    hist=a[a.index("moves")+1:]; r=fen(START); rr={key(r):1}; okh=True
    for s in hist:
        m=parseuci(r,s)
        if m is None: okh=False; break
        make(r,m); rr[key(r)]=rr.get(key(r),0)+1
    if okh:
        # Replay succeeded: always use the replayed position.
        # If the supplied FEN matches the replayed position (ChessAgents native
        # protocol), apply its e/h/f values; if it doesn't match (UCI adapter
        # sends START_FEN + full history), the replayed position's own e/h/f
        # values (maintained by make()) are already correct.
        if fen3(r)==fen3(p): r.e=p.e; r.h=p.h; r.f=p.f
        return r,rr,hist
    return p,rep,hist

def book(p,hist):
    t=tuple(hist[:12])
    B={
    ():("g1f3","e2e4","d2d4"),
    ("e2e4",):("c7c5","e7e5"),
    ("d2d4",):("g8f6","d7d5"),
    ("g1f3",):("d7d5","g8f6"),
    ("c2c4",):("e7e5","g8f6"),
    ("e2e4","e7e5"):("g1f3","f1b5"),
    ("e2e4","e7e5","g1f3"):("b8c6","g8f6"),
    ("e2e4","e7e5","g1f3","b8c6"):("f1b5","f1c4"),
    ("e2e4","e7e5","g1f3","b8c6","f1b5"):("a7a6","g8f6"),
    ("e2e4","e7e5","g1f3","b8c6","f1c4"):("g8f6","f8c5"),
    ("e2e4","e7e5","g1f3","g8f6"):("f3e5","b1c3"),
    ("e2e4","c7c5"):("g1f3","d2d4"),
    ("e2e4","c7c5","g1f3"):("d7d6","b8c6"),
    ("e2e4","c7c5","g1f3","d7d6"):("d2d4","f1b5"),
    ("e2e4","c7c5","g1f3","b8c6"):("d2d4","f1b5"),
    ("e2e4","c7c5","g1f3","e7e6"):("d2d4","b1c3"),
    ("e2e4","e7e6"):("d2d4","b1c3"),
    ("e2e4","e7e6","d2d4"):("d7d5","g8f6"),
    ("e2e4","e7e6","d2d4","d7d5"):("b1c3","e4e5"),
    ("e2e4","c7c6"):("d2d4","b1c3"),
    ("e2e4","c7c6","d2d4"):("d7d5","g8f6"),
    ("e2e4","c7c6","d2d4","d7d5"):("b1c3","e4e5"),
    ("e2e4","g8f6"):("e4e5","b1c3"),
    ("e2e4","d7d5"):("e4d5","b1c3"),
    ("d2d4","d7d5"):("c2c4","g1f3"),
    ("d2d4","d7d5","c2c4"):("e7e6","c7c6"),
    ("d2d4","d7d5","c2c4","e7e6"):("b1c3","g1f3"),
    ("d2d4","d7d5","c2c4","c7c6"):("g1f3","b1c3"),
    ("d2d4","g8f6"):("c2c4","g1f3"),
    ("d2d4","g8f6","c2c4"):("e7e6","g7g6"),
    ("d2d4","g8f6","c2c4","e7e6"):("g1f3","b1c3"),
    ("d2d4","g8f6","c2c4","g7g6"):("b1c3","g1f3"),
    ("d2d4","f7f5"):("g2g3","c2c4"),
    ("d2d4","c7c5"):("d4d5","c2c4"),
    ("g1f3","d7d5"):("d2d4","c2c4"),
    ("g1f3","g8f6"):("c2c4","d2d4"),
    ("g1f3","c7c5"):("c2c4","d2d4"),
    ("c2c4","e7e5"):("b1c3","g1f3"),
    ("c2c4","g8f6"):("b1c3","g1f3"),
    ("c2c4","c7c5"):("g1f3","b1c3"),
    }
    for s in B.get(t,()):
        m=parseuci(p,s)
        if m: return m
    L="""
g1f3 d7d5 d2d4 g8f6 c2c4 e7e6 b1c3 f8e7 c1g5 e8g8 e2e3 h7h6
g1f3 d7d5 d2d4 g8f6 c2c4 c7c6 b1c3 e7e6 e2e3 b8d7 f1d3 d5c4
g1f3 g8f6 c2c4 g7g6 b1c3 f8g7 d2d4 e8g8 e2e4 d7d6 f1e2 e7e5
g1f3 g8f6 c2c4 e7e6 b1c3 f8b4 d1c2 e8g8 a2a3 b4c3 c2c3 d7d5
g1f3 c7c5 c2c4 g8f6 b1c3 d7d5 c4d5 f6d5 e2e3 b8c6 f1b5
e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5
e2e4 e7e5 g1f3 b8c6 f1b5 g8f6 e1g1 f6e4 d2d4 e4d6 b5c6 d7c6
e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6 d2d4 e5d4 c3d4 c5b4
e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4 g8f6 b1c3 f8b4 d4c6 b7c6
e2e4 e7e5 g1f3 g8f6 f3e5 d7d6 e5f3 f6e4 d2d4 d6d5 f1d3 f8e7
e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5
e2e4 c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g8f6 b1c3 d7d6 c1g5 e7e6
e2e4 c7c5 g1f3 e7e6 d2d4 c5d4 f3d4 a7a6 f1d3 g8f6 e1g1 d7d6
e2e4 c7c5 g1f3 g7g6 d2d4 c5d4 f3d4 g8f6 b1c3 d7d6 c1e3 f8g7
e2e4 e7e6 d2d4 d7d5 b1c3 g8f6 c1g5 f8e7 e4e5 f6d7 g5e7 d8e7
e2e4 e7e6 d2d4 d7d5 e4e5 c7c5 c2c3 b8c6 g1f3 d8b6 f1d3 c5d4
e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 h2h4 h7h6
e2e4 c7c6 d2d4 d7d5 e4e5 c8f5 g1f3 e7e6 f1e2 c6c5 e1g1 b8c6
e2e4 g8f6 e4e5 f6d5 d2d4 d7d6 g1f3 d6e5 f3e5 c7c6 f1e2
e2e4 d7d5 e4d5 d8d5 b1c3 d5a5 d2d4 g8f6 g1f3 c7c6 f1c4 c8f5
e2e4 g7g6 d2d4 f8g7 b1c3 d7d6 f1e3 g8f6 d1d2 e8g8 e1c1
d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7 e2e3 e8g8 g1f3 h7h6
d2d4 d7d5 c2c4 e7e6 b1c3 c7c5 c4d5 e6d5 g1f3 b8c6 g2g3 g8f6
d2d4 d7d5 c2c4 c7c6 g1f3 g8f6 b1c3 d5c4 a2a4 c8f5 e2e3 e7e6
d2d4 d7d5 c2c4 d5c4 e2e3 g8f6 f1c4 e7e6 g1f3 c7c5 e1g1 a7a6
d2d4 g8f6 c2c4 e7e6 b1c3 f8b4 e2e3 e8g8 f1d3 d7d5 g1f3 c7c5
d2d4 g8f6 c2c4 e7e6 g1f3 b7b6 g2g3 c8a6 b2b3 f8b4 c1d2
d2d4 g8f6 c2c4 g7g6 b1c3 d7d5 c4d5 f6d5 e2e4 d5c3 b2c3 f8g7
d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 g1f3 e8g8 f1e2 e7e5
d2d4 f7f5 g2g3 g8f6 f1g2 e7e6 g1f3 f8e7 e1g1 e8g8 c2c4 d7d6
d2d4 c7c5 d4d5 g8f6 b1c3 d7d6 e2e4 g7g6 f2f4 f8g7 f1b5 c8d7
c2c4 e7e5 b1c3 g8f6 g1f3 b8c6 g2g3 f8b4 f1g2 e8g8 e1g1
c2c4 g8f6 b1c3 e7e5 g1f3 b8c6 g2g3 f8b4 f1g2 e8g8 e1g1
c2c4 c7c5 g1f3 g8f6 b1c3 b8c6 g2g3 d7d5 c4d5 f6d5 f1g2
"""
    for line in L.splitlines():
        s=line.split()
        if len(t)<len(s) and tuple(s[:len(t)])==t:
            m=parseuci(p,s[len(t)])
            if m: return m
    return None

def main():
    try:
        p,rep,hist=build(sys.stdin.readline())
        m=book(p,hist) if len(hist)<BOOK_PLY else None
        if not m: m=search(p,rep,SEARCH_TIME)
        print(uci(m) if m else "0000")
    except Exception:
        print("0000")
if __name__=="__main__": main()
