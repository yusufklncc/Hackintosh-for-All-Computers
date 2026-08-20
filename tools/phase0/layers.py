"""Phase 0 / step 3: how many keys does each hierarchy level actually own?"""
import plistlib, json, sys, collections

IDENTITY = {'PlatformInfo.Generic.SystemSerialNumber','PlatformInfo.Generic.MLB',
            'PlatformInfo.Generic.SystemUUID','PlatformInfo.Generic.ROM'}

def flat(o, pre=''):
    out={}
    if isinstance(o,dict):
        for k,v in o.items(): out.update(flat(v,f'{pre}{k}.'))
    elif isinstance(o,list):
        for i,v in enumerate(o): out.update(flat(v,f'{pre}[{i}].'))
    else: out[pre[:-1]]=o
    return out

def show(v): return f'<{v.hex()[:10]}>' if isinstance(v,bytes) else str(v)

rows=json.load(open(sys.argv[1]))
canon=[r for r in rows if not (r['chipset'] or r['oem'] or r['variant'])]
F={r['path']:{k:show(v) for k,v in flat(plistlib.load(open(r['path'],'rb'))).items()
              if k not in IDENTITY and not k.endswith('.Comment')} for r in canon}

def common(paths):
    """keys whose value is identical across every path in the group"""
    if not paths: return {}
    first=F[paths[0]]
    return {k:v for k,v in first.items() if all(F[p].get(k)==v for p in paths[1:])}

allp=[r['path'] for r in canon]
base=common(allp)
print(f'{len(canon)} kanonik config\n')
print(f'  LEVEL 0  base (hepsinde ayni)                 {len(base):4d} key')

groups=collections.defaultdict(list)
for r in canon: groups[(r['platform'], r['vendor'])].append(r['path'])
tot_plat=tot_cpu=0
for (plat,vend),paths in sorted(groups.items(), key=lambda x:str(x[0])):
    c=common(paths)
    own={k:v for k,v in c.items() if base.get(k)!=v}
    tot_plat+=len(own)
    label=f'{plat}/{vend or "-"}'
    print(f'  LEVEL 1  {label:20s} {len(paths):3d} config          {len(own):4d} key (base ustune)')
    # per-cpu remainder
    sizes=[]
    for p in paths:
        eff={**base,**own}
        sizes.append(sum(1 for k,v in F[p].items() if eff.get(k)!=v))
    tot_cpu+=sum(sizes)
    print(f'           -> cpu profili basina ort. {sum(sizes)/len(sizes):5.1f} key  (min {min(sizes)}, max {max(sizes)})')
print(f'\n  toplam yazilacak: base {len(base)} + platform {tot_plat} + cpu {tot_cpu} = {len(base)+tot_plat+tot_cpu} key')
print(f'  bugun elle bakilan: {sum(len(F[p]) for p in allp)} key ({len(canon)} kanonik dosyada)')
print(f'  + overlay katmanlari (oem/chipset) ~60 key, 178 dosyanin tamamini turetir')
