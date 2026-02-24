from __future__ import annotations

import unittest
from pathlib import Path

from evaluation.extract_ground_truth import build_ground_truth


class GroundTruthPathTests(unittest.TestCase):
    def test_filesystem_paths_are_relative_and_posix(self) -> None:
        backend_dir = Path("ground_truth/staybooking-project").resolve()
        frontend_dir = Path("ground_truth/stayboookingfe").resolve()
        data = build_ground_truth(backend_dir, frontend_dir)

        source_backend_path = data["sources"]["backend"]["path"]
        source_frontend_path = data["sources"]["frontend"]["path"]
        self.assertFalse(Path(source_backend_path).is_absolute())
        self.assertFalse(Path(source_frontend_path).is_absolute())
        self.assertNotIn("\\", source_backend_path)
        self.assertNotIn("\\", source_frontend_path)

        for endpoint in data["backend"]["endpoints"]:
            self.assertFalse(Path(endpoint["file"]).is_absolute())
            self.assertNotIn("\\", endpoint["file"])

        for entity in data["backend"]["entities"]:
            self.assertFalse(Path(entity["file"]).is_absolute())
            self.assertNotIn("\\", entity["file"])

        for path in data["backend"]["structure"]["controllers"]:
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("\\", path)
        for path in data["backend"]["structure"]["services"]:
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("\\", path)
        for path in data["backend"]["structure"]["repositories"]:
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("\\", path)

        for component in data["frontend"]["components"]:
            self.assertFalse(Path(component).is_absolute())
            self.assertNotIn("\\", component)


if __name__ == "__main__":
    unittest.main()
