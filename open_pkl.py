from pathlib import Path
import pickle
import matplotlib.pyplot as plt

pkl_path = Path("seq.pkl").resolve()
out_path = pkl_path.with_suffix(".png")  # seq.png next to seq.pkl

with pkl_path.open("rb") as f:
    seq = pickle.load(f)

plt.figure()
plt.plot(seq)                 # if seq is a list/1D array
plt.xlabel("Index")
plt.ylabel("Value")
plt.title("Sequence")
plt.tight_layout()
plt.savefig(out_path, dpi=200)
plt.close()

print("Saved plot to:", out_path)
