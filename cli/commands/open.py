"""handoff open command."""

from __future__ import annotations

import os
import sys

from ..backend import (
    backend_type,
    build_resume_args,
    format_shell_command,
    resolved_backend_env,
    resolve_backend_model,
)
from ..config import Config
from .session_target import resolve_session_target


_OPEN_DROP_ENV_KEYS = {"ANTHROPIC_CLAUDECODE_PERMISSION_ACCEPT_ALL"}


def cmd_open(argv: list[str], config: Config):
    """handoff open [<run-id|seq>] [--backend <name>] [--session-id <id>]
    [--pro] [--cwd <dir>] [--verbose]."""
    verbose = "--verbose" in argv
    filtered = [a for a in argv if a != "--verbose"]

    backend_arg = ""
    session_id_arg: str | None = None
    cwd = ""
    selector = ""
    pro_override: bool | None = None

    i = 0
    while i < len(filtered):
        a = filtered[i]
        if a == "--cwd":
            i += 1
            if i >= len(filtered):
                print("handoff open: --cwd requires a value", file=sys.stderr)
                sys.exit(2)
            cwd = filtered[i]
        elif a == "--backend":
            i += 1
            if i >= len(filtered):
                print("handoff open: --backend requires a value", file=sys.stderr)
                sys.exit(2)
            backend_arg = filtered[i]
        elif a.startswith("--backend="):
            backend_arg = a.split("=", 1)[1]
        elif a == "--session-id":
            i += 1
            if i >= len(filtered):
                print("handoff open: --session-id requires a value", file=sys.stderr)
                sys.exit(2)
            session_id_arg = filtered[i]
        elif a.startswith("--session-id="):
            session_id_arg = a.split("=", 1)[1]
        elif a == "--pro":
            pro_override = True
        elif a in ("-h", "--help"):
            from ..main import usage
            usage()
            sys.exit(0)
        elif a.startswith("-"):
            print(f"handoff open: unknown option {a}", file=sys.stderr)
            sys.exit(2)
        else:
            if selector:
                print(f"handoff open: unexpected extra argument {a}", file=sys.stderr)
                sys.exit(2)
            selector = a
        i += 1

    target = resolve_session_target(
        config,
        command="open",
        selector=selector,
        backend_arg=backend_arg,
        session_id_arg=session_id_arg,
        cwd_arg=cwd,
        pro_override=pro_override,
    )
    _open_interactive(
        config,
        target.backend_name,
        target.session_id,
        target.cwd,
        target.pro,
        verbose=verbose,
    )


def _open_interactive(
    config: Config,
    backend_name: str,
    session_id: str,
    cwd: str,
    pro: bool,
    verbose: bool = False,
):
    backend_cfg = config.get_backend(backend_name)
    if not backend_cfg:
        print(
            f"handoff: unknown backend '{backend_name}'. "
            f"Available: {', '.join(sorted(config.backends.keys()))}",
            file=sys.stderr,
        )
        sys.exit(2)

    model = resolve_backend_model(backend_cfg, pro)
    backend_cfg["_resolved_model"] = model
    backend_cfg["_system_prompt"] = config.backend_system_prompt(backend_name)

    unset_keys, set_env = _resolved_open_env(backend_cfg, model)
    _apply_env(unset_keys, set_env)

    args = build_resume_args(
        backend_cfg,
        session_id,
        pro_model=backend_cfg.get("pro_model", ""),
    )

    if verbose:
        print(f"CMD: {format_shell_command(cwd, args, unset_keys, set_env)}", file=sys.stderr, flush=True)
    os.chdir(cwd)
    os.execvp(args[0], args)


def _resolved_open_env(backend_cfg: dict, model: str) -> tuple[list[str], dict[str, str]]:
    pro_model = backend_cfg.get("pro_model", "")
    unset_keys, set_env = resolved_backend_env(backend_cfg, model, pro_model)
    if backend_type(backend_cfg) != "claude":
        return unset_keys, set_env

    default_model = resolve_backend_model(backend_cfg, False)
    default_pro_model = resolve_backend_model(backend_cfg, True) or default_model

    base_env = {
        key: value
        for key, value in set_env.items()
        if key not in _OPEN_DROP_ENV_KEYS
        and key not in {
            "ANTHROPIC_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        }
    }

    if os.path.expanduser(base_env.get("CLAUDE_CONFIG_DIR", "")) == os.path.expanduser("~/.claude"):
        base_env.pop("CLAUDE_CONFIG_DIR", None)

    ordered_env = {}
    if model:
        ordered_env["ANTHROPIC_MODEL"] = model
    if default_pro_model:
        ordered_env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = default_pro_model
    if default_model:
        ordered_env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = default_model
        ordered_env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = default_model
    ordered_env.update(base_env)

    unset_keys = [key for key in unset_keys if key not in ordered_env]
    return unset_keys, ordered_env


def _apply_env(unset_keys: list[str], set_env: dict[str, str]) -> None:
    for key in unset_keys:
        os.environ.pop(key, None)
    for key in _OPEN_DROP_ENV_KEYS:
        os.environ.pop(key, None)
    for key, value in set_env.items():
        os.environ[key] = value
