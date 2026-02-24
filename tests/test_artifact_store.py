from __future__ import annotations

import unittest

from core import Artifact, ArtifactStore


class ArtifactStoreTests(unittest.TestCase):
    def test_register_increments_versions(self) -> None:
        store = ArtifactStore()
        artifact_v1 = Artifact(
            artifact_id="requirements-doc",
            artifact_type="requirements",
            producer="pm",
            content={"version": 1},
        )
        artifact_v2 = Artifact(
            artifact_id="requirements-doc",
            artifact_type="requirements",
            producer="pm",
            content={"version": 2},
        )

        stored_v1 = store.register("requirements", artifact_v1)
        stored_v2 = store.register("requirements", artifact_v2)

        self.assertEqual(1, stored_v1.version)
        self.assertEqual(2, stored_v2.version)
        self.assertEqual([1, 2], store.list_versions("requirements"))

    def test_get_latest_and_specific_version(self) -> None:
        store = ArtifactStore()
        store.register(
            "architecture",
            Artifact(
                artifact_id="architecture-doc",
                artifact_type="architecture",
                producer="architect",
                content={"revision": 1},
            ),
        )
        store.register(
            "architecture",
            Artifact(
                artifact_id="architecture-doc",
                artifact_type="architecture",
                producer="architect",
                content={"revision": 2},
            ),
        )

        self.assertEqual(2, store.get_latest("architecture").version)
        self.assertEqual(1, store.get_version("architecture", 1).version)
        self.assertIsNone(store.get_version("architecture", 3))


if __name__ == "__main__":
    unittest.main()
