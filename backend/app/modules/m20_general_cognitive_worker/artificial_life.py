"""Bounded synchronous Conway B3/S23 grid automaton, no biological claim."""
def simulate(data):
    if not isinstance(data,dict):raise ValueError('data requires object')
    def integer(key,default,lo,hi):
        value=data.get(key,default)
        if type(value)is not int or not lo<=value<=hi:raise ValueError(f'{key} requires integer{lo}..{hi}')
        return value
    width=integer('width',None,3,128);height=integer('height',None,3,128);steps=integer('steps',4,1,1000)
    boundary=data.get('boundary','fixed')
    if boundary not in ('fixed','toroidal'):raise ValueError('boundary requires fixed or toroidal')
    cells=data.get('live_cells')
    if not isinstance(cells,list)or len(cells)>width*height:raise ValueError('live_cells require bounded coordinate list')
    live=set()
    for cell in cells:
        if not isinstance(cell,list)or len(cell)!=2 or any(type(v)is not int for v in cell):raise ValueError('cell requires exact integer[x,y]')
        x,y=cell
        if not 0<=x<width or not 0<=y<height:raise ValueError('cell outside grid')
        if (x,y)in live:raise ValueError('duplicate live cell')
        live.add((x,y))
    if (steps+1)*width*height>200000:raise ValueError('retained grid work product exceeds200000')
    def coords(values):return [list(v)for v in sorted(values)]
    history=[];seen={};first_repeat=None
    def snapshot(step,births,deaths):
        nonlocal first_repeat
        frozen=frozenset(live)
        if frozen in seen and first_repeat is None:first_repeat={'first_seen_step':seen[frozen],'repeated_at_step':step,'period':step-seen[frozen]}
        seen.setdefault(frozen,step)
        history.append({'step':step,'live_cells':coords(live),'births':coords(births),'deaths':coords(deaths),'population':len(live),'density':len(live)/(width*height)})
    snapshot(0,set(),set())
    for step in range(1,steps+1):
        future=set()
        for y in range(height):
            for x in range(width):
                neighbors=0
                for dy in (-1,0,1):
                    for dx in (-1,0,1):
                        if dx==dy==0:continue
                        a,b=x+dx,y+dy
                        if boundary=='toroidal':a%=width;b%=height
                        if (a,b)in live:neighbors+=1
                if neighbors==3 or ((x,y)in live and neighbors==2):future.add((x,y))
        births=future-live;deaths=live-future;live=future;snapshot(step,births,deaths)
    return {'algorithm':'conway_life_B3_S23','width':width,'height':height,'boundary':boundary,'history':history,'first_repeat':first_repeat,'cell_evaluations':width*height*steps,'life_scope':'Conway B3/S23 finite cellular automaton, not biological life or open-ended adaptive agents.'}
