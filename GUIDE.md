# Step-by-step guide: test AI language models on your Android phone

This guide shows how to run open AI language models on an Android phone, fully offline, and measure them the same way as in this project. You don't need to know how to program. You will copy commands into an app and press Enter.

**What you'll get:** four sets of results: how fast each model writes and reads, how heat and battery change over 10 minutes, and how many test questions each model gets right.

**Time:** about one evening for setup (Steps 1–6), then 15–60 minutes for each test.

**You need:**
- An Android phone from about 2020 or later with 6 GB of RAM or more (the tests here used a OnePlus Nord 2 with 8 GB)
- About 16 GB of free storage
- Wi-Fi for setup and downloads
- Optional: a computer, if you'd rather type the long commands on a keyboard

> **How to use the commands.** Each grey box is one command block. Copy the whole block, paste it into Termux and press Enter. Wait until you see the `$` prompt again before pasting the next block. If a long line gets split while pasting and you see an error, run the lines one at a time.

New words are explained in the [Words used here](README.md#words-used-here) table in the README.

---

## Before every test session

The same conditions every time matter more than any single setting. Change one thing at a time and write everything else down.

- [ ] **Turn off "RAM expansion"** (also called virtual RAM or memory extension) in the phone's settings, and leave it off. It uses storage as pretend memory, which is many times slower and would distort the results. Changing it needs a restart.
- [ ] **Charge to full, then unplug.** Charging heats the battery and skews temperature and battery readings.
- [ ] **Turn on airplane mode.** Background syncing steals processor time in the middle of a test.
- [ ] **Keep Termux open on the screen**, with the screen timeout set to 30 minutes and brightness low. Android moves apps in the background onto its slow cores, which would change the results.
- [ ] **Close all other apps.**
- [ ] **Same spot, no case.** Put the phone flat on a table in the same room each time, and note the room temperature.

---

## Step 1 – Install Termux and Termux:API

Termux gives your phone a Linux command line. Termux:API lets it read the battery's temperature and charge level.

Install both from F-Droid, not the Play Store. Termux add-ons only work when they come from the same store as Termux itself.

1. On the phone, open [f-droid.org](https://f-droid.org) in the browser, download the F-Droid app and install it. Allow "Install unknown apps" for the browser when asked.
2. In F-Droid, install **Termux**, then **Termux:API**.
3. Go to Settings → Apps → Termux → Battery, and set it to **Unrestricted** (it may be called "Don't optimise" or "Allow background activity"). Do the same for Termux:API.
4. Open Termux once and wait until it shows a `$` prompt.

---

## Step 2 – Install the tools

Wi-Fi on for this step.

**Install the packages.** If it asks about a configuration file, press Enter to keep the default.

```bash
pkg update && pkg upgrade -y
pkg install -y git cmake clang make libandroid-spawn
pkg install -y openssl wget jq python unzip zip termux-api tmux
```

If you see `404 Not Found` errors, the download server Termux picked is out of date. Run `termux-change-repo`, choose **Single mirror**, pick the default one (`packages.termux.dev`), then run the commands again.

**Allow storage access, keep the processor awake, and make the lab folders.** Tap Allow when asked.

```bash
termux-setup-storage
termux-wake-lock
mkdir -p ~/lab/models ~/lab/results ~/lab/scripts
```

**Check that the battery can be read.** This should print a few lines including `"temperature"`. If it hangs, open the Termux:API app once and try again.

```bash
termux-battery-status
```

**Get the test scripts.** Copy this repository onto the phone and put its four scripts in the lab folder.

```bash
git clone https://github.com/prashantksingh09/android-llm-bench ~/lab/repo
cp ~/lab/repo/scripts/* ~/lab/scripts/
ls ~/lab/scripts
```

You should see `cool.sh`, `quality.py`, `show.py` and `sustained.py`.

**Write down the phone's details.** Change `25` to your room temperature in °C and `4500` to your battery size in mAh.

```bash
cd ~/lab
{
  echo "date: $(date '+%Y-%m-%d %H:%M')"
  echo "phone: $(getprop ro.product.model)"
  echo "android: $(getprop ro.build.version.release)"
  echo "os_build: $(getprop ro.build.display.id)"
  grep MemTotal /proc/meminfo
  echo "room_temp_c: 25"
  echo "ram_expansion: off"
  echo "battery_mah: 4500"
} > results/env.txt
cat results/env.txt
```

### Optional: type from your computer

Long commands are easier on a keyboard. Use this only for setup and for starting tests. The phone and the computer must be on the same Wi-Fi network.

On the phone:

```bash
pkg install -y openssh
passwd
whoami
sshd
```

- `passwd` asks you to type a new password twice. Type it on its own line after the prompt, not after the word `passwd`. Nothing appears on screen while you type, and that's normal.
- `whoami` prints your Termux user name, something like `u0_a245`.

Find the phone's IP address under Settings → Wi-Fi → your network. Then, on the computer:

```bash
ssh -p 8022 u0_a245@192.168.1.23
```

Use your own user name and IP address. The port is always 8022.

If you connect through a phone hotspot and the connection times out, the hotspot may be blocking devices from talking to each other. Make the test phone the hotspot and join it from the computer.

---

## Step 3 – Build llama.cpp

llama.cpp is the free software that runs the models. This builds only the four tools the tests use. It takes about 5–15 minutes, and the phone will get warm.

```bash
cd ~/lab
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
git checkout caa8191df
cmake -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build build --config Release -j 4 --target llama-bench llama-server llama-cli llama-perplexity
echo "llama.cpp: $(git rev-parse --short HEAD)" >> ~/lab/results/env.txt
ls build/bin
```

The last line should list `llama-bench`, `llama-cli`, `llama-perplexity` and `llama-server`.

- **`git checkout caa8191df`** uses the exact version this project's results came from. Leave that line out to use the newest version instead, but then use the same version for every test.
- **`-j 4`, not 8:** building eight files at once can run the phone out of memory.

---

## Step 4 – Find your fast cores

Phone chips mix fast cores with slow, power-saving ones. You need to know which core numbers are fast, so you can keep the work on them.

```bash
for c in 0 1 2 3 4 5 6 7; do
  f=$(cat /sys/devices/system/cpu/cpu$c/cpufreq/cpuinfo_max_freq 2>/dev/null || echo 0)
  echo "cpu$c: $((f / 1000)) MHz"
done | tee -a ~/lab/results/env.txt
```

On the Nord 2, cores 0–3 top out at 2,000 MHz (slow) and cores 4–7 at 2,600–3,000 MHz (fast).

The commands below use **`0xF0`**, which means "cores 4 to 7". If your fast cores have different numbers, you need a different code. For example, `0x0F` means cores 0 to 3, and `0xC0` means cores 6 and 7.

**Why it matters:** llama.cpp splits each step of work evenly across its threads, then waits for all of them to finish. If one thread lands on a slow core, the fast ones sit idle waiting for it.

---

## Step 5 – Download the models

The test set is one model family, Qwen3.5, in three sizes, each at two compression levels: six files, about 12.5 GB in total. Wi-Fi on.

| Size | Compression | File | Download |
| --- | --- | --- | --- |
| 0.8B | 4-bit | `Qwen_Qwen3.5-0.8B-Q4_K_M.gguf` | 0.58 GB |
| 0.8B | 8-bit | `Qwen_Qwen3.5-0.8B-Q8_0.gguf` | 0.84 GB |
| 2B | 4-bit | `Qwen_Qwen3.5-2B-Q4_K_M.gguf` | 1.40 GB |
| 2B | 8-bit | `Qwen_Qwen3.5-2B-Q8_0.gguf` | 2.08 GB |
| 4B | 4-bit | `Qwen_Qwen3.5-4B-Q4_K_M.gguf` | 3.01 GB |
| 4B | 8-bit | `Qwen_Qwen3.5-4B-Q8_0.gguf` | 4.62 GB |

```bash
cd ~/lab/models
for s in 0.8B 2B 4B; do
  for q in Q4_K_M Q8_0; do
    f=Qwen_Qwen3.5-$s-$q.gguf
    wget -c "https://huggingface.co/bartowski/Qwen_Qwen3.5-$s-GGUF/resolve/main/$f"
  done
done
ls -lh
```

If a download stops, run the same block again: `-c` picks up where it left off and skips finished files. If you get a 404 error, open the model's page on [Hugging Face](https://huggingface.co/bartowski) and copy the current file name.

On a phone with 6 GB of RAM, the 4B 8-bit file may not fit. Step 6 will tell you.

---

## Step 6 – Quick check

**Ask one question.** If you get a one-sentence answer, everything works.

```bash
cd ~/lab/llama.cpp
./build/bin/llama-cli -m ~/lab/models/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf -c 2048 -t 4 -C 0xF0 --cpu-strict 1 --reasoning off -st -p "In one sentence, why is the sky blue?"
```

**Check that every file loads.** Each model should print a `pp32` line and a `tg16` line.

```bash
cd ~/lab/llama.cpp
for m in ~/lab/models/*.gguf; do
  echo "== $(basename $m)"
  ./build/bin/llama-bench -m $m -t 4 -p 32 -n 16 -r 1 2>&1 | grep -E 'pp32|tg16|error|failed'
done
```

If a model prints nothing, or you see `Killed`, it ran out of memory. Leave that file out of the tests and note it in `env.txt`.

---

## Before the tests: pick a cooldown temperature

Every test starts only once the battery has cooled to the same temperature, so heat from one run doesn't carry into the next.

Leave the phone idle on the table for 10 minutes, then run:

```bash
termux-battery-status | jq .temperature
```

Add 2 to the number it prints. That's your cooldown temperature. The commands below use **31**; replace it with yours everywhere. If the cooldown script keeps saying "cooling…" for more than 15 minutes, the room is too warm, so pick a number 2 degrees higher and use it for every test.

**Use tmux for long tests.** tmux keeps a test running even if your computer's connection to the phone drops. Start it with `tmux new -s lab` and paste the test commands. To step out without stopping the test, press Ctrl+B, then D. To come back, run `tmux attach -t lab`. When nothing is running, type `exit` to close it.

---

## Step 7 – Speed test

`llama-bench` measures two speeds in tokens per second: **pp** (reading a prompt) and **tg** (writing an answer).

### 7a – Find the best thread setting (about 10 minutes)

This runs the smallest model with 1 to 8 threads placed by Android, then with 4 threads kept on the fast cores.

```bash
cd ~/lab/llama.cpp
M=~/lab/models/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf
bash ~/lab/scripts/cool.sh 31
./build/bin/llama-bench -m $M -p 256 -n 64 -t 1,2,3,4,6,8 -r 3 --delay 10 -o csv > ~/lab/results/threads.csv
bash ~/lab/scripts/cool.sh 31
./build/bin/llama-bench -m $M -p 256 -n 64 -t 4 -C 0xF0 --cpu-strict 1 -r 3 --delay 10 -o csv > ~/lab/results/threads_pinned.csv
python ~/lab/scripts/show.py ~/lab/results/threads*.csv
```

Pick the setting with the highest **tg** number, because that's the speed you feel. On the Nord 2, 4 threads on the fast cores won. The rest of this guide uses that setting. If something else wins on your phone, change `T` and `PIN` in the commands below.

### 7b – Every model (about 30–60 minutes)

```bash
cd ~/lab/llama.cpp
T=4
PIN="-C 0xF0 --cpu-strict 1"
for m in ~/lab/models/*.gguf; do
  n=$(basename $m .gguf); f=~/lab/results/speed_$n.csv
  if [ -f "$f" ] && [ "$(wc -l < "$f")" -ge 3 ]; then echo "skip $n (done)"; continue; fi
  echo "== $n"
  bash ~/lab/scripts/cool.sh 31
  ./build/bin/llama-bench -m $m -t $T $PIN -p 512 -n 128 -r 3 --delay 15 -o csv > $f
done
python ~/lab/scripts/show.py ~/lab/results/speed_*.csv
```

Each result is saved as soon as that model finishes. If the run is interrupted, paste the same block again: it skips the models that are already done.

- **`-r 3`** runs each test 3 times and reports the average and the spread (the ± number).
- **Wait before the answer starts:** for a 512-token prompt, it's about 512 ÷ the pp512 speed, in seconds.

### 7c – Longer context (optional, about 30–45 minutes)

Steps 7a and 7b start every test from an empty context. In a real conversation, the model also looks back over everything said so far. This test first fills the context to a set length, then measures writing speed. Each length runs on its own after a cooldown, so heat doesn't mix into the result.

```bash
cd ~/lab/llama.cpp
for d in 0 1024 2048 4096 8192; do
  bash ~/lab/scripts/cool.sh 31
  ./build/bin/llama-bench -m ~/lab/models/Qwen_Qwen3.5-2B-Q4_K_M.gguf -t 4 -C 0xF0 --cpu-strict 1 -p 0 -n 128 -d $d -r 3 --progress -o csv > ~/lab/results/depth_2B_$d.csv
done
for d in 0 1024 2048 4096 8192; do echo "depth $d"; python ~/lab/scripts/show.py ~/lab/results/depth_2B_$d.csv; done
```

`--progress` prints each stage on screen, because the results themselves go into the files.

**Optional: see how big the cache is.** This loads the model with room for 8,192 tokens and saves llama.cpp's detailed log, which reports the cache size and which layers keep one.

```bash
cd ~/lab/llama.cpp
./build/bin/llama-cli -m ~/lab/models/Qwen_Qwen3.5-2B-Q4_K_M.gguf -c 8192 -n 1 -st -p hi -v > ~/lab/results/kvcache_2B_ctx8192.log 2>&1
grep -E "llama_kv_cache: size|llama_memory_recurrent: size" ~/lab/results/kvcache_2B_ctx8192.log
```

---

## Step 8 – Heat and battery over 10 minutes (about 40 minutes)

Step 7 measures a cool phone. This step measures a phone that has been working nonstop for 10 minutes. The script writes text in 128-token rounds and logs speed, battery temperature and charge after each round.

Charge to full and unplug first. Then:

```bash
bash ~/lab/scripts/cool.sh 31
python ~/lab/scripts/sustained.py ~/lab/models/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf --threads 4 --mask 0xF0
bash ~/lab/scripts/cool.sh 31
python ~/lab/scripts/sustained.py ~/lab/models/Qwen_Qwen3.5-4B-Q4_K_M.gguf --threads 4 --mask 0xF0
```

Leave the phone alone with Termux on screen until both runs finish. Each run ends with a summary of tokens written, battery used and battery per 1,000 tokens.

- **Different battery size?** Add `--capacity` followed by your battery size in mAh (for example `--capacity 5000`) to get battery use in mAh.
- **Ignore the `current_ua` column** in the results file. Many phones report it in mixed units, and it is read in the short idle pause between rounds.

---

## Step 9 – Quality check (about 30–60 minutes)

Speed is only half the story. This step asks every model the same 20 questions and marks the answers.

Each model is started as a small local server, the questions are asked, and then the server is stopped. Settings are fixed (temperature 0, same seed), so the same model always gives the same answer.

```bash
cd ~/lab/llama.cpp
T=4
PIN="-C 0xF0 --cpu-strict 1"
for m in ~/lab/models/*.gguf; do
  bash ~/lab/scripts/cool.sh 31
  ./build/bin/llama-server -m $m -t $T $PIN -c 4096 -np 1 --port 8080 --reasoning off > ~/lab/results/server.log 2>&1 &
  python ~/lab/scripts/quality.py $m
  kill $!; sleep 5
done
```

Short answers are marked automatically. Answers longer than 8 words are flagged `REVIEW`, because a model that explains itself can mention the right number and still get the answer wrong. For those, open the `quality_*.csv` file and type 1 (right) or 0 (wrong) in the empty `correct` cell.

### Optional: perplexity

Perplexity measures how well each model predicts real Wikipedia text. Lower is better. It's the standard way to measure what compression costs. Wi-Fi on for the download.

```bash
cd ~/lab/llama.cpp
bash scripts/get-wikitext-2.sh
for m in ~/lab/models/*.gguf; do
  n=$(basename $m .gguf)
  ./build/bin/llama-perplexity -m $m -f wikitext-2-raw/wiki.test.raw -c 512 -b 512 --chunks 20 -t 4 -C 0xF0 --cpu-strict 1 2>&1 | tee ~/lab/results/ppl_$n.txt | grep 'Final estimate'
done
```

This test needs extra memory on top of the model. On the 8 GB Nord 2, the 4B 8-bit file did not fit: Android stopped the test even right after a restart. To see how much memory is free, run `grep MemAvailable /proc/meminfo`.

---

## Step 10 – Collect the results and make the charts

**Zip the results into the phone's Downloads folder:**

```bash
cd ~/lab
zip -r ~/storage/downloads/llm-lab-results-$(date +%Y%m%d).zip results
```

Move the zip to your computer (USB cable, email or cloud storage) and unzip it.

**Make the charts** on your computer, from a copy of this repository. Replace the files in its `results/` folder with yours, then run:

```bash
pip install -r requirements.txt
python analysis/make_figures.py
```

The script rebuilds every chart in `figures/`, writes `analysis/summary.csv` and prints the key numbers. If your phone has a different memory speed, change `PEAK_BANDWIDTH_GBS` at the top of the script. You can find your chip's memory bandwidth on its spec sheet.

---

## Extra: chat with a model

Once Step 3 is done, you can chat with any of the models offline. Save two shortcuts once:

```bash
cat >> ~/.bashrc <<'EOF'

# chat [size] [bits]  e.g. chat, chat 4B, chat 0.8B Q8_0
chat() {
  ~/lab/llama.cpp/build/bin/llama-cli -m ~/lab/models/Qwen_Qwen3.5-${1:-2B}-${2:-Q4_K_M}.gguf -c 4096 -t 4 -C 0xF0 --cpu-strict 1 --reasoning off
}
# ask "question" [size]  e.g. ask "why is the sky blue?"
ask() {
  ~/lab/llama.cpp/build/bin/llama-cli -m ~/lab/models/Qwen_Qwen3.5-${2:-2B}-Q4_K_M.gguf -c 2048 -t 4 -C 0xF0 --cpu-strict 1 --reasoning off -st -p "$1"
}
EOF
grep -q bashrc ~/.bash_profile 2>/dev/null || echo '[ -f ~/.bashrc ] && . ~/.bashrc' >> ~/.bash_profile
source ~/.bashrc
```

Now type `chat` for a back-and-forth conversation (Ctrl+C to quit), or `ask "your question"` for one quick answer.

---

## Troubleshooting

| What you see | Likely cause | What to do |
| --- | --- | --- |
| `Killed`, or Termux closes while a model loads | Out of memory | Close other apps, restart the phone, or leave that model out |
| `Connection closed by remote host` over SSH during a big test | Android stopped Termux to free memory | Run that test on the phone itself, inside tmux, right after a restart |
| `[Process completed (signal 9)]` with memory to spare | Android stops busy background apps | Keep Termux on screen. Advanced: from a computer with USB debugging, run `adb shell settings put global settings_enable_monitor_phantom_procs false` |
| `404 Not Found` from `pkg install` | Out-of-date download server | Run `termux-change-repo` and pick the default single mirror |
| `404` from `wget` | The model file was renamed | Open the model's page and copy the current file name |
| `termux-battery-status` hangs | Termux:API missing, or from a different store | Install Termux:API from F-Droid and open it once |
| `can't open file '.../termux-api'` | A long command got split while pasting | Run the lines one at a time |
| `passwd: run passwd without args` | The password was typed on the same line | Type `passwd` alone, then the password when asked |
| SSH says the password is wrong | Wrong user name, or the password was never set | Run `whoami` and `passwd` again on the phone, then test with `ssh -p 8022 localhost` on the phone |
| `address already in use` on port 8080 | An old server is still running | `pkill llama-server` |
| Very slow results with a big ± | Heat, background apps, or threads on slow cores | Airplane mode, cool down, close apps, use `-C` with your fast-core code |
| Numbers change between days | Different llama.cpp version or a warmer room | Check the version in `env.txt` and note the room temperature |
