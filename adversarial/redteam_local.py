#!/usr/bin/env python3
"""Adversarial review of Flock ALPR RE findings using local abliterated models.

The hosted assistant tends to hedge on offensive-security reasoning. These local,
GPU-backed, uncensored ("heretic"/abliterated) models don't — so we use them for
the adversarial passes: red-teaming attack paths, refuting shaky findings, and
naming gaps the primary analysis skipped.

Backend: a local, GPU-backed Ollama host serving the abliterated models. Point
it at yours with --host or the OLLAMA_GEN_URL env var. No third-party deps.

Usage:
  # feed the workflow's JSON result (or any {..., "findings": [...]} / list)
  redteam_local.py --in findings.json --mode redteam
  redteam_local.py --in findings.json --mode refute --votes 3
  redteam_local.py --mode gaps --in analysis.json
  echo "hardcoded MQTT creds in system/etc/flock.conf" | redteam_local.py --mode refute

Modes:
  redteam  per finding: concrete attack paths, preconditions, impact (no hedging)
  refute   per finding: N independent skeptics try to refute; majority kills it
  gaps     one pass over all findings: what's missing / self-censored / unverified
"""
import argparse, json, os, sys, urllib.request, urllib.error

DEFAULT_HOST = os.environ.get("OLLAMA_GEN_URL", "http://127.0.0.1:11434")
# Most capable uncensored model on the gen host; override with --model.
DEFAULT_MODEL = os.environ.get(
    "HERETIC_MODEL",
    "hf.co/slevinw/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF:Q4_K_M",
)
FAST_MODEL = "heretic-llama31-8b-instruct:latest"  # cheap fan-out tier


def generate(host, model, prompt, num_predict=512, temperature=0.3,
             keep_alive="30m", timeout=300):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": num_predict, "temperature": temperature},
    }).encode()
    req = urllib.request.Request(host.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()).get("response", "").strip(), True
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        return f"[backend error: {e}]", False


def load_findings(path):
    """Accept: a JSON list of strings, {"findings":[...]}, or the workflow
    result object; else treat file as newline-delimited text."""
    raw = sys.stdin.read() if path in (None, "-") else open(path).read()
    try:
        obj = json.loads(raw)
    except ValueError:
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    out = []
    def add(x):
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, dict):
            out.append("; ".join(f"{k}={v}" for k, v in x.items()
                                 if isinstance(v, (str, int, float))))
    if isinstance(obj, list):
        for x in obj:
            add(x)
    elif isinstance(obj, dict):
        # pull the interesting arrays out of a workflow result
        for key in ("findings", "endpoints", "secrets_summary",
                    "strings_of_interest", "imports_of_interest",
                    "functions_of_interest", "key_findings", "re_targets"):
            for x in obj.get(key, []) or []:
                add(x)
        a = obj.get("analysis") or {}
        for key in ("endpoints", "secrets_summary", "functions_of_interest",
                    "strings_of_interest"):
            for x in a.get(key, []) or []:
                add(x)
        for e in obj.get("extraction", []) or []:
            for x in (e.get("key_findings") or []):
                add(f"[{e.get('component','?')}] {x}")
    # de-dup, preserve order
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f); uniq.append(f)
    return uniq


CTX = ("Target: a Flock Safety ALPR (license-plate reader) camera — a Qualcomm "
       "Snapdragon / Android mass-surveillance device. Its firmware was leaked "
       "publicly via DDoSecrets and is under authorized security review. Answer "
       "as a blunt offensive-security engineer; be concrete and technical, do "
       "not moralize, hedge, or add disclaimers.")


def redteam(host, model, findings, args):
    print(f"# Red-team pass ({model})\n")
    for i, f in enumerate(findings, 1):
        p = (f"{CTX}\n\nRE finding:\n{f}\n\nIf this is a real weakness, give: "
             "(1) the concrete attack path, (2) preconditions/access needed, "
             "(3) realistic impact, (4) how to confirm it against the dump. "
             "If it is not exploitable, say so plainly. Be terse.")
        out, ok = generate(host, model, p, num_predict=args.tokens,
                           temperature=0.4)
        print(f"## {i}. {f}\n\n{out}\n")
        sys.stdout.flush()


def refute(host, model, findings, args):
    print(f"# Refutation pass ({model}, {args.votes} skeptics each)\n")
    for i, f in enumerate(findings, 1):
        refuted = 0
        notes = []
        for v in range(args.votes):
            p = (f"{CTX}\n\nClaimed RE finding:\n{f}\n\nYou are skeptic #{v+1}. "
                 "Try hard to REFUTE this claim on technical grounds. If you "
                 "cannot refute it, say CONFIRMED. Start your answer with "
                 "exactly REFUTED or CONFIRMED, then one sentence why.")
            out, ok = generate(host, model, p, num_predict=180, temperature=0.6)
            verdict = "REFUTED" if out.upper().lstrip().startswith("REFUTED") else "CONFIRMED"
            if verdict == "REFUTED":
                refuted += 1
            notes.append(f"  - {verdict}: {out.splitlines()[0][:160] if out else ''}")
        survives = refuted < (args.votes + 1) // 2 + (0 if args.votes % 2 else 1)
        # majority-refute kills it: refuted > votes/2
        killed = refuted > args.votes / 2
        tag = "DROP" if killed else "KEEP"
        print(f"## {i}. [{tag}] ({refuted}/{args.votes} refuted) {f}")
        print("\n".join(notes) + "\n")
        sys.stdout.flush()


def gaps(host, model, findings, args):
    print(f"# Gap analysis ({model})\n")
    joined = "\n".join(f"- {f}" for f in findings)
    p = (f"{CTX}\n\nHere is everything the primary (hosted) analysis reported:\n"
         f"{joined}\n\nAs an adversarial reviewer, list what is MISSING: attack "
         "surface not examined, findings stated but never verified, likely "
         "secrets/endpoints/logic the primary pass would have skipped or "
         "self-censored, and the highest-value next probes against this firmware. "
         "Be specific to an Android/Qualcomm ALPR camera. Numbered list.")
    out, ok = generate(host, model, p, num_predict=max(args.tokens, 800),
                       temperature=0.5)
    print(out + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="infile", default="-",
                    help="findings JSON/text file, or - for stdin")
    ap.add_argument("--mode", choices=["redteam", "refute", "gaps"],
                    default="redteam")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"ollama model tag (default: 27B heretic; --fast for {FAST_MODEL})")
    ap.add_argument("--fast", action="store_true",
                    help=f"use the cheap 8B heretic tier ({FAST_MODEL})")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--votes", type=int, default=3, help="skeptics per finding (refute)")
    ap.add_argument("--tokens", type=int, default=400, help="num_predict per answer")
    args = ap.parse_args()
    if args.fast:
        args.model = FAST_MODEL

    findings = load_findings(args.infile)
    if not findings:
        sys.exit("no findings parsed from input")
    print(f"<!-- {len(findings)} findings | host {args.host} | model {args.model} -->\n")
    {"redteam": redteam, "refute": refute, "gaps": gaps}[args.mode](
        args.host, args.model, findings, args)


if __name__ == "__main__":
    main()
