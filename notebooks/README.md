# Notebooks

## c1_remote_inference_colab.ipynb: run the C1 model on a remote GPU

The C1 app normally writes task drafts with the local Ollama model `c1-req` on your own computer ("On device"). This notebook serves the same model from a Google Colab GPU, so the app can use it as the **Cloud** target (Process > Cloud in the app). The model, the prompt and the Modelfile are unchanged. Nothing here claims that the cloud is faster: measure it (section D).

### A. Colab steps

1. Open `c1_remote_inference_colab.ipynb` in Google Colab. Choose *Runtime > Change runtime type > T4 GPU* (or better).
2. Put `c1_merged_q4_k_m.gguf` in Google Drive at `My Drive/Reasech Dataset/outputs/` (the folder name is spelled that way in the notebook).
3. Run the cells in order, one at a time:
   - cell 2 mounts Drive and copies the model to `/content/`;
   - cell 3 installs `zstd` and Ollama with the official install script;
   - cell 4 starts `ollama serve` with `OLLAMA_NUM_PARALLEL=4` and `OLLAMA_KEEP_ALIVE=24h` and waits until it answers;
   - cell 5 writes the Modelfile (the repository's `project/models/component1/part_b/Modelfile`, only the `FROM` line points at `/content/c1_merged_q4_k_m.gguf`) and runs `ollama create c1-req`;
   - cell 6 downloads `cloudflared`, opens a quick tunnel to `http://localhost:11434` and prints an `https://....trycloudflare.com` address;
   - cell 7 calls the address with `/api/tags` and `/v1/models` and prints the model list;
   - cell 8 stops the tunnel and Ollama.
4. In the C1 app (frontend): *Process:* > gear icon, paste the address into **Cloud URL**, leave the key empty, keep model `c1-req`, tick *Requirement text will be sent to this server*, press **Test connection**, then **Save**. When the test says *Connected*, choose **Cloud**.
5. When you are finished: run cell 8, then *Runtime > Disconnect and delete runtime*.

The app adds `/v1` to the address by itself.

### B. The same steps on a rented GPU box (RunPod, Vast.ai, similar)

The notebook is only a script for a Linux machine with a GPU; any such machine works.

1. Rent an instance with an NVIDIA GPU that has enough memory for the model file (check the size of `c1_merged_q4_k_m.gguf`) and a plain Ubuntu or PyTorch image with a shell.
2. Upload `c1_merged_q4_k_m.gguf` and `project/models/component1/part_b/Modelfile`. In the uploaded Modelfile change only the `FROM` line to the path of the uploaded file.
3. Install: `apt-get install -y zstd` (if missing), then `curl -fsSL https://ollama.com/install.sh | sh`.
4. Start the server and create the model:
   ```bash
   OLLAMA_NUM_PARALLEL=4 OLLAMA_KEEP_ALIVE=24h nohup ollama serve > ollama.log 2>&1 &
   ollama create c1-req -f Modelfile
   ```
5. Make port 11434 reachable over **https**. Either use the provider's HTTPS proxy for an exposed HTTP port (see the provider's documentation for the address format), or start a quick tunnel exactly as notebook cell 6 does (`cloudflared tunnel --no-autoupdate --http-host-header localhost:11434 --url http://localhost:11434`).
6. Check it from your laptop: `curl https://<address>/v1/models` must list `c1-req`.
7. Enter the address in the app as in A.4. If the provider's proxy needs a key, put it in the **API key** field (it is write-only).
8. **Stop the instance when you are done, or you keep paying.** Billing runs while the instance runs. A *stopped* instance can still be billed for its disk: *terminate / destroy* it (after copying anything you need) to stop all charges. Check the provider's billing page afterwards.

### C. Safety notes

- **Colab terms.** Google may restrict serving a web service through a tunnel from Colab. Check the current terms before you use the notebook; use it only if they allow it.
- **Requirement text leaves your laptop.** Every requirement sent for a draft travels over the internet to the remote machine. Do not use the cloud target for documents you are not allowed to send to a third party. The app asks for consent once (the tick box) and says *Requirement text is sent to a remote server* in the sidebar whenever Cloud is active.
- **The address has no password.** A quick-tunnel address is unguessable but not secret-protected: anyone who has it can use your model and send it text. Do not share it, paste it into chats, tickets or screenshots, or commit it. The app never shows the full address again after saving (only its host name) and never shows an API key.
- **Stop the runtime afterwards** (cell 8, then *Disconnect and delete runtime*; on a rented box, terminate it).
- Nothing switches automatically. If the cloud stops answering, the app pauses the drafts and shows **Cloud unreachable** with two buttons, *Retry* and *Switch to device*.

### D. An honest speed measurement (5 steps)

The aim is two numbers from your own hardware, not a claim.

1. **Pick one document** and use it for both runs. Set *Task drafts* to the same value both times (for a full comparison use *All requirements*).
2. **Start each run from nothing.** In the app press *Clear all* on the sources, then upload the document again. Clearing the sources does **not** clear the cache of already written drafts (it is shared by both targets), and a cached draft appears instantly, which would make the second run look fast for the wrong reason. So also delete the cached drafts before each run, from the repository root (this removes only cached drafts, nothing else):
   ```powershell
   py -c "import sqlite3; c = sqlite3.connect(r'project\outputs\c1_workspace\c1.db'); c.execute('DELETE FROM gen_cache'); c.commit(); print('cache cleared')"
   ```
3. **Run on the device first.** *Process: On device*, press *Run analysis*, start a stopwatch, and stop it when the draft progress shows every draft finished. Write down the seconds, the number of drafts, and the values on the *Engine status* card (Processing, Generation).
4. **Run on the cloud.** Repeat step 2, choose *Process: Cloud* (Test connection first), run the same analysis and write down the same values. The first request can be slow because the model is still loading (section E); to keep that out of the number, send one throw-away request first or report the first-request delay separately.
5. **Report both numbers as they are**: seconds per document and seconds per draft for each target, with the GPU and the laptop used. Do not extrapolate to other documents or other hardware, and say that the wording of drafts can differ slightly between targets (the same model on different hardware does not always give identical text).

The *time left* estimate in the app comes from the backend (items waiting divided by the measured throughput of the last 10 finished drafts on the active target); it is an estimate, not a result.

### E. Slow first request, and the timeout

The first request through a tunnel can take a long time while Ollama loads the model into GPU memory. Keep `LLM_TIMEOUT` at **600** on the laptop (`scripts/run_c1_live.ps1` already sets it) so the first draft is not cut off and counted as a failure.
