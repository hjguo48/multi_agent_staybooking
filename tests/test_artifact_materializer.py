from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.artifact_materializer import ArtifactMaterializer


class ArtifactMaterializerTests(unittest.TestCase):
    def test_materialize_writes_code_bundle_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "generated"
            template_backend = Path(tmpdir) / "backend_template"
            template_frontend = Path(tmpdir) / "frontend_template"
            template_backend.mkdir(parents=True, exist_ok=True)
            template_frontend.mkdir(parents=True, exist_ok=True)
            (template_backend / "build.gradle").write_text("plugins {}", encoding="utf-8")
            (template_frontend / "package.json").write_text("{}", encoding="utf-8")

            materializer = ArtifactMaterializer(output_root)
            payload = {
                "artifact_store": {
                    "backend_code": [
                        {
                            "content": {
                                "code_bundle": {
                                    "src/main/java/com/example/App.java": "class App {}",
                                }
                            }
                        }
                    ],
                    "frontend_code": [
                        {
                            "content": {
                                "code_bundle": {
                                    "src/App.jsx": "export default function App() { return null; }",
                                }
                            }
                        }
                    ],
                }
            }

            result = materializer.materialize(
                run_name="test-run",
                state_payload=payload,
                backend_template=template_backend,
                frontend_template=template_frontend,
            )

            backend_root = Path(result.backend_root)
            frontend_root = Path(result.frontend_root)
            self.assertTrue((backend_root / "build.gradle").exists())
            self.assertTrue((frontend_root / "package.json").exists())
            self.assertTrue((backend_root / "src/main/java/com/example/App.java").exists())
            self.assertTrue((frontend_root / "src/App.jsx").exists())

    def test_materialize_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            materializer = ArtifactMaterializer(Path(tmpdir) / "generated")
            payload = {
                "artifact_store": {
                    "backend_code": [
                        {
                            "content": {
                                "code_bundle": {
                                    "../escape.txt": "bad",
                                }
                            }
                        }
                    ],
                    "frontend_code": [{"content": {"code_bundle": {}}}],
                }
            }

            with self.assertRaises(ValueError):
                materializer.materialize(run_name="escape-run", state_payload=payload)


if __name__ == "__main__":
    unittest.main()
