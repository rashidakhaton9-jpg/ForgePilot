import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "forgepilot.py"
SPEC = importlib.util.spec_from_file_location("forgepilot", SCRIPT)
forgepilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forgepilot)


class ForgePilotTests(unittest.TestCase):
    def test_inventory_finds_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("test", encoding="utf-8")
            (root / "sample.py").write_text("print('hi')", encoding="utf-8")
            result = forgepilot.inventory(root)
            self.assertIn("README.md", result["markers_found"])
            self.assertEqual(result["extensions"][".py"], 1)

    def test_checks_warn_when_readme_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = forgepilot.checks(Path(tmp))
            readme = next(x for x in result if x["check"] == "README exists")
            self.assertEqual(readme["status"], "WARN")

    def test_invalid_path_raises(self):
        with self.assertRaises(ValueError):
            forgepilot.inventory(Path("/this/path/should/not/exist/forgepilot-test"))


class SkillValidatorTests(unittest.TestCase):
    def test_project_skill_metadata_validates(self):
        validator_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_skill.py"
        validator_spec = importlib.util.spec_from_file_location("validate_skill", validator_path)
        validator = importlib.util.module_from_spec(validator_spec)
        validator_spec.loader.exec_module(validator)
        errors = validator.validate(Path(__file__).resolve().parents[1])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
