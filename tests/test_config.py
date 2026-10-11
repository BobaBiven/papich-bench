from __future__ import annotations

from pathlib import Path

import pytest

from papich_bench.config import AnswererSpec, ConfigError, RunConfig


def _cfg() -> RunConfig:
    return RunConfig(
        answerers=[
            AnswererSpec(name="llm_direct", label="glm", options={"model": "glm"}),
            AnswererSpec(name="llm_direct", label="minimax", options={"model": "minimax"}),
            AnswererSpec(name="duckduckgo"),
        ]
    )


def test_label_is_display_name() -> None:
    assert AnswererSpec(name="llm_direct", label="glm").display_name == "glm"
    assert AnswererSpec(name="llm_direct").display_name == "llm_direct"


def test_duplicate_display_names_rejected() -> None:
    with pytest.raises(ValueError, match="distinct `label`"):
        RunConfig(answerers=[AnswererSpec(name="llm_direct"), AnswererSpec(name="llm_direct")])


def test_duplicate_display_names_in_yaml_is_config_error(tmp_path: Path) -> None:
    path = tmp_path / "cfg.yaml"
    path.write_text("answerers: [llm_direct, llm_direct]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="distinct `label`"):
        RunConfig.from_yaml(path)


def test_select_by_label_keeps_options() -> None:
    [spec] = _cfg().select_answerers(["minimax"])
    assert spec.label == "minimax"
    assert spec.options == {"model": "minimax"}


def test_select_by_name_picks_every_entry() -> None:
    picked = _cfg().select_answerers(["llm_direct"])
    assert [s.display_name for s in picked] == ["glm", "minimax"]


def test_select_unknown_to_config_uses_defaults() -> None:
    [spec] = _cfg().select_answerers(["tavily"])
    assert spec == AnswererSpec(name="tavily")


def test_select_does_not_duplicate_overlapping_tokens() -> None:
    picked = _cfg().select_answerers(["glm", "llm_direct", "duckduckgo"])
    assert [s.display_name for s in picked] == ["glm", "minimax", "duckduckgo"]
