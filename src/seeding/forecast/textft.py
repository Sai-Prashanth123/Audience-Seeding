"""Fine-tuned text model on CPU (same job as section A of notebooks/colab_train.ipynb, without a GPU).

For each frozen fold and target (views, X score): fine-tune `BAAI/bge-small-en-v1.5` with a regression head on that
fold's TRAIN posts to predict how much a post beats its author's usual level (y - lb, standardized), then predict the
fold's cal and test posts. Lighter than the GPU version (1 epoch, 96 tokens) so it finishes in a few hours on CPU.
Output: data/colab/text_ft_preds.parquet (fold, tweet_id, target, split, ft_pred), judged later like any member.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .colab import DIR, EXPORT

MODEL = "BAAI/bge-small-en-v1.5"
MAX_LEN = 96
BATCH = 32
LR = 3e-5
EPOCHS = 1


def _batches(texts: list[str], tok, labels=None, shuffle=False, seed=0):
    import torch
    idx = np.arange(len(texts))
    if shuffle:
        np.random.default_rng(seed).shuffle(idx)
    for i in range(0, len(idx), BATCH):
        b = idx[i:i + BATCH]
        enc = tok([texts[j] for j in b], truncation=True, max_length=MAX_LEN, padding=True, return_tensors="pt")
        yield enc, (torch.tensor(labels[b], dtype=torch.float32) if labels is not None else None)


def run(threads: int = 8) -> str:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    torch.set_num_threads(threads)
    torch.manual_seed(0)
    df = pd.read_parquet(EXPORT)
    tok = AutoTokenizer.from_pretrained(MODEL)
    parts_dir = DIR / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    for k in range(1, 5):
        for t in ("views", "xscore"):
            part = parts_dir / f"textft_f{k}_{t}.parquet"
            if part.exists():
                print("done already:", part.name, flush=True)
                continue
            f = f"fold{k}"
            tr = df[df[f] == "train"].dropna(subset=[f"y_{t}", f"lb_{t}"])
            ev = df[df[f].isin(["cal", "test"])]
            resid = (tr[f"y_{t}"] - tr[f"lb_{t}"]).to_numpy()
            mu, sd = resid.mean(), resid.std()
            model = AutoModelForSequenceClassification.from_pretrained(MODEL, num_labels=1, problem_type="regression")
            opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
            texts = tr.text.fillna("").str.slice(0, 600).tolist()
            y = ((resid - mu) / sd).astype(np.float32)
            n_steps = EPOCHS * int(np.ceil(len(texts) / BATCH))
            sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=n_steps, pct_start=0.06)
            model.train()
            t0, step = time.time(), 0
            for ep in range(EPOCHS):
                for enc, lab in _batches(texts, tok, y, shuffle=True, seed=ep):
                    loss = torch.nn.functional.mse_loss(model(**enc).logits.squeeze(-1), lab)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step(); sched.step(); opt.zero_grad()
                    step += 1
                    if step % 100 == 0:
                        print(f"fold {k} {t}: step {step}/{n_steps} loss {loss.item():.3f} "
                              f"({(time.time() - t0) / step:.2f}s/step)", flush=True)
            model.eval()
            preds = []
            with torch.no_grad():
                for enc, _ in _batches(ev.text.fillna("").str.slice(0, 600).tolist(), tok):
                    preds.append(model(**enc).logits.squeeze(-1).numpy())
            pd.DataFrame({"fold": k, "tweet_id": ev.tweet_id.to_numpy(), "target": t, "split": ev[f].to_numpy(),
                          "ft_pred": np.concatenate(preds) * sd + mu}).to_parquet(part, index=False)
            print(f"saved {part.name}: trained on {len(tr):,}, predicted {len(ev):,} "
                  f"in {(time.time() - t0) / 60:.0f} min", flush=True)
    out = pd.concat([pd.read_parquet(p) for p in sorted(parts_dir.glob("textft_*.parquet"))], ignore_index=True)
    path = DIR / "text_ft_preds.parquet"
    out.to_parquet(path, index=False)
    return str(path)
