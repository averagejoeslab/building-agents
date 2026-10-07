import sys, time, torch
sys.path.insert(0, ".")
import model as M
from transformers import AutoModelForCausalLM
t=time.time(); ours=M.load_real().eval(); print("ours loaded", round(time.time()-t,1))
ref=AutoModelForCausalLM.from_pretrained(M.REAL, torch_dtype=torch.float32).eval()
ids=torch.tensor([M.encode("The capital of France is")])
with torch.no_grad():
    a=ours(ids); b=ref(ids).logits
print("max logit difference", (a-b).abs().max().item(), "same top token", a[0,-1].argmax().item()==b[0,-1].argmax().item())
t=time.time(); print(repr(M.generate(ours, "The capital of France is", most=20))); print("20 tokens", round(time.time()-t,1),"s")
print(repr(M.generate(ours, "# list every file in this folder, one per line\n$", most=20, stop=("\n",))))
