import zipfile

from backup.core.scoring import score_evaluation
from backup.core.scoring import utils as scoring_utils


def test_process_full_submission_returns_failure_for_missing_zip(tmp_path):
	missing_zip = tmp_path / "missing.zip"

	result = score_evaluation.process_full_submission(str(missing_zip))

	assert result["ok"] is False
	assert "ZIP file not found" in result["processor_info"]


def test_process_full_submission_returns_failure_for_bad_zip_and_cleans_file(tmp_path):
	bad_zip = tmp_path / "bad.zip"
	bad_zip.write_text("this is not a zip", encoding="utf-8")

	result = score_evaluation.process_full_submission(str(bad_zip))

	assert result["ok"] is False
	assert "not a valid ZIP" in result["processor_info"]
	assert not bad_zip.exists()


def test_process_full_submission_happy_path_with_minimal_dataset(tmp_path, monkeypatch):
	monkeypatch.setattr(score_evaluation, "NUMBER_OF_INSTANCES_PER_CATEGORY", 1)
	monkeypatch.setattr(scoring_utils, "NUMBER_OF_INSTANCES_PER_CATEGORY", 1)

	instances_root = tmp_path / "instances"
	for category, prefix in (("small", "S"), ("medium", "M"), ("large", "L")):
		cat_dir = instances_root / category
		cat_dir.mkdir(parents=True)
		(cat_dir / f"MPVRP_{prefix}_001_test.dat").write_text("instance", encoding="utf-8")
	monkeypatch.setattr(score_evaluation, "INSTANCES_ROOT", str(instances_root))

	import backup.core.model.feasibility as feasibility
	import backup.core.model.utils as model_utils

	monkeypatch.setattr(model_utils, "parse_instance", lambda _path: object())
	monkeypatch.setattr(model_utils, "parse_solution", lambda _path: object())
	monkeypatch.setattr(
		feasibility,
		"verify_solution",
		lambda _i, _s: ([], {"distance_total": 10.0, "total_switch_cost": 5.0}),
	)

	submission_zip = tmp_path / "submission.zip"
	with zipfile.ZipFile(submission_zip, "w") as zf:
		zf.writestr("small/Sol_S_001.dat", "sol")
		zf.writestr("medium/Sol_M_001.dat", "sol")
		zf.writestr("large/Sol_L_001.dat", "sol")

	result = score_evaluation.process_full_submission(str(submission_zip))

	assert result["ok"] is True
	assert result["is_fully_feasible"] is True
	assert result["total_feasible_count"] == 3
	assert result["category_stats"] == {"small": 1, "medium": 1, "large": 1}
	assert len(result["instance_results"]) == 3
	assert result["total_weighted_score"] == 8.5
	assert not submission_zip.exists()


