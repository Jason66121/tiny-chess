import json,os,urllib.request as u
V=0,100,320,330,500,900,0
T='KKKKUUUUMMOQLLMPKKKOLJIKLMMGKKKKACEECGKKEKMNELNOEKNOELMNCGKLACEEGIIIIKKKIKLMILLMIKMMIMMMILKKGIIIKKKKLMMMJKKKJKKKJKKKJKKKJKKKKKKLECCAECCAECCAECCAGEECIGGGOOKKOQMK'
N=(-33,-31,-18,-14,14,18,31,33)
K=(-17,-16,-15,-1,1,15,16,17)
B=(-17,-15,15,17)
R=(-16,-1,1,16)
Q=B+R
O=(N,B,R,Q,K)
F='abcdefgh'
T=[ord(c)-75 for c in T]
def P(f):
 x=f.split();b=[0]*128;r=7;g=0
 for c in x[0]:
  if c=='/':r-=1;g=0
  elif c.isdigit():g+=int(c)
  else:b[r*16+g]=('PNBRQK'.index(c.upper())+1)*(1 if c.isupper() else -1);g+=1
 t=1 if x[1]=='w' else -1;c=0
 for k,v in zip('KQkq',(1,2,4,8)):
  if k in x[2]:c|=v
 e=-1
 if x[3]!='-':e=(8-int(x[3][1]))*16+F.index(x[3][0])
 return [b,t,c,e]
def A(b,s,y):
 d=-16*y
 for t in (s+d-1,s+d+1):
  if not t&0x88 and b[t]==y:return 1
 for d in N+K:
  t=s+d
  if not t&0x88 and b[t]==(y*2 if d in N else y*6):return 1
 for d in Q:
  t=s+d
  while not t&0x88:
   v=b[t]
   if v:
    if v==y*5 or v==(y*3 if d in B else y*4):return 1
    break
   t+=d
 return 0
def G(p,C=0):
 b,t=p[0],p[1];m=[]
 for s in range(128):
  v=b[s]
  if not v or (v>0)!=(t>0):continue
  a=abs(v)
  if a==1:
   d=16*t;g=7*(t>0);q=[]
   o=s+d
   if b[o]==0:
    q.append(o)
    if (s>>4)==6-5*(t>0) and b[s+2*d]==0:q.append(s+2*d)
   for f in (-1,1):
    w=s+d+f
    if not w&0x88 and ((b[w] and (b[w]>0)!=(t>0)) or w==p[3]):q.append(w)
   for w in q:
    if (w>>4)==g:
     for j in (5,4,3,2):m.append((s,w,j))
    else:m.append((s,w,0))
  else:
   for d in O[a-2]:
    w=s+d
    while not w&0x88:
     x=b[w]
     if not x:
      if not C:m.append((s,w,0))
     else:
      if (x>0)!=(t>0):m.append((s,w,0))
      break
     if a==2 or a==6:break
     w+=d
 if not C:
  d=112*(t<0)
  for k,e,to,at in ((1,(5,6),6,(4,5,6)),(2,(3,2,1),2,(4,3,2))):
   if p[2]&(k*(1+3*(d>0))) and all(b[s+d]==0 for s in e) and not any(A(b,s+d,-t) for s in at):m.append((4+d,to+d,0))
 return m
def M(p,m):
 b=p[0][:];f,t,pr=m;v=b[f];c=b[t];b[t]=v;b[f]=0;e=-1;X=p[2]
 if abs(v)==1 and t==p[3] and c==0:
  c=-p[1];b[t-16*p[1]]=0
 if abs(v)==1 and abs(t-f)==32:e=(f+t)//2
 if pr:b[t]=p[1]*pr
 if abs(v)==6 and abs(t-f)==2:
  for to,rs,rk in ((6,5,7),(2,3,0),(118,117,119),(114,115,112)):
   if t==to:b[rs],b[rk]=(4 if t<100 else -4),0
 for sq,ms in ((4,3),(116,12),(7,1),(0,2),(119,4),(112,8)):
  if f==sq or t==sq:X&=~ms
 return [b,-p[1],X,e]
def L(p):
 o=[]
 for m in G(p):
  n=M(p,m)
  if not A(n[0],n[0].index(6 if p[1]>0 else -6),-p[1]):o.append(m)
 return o
def E(p):
 b=p[0];s=0
 for j,v in enumerate(b):
  if not v:continue
  a=abs(v);i=(j>>4)*8+(j&7);k=i^56*(v>0);f=min(k&7,7-(k&7));o=(a-1-a//6)*32+(k>>3)*4+f
  u=V[a]+(T[o]*5 if a!=5 else 0);s+=u if v>0 else -u
 return s*p[1]+25
C=0;Z=6e4;BM=None;D={}
def S(p,d,a,b,y):
 global C,BM
 C+=1
 if C>Z:return E(p)
 k=hash((tuple(p[0]),p[1]))%99991;w=D.get(k)
 c=A(p[0],p[0].index(6 if p[1]>0 else -6),-p[1])
 if c and y:d+=1
 if d<=0 and not c:
  w=E(p)
  if w>=b:return b
  if w>a:a=w
 m=L(p) if c or d>0 else G(p,1)
 if not m:return -100000+y if c else a*(d<=0)
 o=sorted(m,key=lambda v:(v==w)*9999+V[abs(p[0][v[1]])]*10-V[abs(p[0][v[0]])]//10,reverse=True)
 bv=-10**9;u=o[0]
 for v in o:
  n=M(p,v)
  if d<=0 and A(n[0],n[0].index(6 if p[1]>0 else -6),-p[1]):continue
  x=-S(n,d-1,-b,-a,y+1)
  if C>Z:return bv if bv!=-10**9 else E(p)
  if x>bv:bv=x;u=v
  if x>a:
   a=x
   if y==0:BM=v
   if a>=b:break
 D[k]=u;return bv if bv!=-10**9 else a
def R(p,l):
 global C,BM
 C=0;BM=None;b=l[0];d=1
 while d<65 and C<=Z:
  S(p,d,-10**9,10**9,0)
  if C<=Z and BM is not None:b=BM
  d+=1
 return b
U=os.environ['MAKEFUN_ENV_URL']
def post(p,y):
 with u.urlopen(U+p,json.dumps(y).encode()) as w:return json.load(w)
while 1:
 g=post('/game',{})
 if g['status']=='done':break
 while g['status']=='your_move':
  p=P(g['fen']);l=[(F.index(i[0])+(int(i[1])-1)*16,F.index(i[2])+(int(i[3])-1)*16,'nbrq'.index(i[4])+2 if len(i)==5 else 0) for i in g['legal_moves']]
  v=R(p,l)
  g=post('/move',{'game':g['game'],'move':F[v[0]&7]+str((v[0]>>4)+1)+F[v[1]&7]+str((v[1]>>4)+1)+('nbrq'[v[2]-2] if v[2] else '')})
