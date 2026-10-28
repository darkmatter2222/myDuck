#!/usr/bin/env python3
"""Run a setup step with live output, periodic heartbeat and a finite timeout."""
import argparse
import os
import signal
import subprocess
import sys
import threading
import time


def run_step(command, label, timeout=1200, heartbeat=15):
    started=time.monotonic()
    print(f'[SETUP] {label}: starting',flush=True)
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                           start_new_session=True,bufsize=0)
    def relay():
        for line in iter(child.stdout.readline,b''):
            print(line.decode('utf-8','replace').rstrip('\r\n'),flush=True)
    reader=threading.Thread(target=relay,daemon=True);reader.start()
    next_notice=started+heartbeat
    try:
        while child.poll() is None:
            elapsed=time.monotonic()-started
            if elapsed>timeout:
                print(f'[SETUP] {label}: timed out after {timeout}s; see setup log.',flush=True)
                return 124
            if time.monotonic()>=next_notice:
                print(f'[SETUP] {label}: still running ({int(elapsed)}s elapsed)',flush=True)
                next_notice=time.monotonic()+heartbeat
            time.sleep(.1)
        reader.join(timeout=3)
        print(f'[SETUP] {label}: exit {child.returncode} ({int(time.monotonic()-started)}s)',flush=True)
        return child.returncode
    finally:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
        reader.join(timeout=2)
        child.stdout.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',required=True)
    parser.add_argument('--timeout',type=float,default=1200)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:parser.error('command required')
    sys.exit(run_step(command,args.label,args.timeout))
