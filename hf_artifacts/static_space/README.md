---
title: RepoNeedle Playground
emoji: 🪡
colorFrom: blue
colorTo: indigo
sdk: static
pinned: false
license: mit
---

# RepoNeedle Playground (V1.1.0)

This is the static browser interface for the RepoNeedle V1.1.0 public demonstration. It calls a separately hosted FastAPI service; the static Space does not execute the Python retrieval engine itself.

**Live backend:** `https://reponeedle.onrender.com`  
**Source repository:** https://github.com/krishika08/RepoNeedle  
**Dataset:** https://huggingface.co/datasets/RepoNeedle/RepoNeedle-Bench
## ☕ Support RepoNeedle

If you find RepoNeedle useful, consider supporting its continued development.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20RepoNeedle-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/krishika.x)

## Demonstration scope

The public Playground uses small embedded demonstration snapshots for `pallets/flask` and `psf/requests`. It does not clone arbitrary GitHub repositories, accept repository uploads, or reproduce the complete ARB v2 evaluation. Benchmark results described in the source repository were obtained in separate documented evaluations; this web demo is not itself a benchmark reproduction.

The browser sends retrieval requests to the public API. Queries are processed in memory and are not persisted by the demo API. The API is unauthenticated and intended for demonstration use, not production workloads. The free backend may sleep after inactivity, causing a cold-start delay.

## Reproducing the Space

Upload `README.md` and `index.html` from this directory to a Hugging Face Space with the **Static** SDK. The interface is preconfigured with the public demo API URL; users can change the URL to point to their own deployment.

See [deployment guide](https://github.com/krishika08/RepoNeedle/blob/main/docs/STATIC_PLAYGROUND_DEPLOYMENT.md) in the GitHub repository for backend deployment and configuration instructions.
