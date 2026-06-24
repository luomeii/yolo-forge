"""Trainer 模块测试 (只测配置/命令构造, 不实际跑训练)."""
from __future__ import annotations

import pytest

from yolo_forge_core.trainer import TrainConfig, TrainCallbacks, Trainer


def test_train_config_defaults():
    cfg = TrainConfig(data_yaml="/path/to/data.yaml")
    assert cfg.model == "yolo11n.pt"
    assert cfg.epochs == 100
    assert cfg.imgsz == 640
    assert cfg.batch == 16


def test_train_config_to_kwargs():
    cfg = TrainConfig(
        data_yaml="/path/to/data.yaml",
        model="yolo11s.pt",
        epochs=50,
        batch=8,
        device="0",
    )
    kw = cfg.to_ultralytics_kwargs()
    assert kw["data"] == "/path/to/data.yaml"
    assert kw["model"] == "yolo11s.pt"
    assert kw["epochs"] == 50
    assert kw["batch"] == 8
    assert kw["device"] == "0"


def test_trainer_command_construction():
    """测试训练命令构造正确."""
    cfg = TrainConfig(
        data_yaml="/data/data.yaml",
        model="yolo11n.pt",
        epochs=10,
        imgsz=640,
        batch=4,
        device="0",
        workers=2,
        project="/runs",
        name="test_exp",
    )
    trainer = Trainer(cfg, TrainCallbacks())
    cmd = trainer._build_command()

    # 命令第一个应该是 python, 第二个是 -m ultralytics, 第三个是 train
    assert "-m" in cmd
    assert "ultralytics" in cmd
    assert "train" in cmd

    # 关键参数都在
    cmd_str = " ".join(cmd)
    assert "model=yolo11n.pt" in cmd_str
    assert "data=/data/data.yaml" in cmd_str
    assert "epochs=10" in cmd_str
    assert "batch=4" in cmd_str
    assert "device=0" in cmd_str
    assert "name=test_exp" in cmd_str


def test_trainer_command_no_device_when_empty():
    """device 为空时不应该出现在命令里."""
    cfg = TrainConfig(data_yaml="/x.yaml", device="")
    trainer = Trainer(cfg, TrainCallbacks())
    cmd = trainer._build_command()
    assert not any("device=" in c for c in cmd)


def test_trainer_command_no_augment_flag():
    """augment=False 时应该有 augment=False 标志."""
    cfg = TrainConfig(data_yaml="/x.yaml", augment=False)
    trainer = Trainer(cfg, TrainCallbacks())
    cmd = trainer._build_command()
    assert "augment=False" in cmd


def test_trainer_not_running_initially():
    cfg = TrainConfig(data_yaml="/x.yaml")
    trainer = Trainer(cfg, TrainCallbacks())
    assert trainer.is_running() is False
