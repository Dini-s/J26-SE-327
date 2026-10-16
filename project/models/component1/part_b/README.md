# Part B model files (`c1-req`)

| File | What it is |
|---|---|
| `c1_merged_q4_k_m.gguf` | the merged, Q4_K_M quantised fine-tuned model (8B), loaded by Ollama |
| `Modelfile` | the committed, machine-independent Ollama definition (`temperature 0`, `num_predict 600`, stop token). Do not tune it for one laptop |
| `Modelfile.local` | **your own, git-ignored** copy with machine-specific tuning (see below) |

Create or update the Ollama model from the folder that holds the files:

```powershell
cd project\models\component1\part_b
ollama create c1-req -f Modelfile          # the committed defaults
ollama create c1-req -f Modelfile.local    # or your local tuning (same model name, so the API needs no change)
```

## Speed on a small GPU (RTX 3050, 4 GB)

Measured on this laptop with the same input, greedy decoding, `ollama run --verbose`:

| Settings | tokens/s | CPU / GPU split | Notes |
|---|---|---|---|
| default | 5.2 | 58% / 42% | model load 13.6 s |
| `num_ctx 2048` + `num_gpu 22` | 8.81 | 35% / 65% | VRAM 3605 MiB |
| `num_ctx 2048` + `num_gpu 24` | 10.95 | (more layers on the GPU) | VRAM 3777 of 4096 MiB, load 10.0 s |
| `num_thread` 4, 8, 12 | 9.78, 10.01, 10.61 | | no better than the default, **not used** |

A reply of about 125 tokens therefore takes about 25 s with the defaults and about 12 s tuned. In the API workflow the mean was 26 s per requirement with default settings in one live run.
A check made while preparing the generation policy, against the tuned model through the API's `/api/chat`: 10.65 tokens/s, `ollama ps` (`/api/ps`) 70% GPU / 30% CPU, context 2048.

`num_gpu` is the number of layers kept on the GPU. It depends on the VRAM of the machine, so these values are tuning knobs for **this** laptop, not defaults. `Modelfile.local` for this machine:

```text
FROM ./c1_merged_q4_k_m.gguf
PARAMETER stop "<|eot_id|>"
PARAMETER temperature 0
PARAMETER num_predict 600
PARAMETER num_ctx 2048
PARAMETER num_gpu 24
```

If `num_gpu` is too high the model no longer fits in VRAM and generation gets slower or fails: lower it by 1 or 2.

**Caveat.** Tuned settings can change the greedy wording slightly compared with the default settings (different context size and offload). Run any local evaluation with the **same settings you use for the demo**, and say which `Modelfile` produced the numbers.

## Keep the model loaded between requests

Ollama unloads an idle model after 5 minutes, and the next draft then pays the load time again (10 to 14 s). These two variables are read by the **Ollama server process**, not by the API, so they are not set in `scripts\run_c1_live.ps1`:

```powershell
setx OLLAMA_KEEP_ALIVE 1h
setx OLLAMA_FLASH_ATTENTION 1     # optional
```

`setx` only affects programs started afterwards: **quit Ollama (tray icon, Quit) and start it again.** Check with `ollama ps` while a draft is running.
