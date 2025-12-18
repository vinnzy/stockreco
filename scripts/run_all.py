#!/usr/bin/env python3
"""
Unified orchestration script for the entire stock recommendation pipeline.

This script:
1. Generates models (data/models) at end of day
2. Generates stock recommendations (reports/...)
3. Generates options recommendations (reports/options/...)
4. Generates MCX recommendations (reports/mcx/...)
5. Starts the backend API server
6. Starts the frontend development server

Usage:
    python scripts/run_all.py [--as-of YYYY-MM-DD] [--skip-models] [--skip-servers]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import os
import signal
from pathlib import Path
from datetime import datetime, timedelta


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _get_yesterday() -> str:
    """Get yesterday's date in YYYY-MM-DD format."""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def run_step(step_name: str, cmd: list[str], cwd: Path | None = None) -> bool:
    """Run a command and return True if successful."""
    print(f"\n{'='*80}")
    print(f"🚀 STEP: {step_name}")
    print(f"{'='*80}")
    print(f"▶ Running: {' '.join(cmd)}")
    print(f"{'='*80}\n")
    
    try:
        subprocess.check_call(cmd, cwd=cwd)
        print(f"\n✅ {step_name} completed successfully!\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {step_name} failed with exit code {e.returncode}\n", file=sys.stderr)
        return False
    except Exception as e:
        print(f"\n❌ {step_name} failed: {e}\n", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(
        description="Run the complete stock recommendation pipeline and start servers"
    )
    ap.add_argument(
        "--as-of",
        default=None,
        help="Date for processing (YYYY-MM-DD). Default: yesterday"
    )
    ap.add_argument(
        "--skip-models",
        action="store_true",
        help="Skip model generation (use existing models)"
    )
    ap.add_argument(
        "--skip-servers",
        action="store_true",
        help="Skip starting the backend and frontend servers"
    )
    ap.add_argument(
        "--mode",
        default="aggressive",
        help="Signal generation mode: aggressive|balanced|conservative"
    )
    ap.add_argument(
        "--provider",
        default="local_csv",
        help="Data provider: local_csv|nse_fallback|zerodha|upstox"
    )
    ap.add_argument(
        "--universe",
        default=None,
        help="Comma-separated list of tickers (optional, auto-detected if not provided)"
    )
    ap.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM-based qualitative review (requires OPENAI_API_KEY)"
    )
    
    args = ap.parse_args()
    
    repo = _repo_root()
    as_of = args.as_of or _get_yesterday()
    
    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                   STOCK RECOMMENDATION PIPELINE                            ║
║                                                                            ║
║  Date: {as_of}                                                      ║
║  Mode: {args.mode}                                                   ║
║  Provider: {args.provider}                                          ║
║  LLM Review: {"ENABLED" if args.use_llm else "DISABLED"}                                         ║
╚════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Track success/failure
    results = {}
    
    # =========================================================================
    # STEP 1: Generate Models and Stock Recommendations
    # =========================================================================
    if not args.skip_models:
        cmd = [
            sys.executable,
            "scripts/run_daily_full_pipeline.py",
            "--as-of", as_of,
            "--mode", args.mode,
            "--provider", args.provider,
        ]
        if args.universe:
            cmd.extend(["--universe", args.universe])
        
        results["models_and_stocks"] = run_step(
            "Generate Models & Stock Recommendations",
            cmd,
            cwd=repo
        )
        
        if not results["models_and_stocks"]:
            print("\n⚠️  Model/Stock generation failed. Continuing with other steps...\n")
    else:
        print("\n⏭️  Skipping model generation (--skip-models flag set)\n")
        results["models_and_stocks"] = True  # Mark as success since we're skipping
    
    # =========================================================================
    # STEP 2: Generate Options Recommendations
    # =========================================================================
    cmd = [
        sys.executable,
        "scripts/run_eod_option_reco.py",
        "--as-of", as_of,
        "--provider", args.provider,
    ]
    if args.universe:
        cmd.extend(["--universe", args.universe])
    
    if args.use_llm:
        cmd.append("--use-llm")
    
    results["options"] = run_step(
        "Generate Options Recommendations",
        cmd,
        cwd=repo
    )
    
    if not results["options"]:
        print("\n⚠️  Options generation failed. Continuing with other steps...\n")
    
    # =========================================================================
    # STEP 3: Generate MCX Recommendations
    # =========================================================================
    cmd = [
        sys.executable,
        "scripts/generate_mcx_recos.py",
        "--as-of", as_of,
    ]
    
    results["mcx"] = run_step(
        "Generate MCX Recommendations",
        cmd,
        cwd=repo
    )
    
    if not results["mcx"]:
        print("\n⚠️  MCX generation failed. Continuing with other steps...\n")
    
    # =========================================================================
    # STEP 3.5: Evaluate Options Performance (Lifecycle Tracking)
    # =========================================================================
    # Loop through recos from the last 15 days and update their status with today's data.
    print(f"\n{'-'*60}")
    print("📈 Updating Option Performance Lifecycle...")
    print(f"{'-'*60}\n")
    
    try:
        current_dt = datetime.strptime(as_of, "%Y-%m-%d")
        options_dir = repo / "reports" / "options"
        
        # Look back 15 days
        for i in range(15):
            past_dt = current_dt - timedelta(days=i) # today, yesterday, ...
            # Skip if checking future vs past (though logic handles it)
            # Actually we want: for RECO_DATE in [last 15 days], check against OUTCOME_DATE (as_of)
            # If reco_date == as_of, we haven't generated outcomes yet (rec usually for next day).
            # But technically we can check same-day if intraday.
            # Usually we assume Reco is generated EOD for Next Day, but sometimes EOD for Today.
            # Let's just process all found files.
            
            reco_date_str = past_dt.strftime("%Y-%m-%d")
            reco_file = options_dir / f"option_reco_{reco_date_str}.json"
            
            # If checking today's reco against today's data? 
            # If reco is generated AT 3:30 PM, it has no performance yet (performance starts tomorrow).
            # So maybe skip i=0 (today)? 
            # But the user might run this for a past date "as_of".
            # Safe logic: Run for all exists. If reco_date == outcome_date, nothing happens (day 0).
            
            if reco_file.exists():
                print(f"   > Updating performance for Reco {reco_date_str}...")
                cmd = [
                    sys.executable,
                    "scripts/generate_option_performance.py",
                    "--reco-file", str(reco_file),
                    "--outcome-date", as_of
                ]
                # We don't fail the pipeline if one update fails
                subprocess.call(cmd, cwd=repo)
                
        results["option_performance"] = True
            
    except Exception as e:
        print(f"\n⚠️  Option Performance cycle failed: {e}\n")
        results["option_performance"] = False

    
    # =========================================================================
    # STEP 4: Start Servers (if not skipped)
    # =========================================================================
    if not args.skip_servers:
        print(f"\n{'='*80}")
        print("🌐 STARTING SERVERS")
        print(f"{'='*80}\n")
        
        print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                          SERVERS STARTING                                  ║
║                                                                            ║
║  Backend API:  http://localhost:8000                                       ║
║  Frontend UI:  http://localhost:5173                                       ║
║                                                                            ║
║  Press Ctrl+C to stop both servers                                        ║
╚════════════════════════════════════════════════════════════════════════════╝
""")
        
        # Start backend server
        backend_proc = subprocess.Popen(
            [sys.executable, "scripts/run_ui_api.py"],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Start frontend server
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=repo / "frontend",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        print("✅ Backend server started (PID: {})".format(backend_proc.pid))
        print("✅ Frontend server started (PID: {})\n".format(frontend_proc.pid))
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            print("\n\n🛑 Shutting down servers...")
            backend_proc.terminate()
            frontend_proc.terminate()
            try:
                backend_proc.wait(timeout=5)
                frontend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_proc.kill()
                frontend_proc.kill()
            print("✅ Servers stopped.\n")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Stream output from both processes
        try:
            while True:
                # Check if processes are still running
                if backend_proc.poll() is not None:
                    print("❌ Backend server stopped unexpectedly!")
                    break
                if frontend_proc.poll() is not None:
                    print("❌ Frontend server stopped unexpectedly!")
                    break
                
                # Read and print output
                if backend_proc.stdout:
                    line = backend_proc.stdout.readline()
                    if line:
                        print(f"[BACKEND] {line.rstrip()}")
                
                if frontend_proc.stdout:
                    line = frontend_proc.stdout.readline()
                    if line:
                        print(f"[FRONTEND] {line.rstrip()}")
        
        except KeyboardInterrupt:
            signal_handler(None, None)
    else:
        print("\n⏭️  Skipping server startup (--skip-servers flag set)\n")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print(f"\n{'='*80}")
    print("📊 PIPELINE SUMMARY")
    print(f"{'='*80}\n")
    
    for step, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {step.upper()}: {status}")
    
    print(f"\n{'='*80}\n")
    
    # Exit with error code if any critical step failed
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
