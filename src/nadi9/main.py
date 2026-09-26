from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nadi9.config.settings import Settings
from nadi9.graph.graph import run_pipeline
from nadi9.reporting import write_sample_run


def cli_entry() -> None:
    parser = argparse.ArgumentParser(description="Nadi-9 evidence-grounded subtitle decisions")
    parser.add_argument("--mode", default="mock", choices=["mock", "live"])
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--no-correction", action="store_true")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI reviewer API")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        from nadi9.api.app import app

        uvicorn.run(app, host="127.0.0.1", port=8000)
        return

    kwargs = {"mode": args.mode}
    if args.data_dir:
        kwargs["data_dir"] = Path(args.data_dir)
    if args.output_dir:
        kwargs["output_dir"] = Path(args.output_dir)
    settings = Settings(**kwargs)
    state = run_pipeline(
        settings,
        apply_midrun_correction=not args.no_correction,
    )
    write_sample_run(state, settings.output_dir)
    print(f"run_id={state.get('run_id')}")
    print(f"recommendation={state.get('release_recommendation')}")
    print(f"model_calls={state.get('model_calls')} tool_calls={state.get('tool_calls')}")
    print(f"wrote {settings.output_dir}")


def main() -> None:
    cli_entry()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
