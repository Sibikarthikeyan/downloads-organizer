"""Unit tests for the pipeline: ignore list, plugins, error isolation."""

from pathlib import Path

from downloads_organizer.classifier.base import Classification
from downloads_organizer.config.schema import AppConfig
from downloads_organizer.core.pipeline import OrganizerPipeline
from downloads_organizer.plugins.base import OrganizerPlugin
from downloads_organizer.plugins.registry import PluginRegistry
from tests.conftest import make_file


def test_scan_existing_organizes_mock_downloads(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "Invoice_March.pdf")
    make_file(downloads, "photo.png")
    make_file(downloads, "mystery.blob")
    make_file(downloads, "notes.tmp")  # ignored pattern
    make_file(downloads, ".hidden")  # hidden

    moved = OrganizerPipeline(config).scan_existing()

    assert moved == 3
    assert (downloads / "Bills" / "Invoice_March.pdf").is_file()  # rule beats extension
    assert (downloads / "Images" / "photo.png").is_file()
    assert (downloads / "Unknown" / "mystery.blob").is_file()
    assert (downloads / "notes.tmp").is_file()
    assert (downloads / ".hidden").is_file()


def test_files_in_managed_folders_are_not_reprocessed(config: AppConfig, downloads: Path) -> None:
    organized = downloads / "Images" / "photo.png"
    organized.parent.mkdir()
    organized.write_bytes(b"x")
    pipeline = OrganizerPipeline(config)
    assert not pipeline.should_process(organized)


def test_nested_robotics_categories(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "scan.pcd")
    make_file(downloads, "rosbag2.db3")
    make_file(downloads, "arm.urdf")
    make_file(downloads, "cartographer_map.db")

    assert OrganizerPipeline(config).scan_existing() == 4
    assert (downloads / "Robotics" / "PointClouds" / "scan.pcd").is_file()
    assert (downloads / "Robotics" / "Rosbags" / "rosbag2.db3").is_file()
    assert (downloads / "Robotics" / "Models" / "arm.urdf").is_file()
    assert (downloads / "Robotics" / "Data" / "cartographer_map.db").is_file()


def test_files_inside_nested_managed_folders_are_skipped(config: AppConfig, downloads: Path) -> None:
    organized = downloads / "Robotics" / "PointClouds" / "scan.pcd"
    organized.parent.mkdir(parents=True)
    organized.write_bytes(b"x")
    pipeline = OrganizerPipeline(config)
    assert not pipeline.should_process(organized)
    assert pipeline.scan_existing() == 0


def test_directories_are_ignored(config: AppConfig, downloads: Path) -> None:
    (downloads / "somedir").mkdir()
    assert OrganizerPipeline(config).scan_existing() == 0


def test_plugin_classify_and_hooks(config: AppConfig, downloads: Path) -> None:
    events: list[str] = []

    class PdfToTaxes(OrganizerPlugin):
        name = "taxes"
        priority = 50  # before filename rules

        def classify(self, path: Path) -> Classification | None:
            if path.suffix == ".pdf":
                return Classification("Taxes", "plugin says so")
            return None

        def after_move(self, source: Path, destination: Path, classification: Classification) -> None:
            events.append(f"after:{destination.name}")

    registry = PluginRegistry()
    registry.register(PdfToTaxes())
    make_file(downloads, "Invoice_March.pdf")
    OrganizerPipeline(config, registry=registry).scan_existing()

    assert (downloads / "Taxes" / "Invoice_March.pdf").is_file()
    assert events == ["after:Invoice_March.pdf"]


def test_plugin_veto_blocks_move(config: AppConfig, downloads: Path) -> None:
    class VetoAll(OrganizerPlugin):
        name = "veto"

        def before_move(self, path: Path, classification: Classification) -> bool:
            return False

    registry = PluginRegistry()
    registry.register(VetoAll())
    src = make_file(downloads, "photo.png")
    assert OrganizerPipeline(config, registry=registry).scan_existing() == 0
    assert src.exists()


def test_crashing_plugin_does_not_stop_processing(config: AppConfig, downloads: Path) -> None:
    class Broken(OrganizerPlugin):
        name = "broken"

        def classify(self, path: Path) -> Classification | None:
            raise RuntimeError("boom")

        def after_move(self, *args: object) -> None:
            raise RuntimeError("boom again")

    registry = PluginRegistry()
    registry.register(Broken())
    make_file(downloads, "photo.png")
    assert OrganizerPipeline(config, registry=registry).scan_existing() == 1
    assert (downloads / "Images" / "photo.png").is_file()


def test_dry_run_scan_touches_nothing(config: AppConfig, downloads: Path) -> None:
    config.dry_run = True
    make_file(downloads, "photo.png")
    OrganizerPipeline(config).scan_existing()
    assert (downloads / "photo.png").is_file()
    assert not (downloads / "Images").exists()
