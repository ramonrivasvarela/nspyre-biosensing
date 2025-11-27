from pathlib import Path
import pickle
import matplotlib.pyplot as plt
from pulsestreamer import Sequence

pkl_path = Path("nspyre-biosensing/seq.pkl").resolve()
out_path = pkl_path.with_suffix(".png")  # seq.png next to seq.pkl

with pkl_path.open("rb") as f:
    seq = pickle.load(f)
print(seq)
seq.plot()
# plt.figure()
# plt.show()

# print('len(data):', len(data))
# plt.figure()
# plt.plot(data)                 # if seq is a list/1D array
# plt.xlabel("Index")
# plt.ylabel("Value")
# plt.title("Sequence")
# plt.tight_layout()
# plt.savefig(out_path, dpi=200)
# plt.close()

# print("Saved plot to:", out_path)
