from backup.core.scoring import utils


def test_parse_solution_filename_supports_short_and_long_formats():
    assert utils._parse_solution_filename("Sol_S_002.dat") == ("small", "002")
    assert utils._parse_solution_filename("Sol_MPVRP_M_017_anything.dat") == ("medium", "017")


def test_parse_solution_filename_rejects_invalid_names():
    assert utils._parse_solution_filename("Sol_X_002.dat") is None
    assert utils._parse_solution_filename("Sol_S_2.dat") is None
    assert utils._parse_solution_filename("readme.txt") is None


def test_discover_category_dirs_prefers_shallow_path_and_warns_duplicates(tmp_path):
    (tmp_path / "small").mkdir()
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "small").mkdir()
    (nested / "medium").mkdir()

    category_dirs, warnings = utils._discover_category_dirs(str(tmp_path))

    assert category_dirs["small"] == str(tmp_path / "small")
    assert category_dirs["medium"] == str(nested / "medium")
    assert any("small" in warning for warning in warnings)


def test_validate_zip_structure_reports_missing_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "NUMBER_OF_INSTANCES_PER_CATEGORY", 1)
    (tmp_path / "small").mkdir()
    (tmp_path / "small" / "Sol_S_001.dat").write_text("dummy", encoding="utf-8")

    report = utils._validate_zip_structure(
        extract_root=str(tmp_path),
        category_dirs={"small": str(tmp_path / "small")},
    )

    assert report["ok"] is False
    assert any("medium" in err for err in report["errors"])
    assert any("large" in err for err in report["errors"])
    assert report["by_category"]["small"]["present"] is True


def test_failed_result_returns_expected_shape():
    result = utils._failed_result("boom")

    assert result["ok"] is False
    assert result["processor_info"] == "boom"
    assert result["total_feasible_count"] == 0
    assert result["instance_results"] == []
    assert set(result["category_stats"].keys()) == {"small", "medium", "large"}


