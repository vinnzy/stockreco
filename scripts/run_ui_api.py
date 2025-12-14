#!/usr/bin/env python3
from __future__ import annotations
import argparse
from stockreco.api.app import run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    run(host=args.host, port=args.port)

if __name__ == "__main__":
    main()
