"""Profile 加载和校验测试."""
from __future__ import annotations

import pytest

from yolo_forge_core.converter.profiles import (
    BackgroundHandling,
    DatasetProfile,
    LabelFormat,
    Source,
)


class TestSourceParsing:
    def test_minimal_source(self):
        s = Source.from_dict({
            "name": "test",
            "path": "/tmp/test",
        })
        assert s.name == "test"
        assert s.path == "/tmp/test"
        assert s.label_format == LabelFormat.YOLO
        assert s.background == BackgroundHandling.INCLUDE

    def test_dict_class_mappings(self):
        # dict 简写形式
        s = Source.from_dict({
            "name": "test",
            "path": "/tmp/test",
            "class_mappings": {0: 1, 1: 0},  # 互换 id
        })
        assert len(s.class_mappings) == 2
        assert s.class_mappings[0].source_id == 0
        assert s.class_mappings[0].target_id == 1

    def test_voc_format(self):
        s = Source.from_dict({
            "name": "voc",
            "path": "/tmp/voc",
            "label_format": "voc",
            "class_mappings": [
                {"source_name": "dog", "target_id": 0},
            ],
        })
        assert s.label_format == LabelFormat.VOC
        assert s.class_mappings[0].source_name == "dog"


class TestProfileValidation:
    def test_split_must_sum_to_one(self):
        with pytest.raises(ValueError, match="必须为 1.0"):
            DatasetProfile(
                name="test",
                sources=[],
                output_dir="/tmp/out",
                classes=["a"],
                train_split=0.7,
                val_split=0.4,
                test_split=0.0,
            )

    def test_empty_sources_rejected(self):
        with pytest.raises(ValueError, match="至少要有一个 source"):
            DatasetProfile.from_dict({
                "name": "test",
                "output_dir": "/tmp/out",
                "classes": ["a"],
                "sources": [],
            })

    def test_validate_nonexistent_path(self, tmp_path):
        p = DatasetProfile(
            name="test",
            sources=[Source(name="s1", path="/nonexistent/path/xyz")],
            output_dir=str(tmp_path / "out"),
            classes=["a"],
        )
        ok, errors = p.validate()
        assert not ok
        assert any("path 不存在" in e for e in errors)

    def test_validate_ok(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        p = DatasetProfile(
            name="test",
            sources=[Source(name="s1", path=str(src_dir))],
            output_dir=str(tmp_path / "out"),
            classes=["a"],
        )
        ok, errors = p.validate()
        assert ok, errors


class TestProfileYamlRoundtrip:
    def test_yaml_roundtrip(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        original = DatasetProfile(
            name="rt_test",
            sources=[
                Source(name="s1", path=str(src_dir), label_format=LabelFormat.YOLO),
                Source(name="s2", path=str(src_dir), label_format=LabelFormat.NONE,
                       background=BackgroundHandling.SKIP),
            ],
            output_dir=str(tmp_path / "out"),
            classes=["cat", "dog"],
            description="Round-trip test",
        )
        yaml_path = tmp_path / "profile.yaml"
        original.to_yaml(yaml_path)

        loaded = DatasetProfile.from_yaml(yaml_path)
        assert loaded.name == "rt_test"
        assert loaded.classes == ["cat", "dog"]
        assert len(loaded.sources) == 2
        assert loaded.sources[0].label_format == LabelFormat.YOLO
        assert loaded.sources[1].background == BackgroundHandling.SKIP
