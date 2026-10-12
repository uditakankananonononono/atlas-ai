import json, random, sys
def mk(name, desc, argname, queries, vals):
    return dict(name=name, description=desc, parameters=dict(type="object", properties={argname: dict(type="string", description=argname)}, required=[argname]))
A = [("get_weather","Get weather for a city","city","What's the weather in {v}?",["Lagos","Oslo","Lima","Pune","Cairo","Perth"]),
     ("set_timer","Set a timer","duration","Set a timer for {v}",["5 minutes","10 minutes","1 hour","30 seconds","2 hours","15 minutes"]),
     ("play_music","Play music by an artist","artist","Play some {v}",["Adele","Drake","Bjork","Coldplay","Shakira","Prince"])]
B = [("send_email","Send an email to a contact","recipient","Email {v} about lunch",["Maria","Jon","Priya","Chen","Omar","Sofia"]),
     ("add_todo","Add a todo item","item","Add {v} to my todo list",["buy milk","call dentist","pay rent","book flights","water plants","renew passport"]),
     ("search_web","Search the web","query","Search for {v}",["cheap flights","python tutorials","bike repair","tax forms","pizza dough","chess openings"])]
def rows(tools, vals_split, seed):
    rnd = random.Random(seed); out=[]
    specs=[mk(n,d,a,None,None) for n,d,a,_,_ in tools]
    for n,d,a,tpl,vs in tools:
        for v in vs[vals_split]:
            out.append(dict(query=tpl.format(v=v), tools=specs, answers=[dict(name=n, arguments={a:v})]))
    for q in ["Tell me a joke","What is the meaning of life?","Sing a song"]:
        out.append(dict(query=q, tools=specs, answers=[]))
    rnd.shuffle(out); return out
if __name__=="__main__":
    for name,tools in (("A",A),("B",B)):
        for split,sl in (("train",slice(0,4)),("test",slice(4,6))):
            with open(f"{name}_{split}.jsonl","w") as f:
                for r in rows(tools, sl, 1): f.write(json.dumps(r)+"\n")
