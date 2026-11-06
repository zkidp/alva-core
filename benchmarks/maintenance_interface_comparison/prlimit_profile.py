#!/usr/bin/python3
"""Trusted launcher: one fixed prospective RLIMIT_NPROC adjustment only."""
import os
import sys

if __name__ == "__main__":
    args = sys.argv[1:]
    if args.count("--nproc=128:128") != 1:
        raise SystemExit("Unexpected resource profile; no launch")
    args = ["--nproc=512:512" if a == "--nproc=128:128" else a for a in args]
    os.execv("/usr/bin/prlimit", ["/usr/bin/prlimit", *args])
