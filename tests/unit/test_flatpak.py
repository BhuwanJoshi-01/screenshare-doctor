from __future__ import annotations

from pathlib import Path

from screenshare_doctor.collectors.flatpak import installed_flatpaks


def test_system_and_user_installations() -> None:
    present = {
        "/var/lib/flatpak/app/com.discordapp.Discord",
        "/home/u/.local/share/flatpak/app/org.mozilla.firefox",
    }
    found = installed_flatpaks(
        ["com.discordapp.Discord", "org.mozilla.firefox", "com.slack.Slack"],
        home="/home/u",
        is_dir=present.__contains__,
    )
    assert found == ("com.discordapp.Discord", "org.mozilla.firefox")


def test_without_home_only_the_system_directory_is_checked() -> None:
    looked: list[str] = []

    def is_dir(path: str) -> bool:
        looked.append(path)
        return False

    assert installed_flatpaks(["a.b.C"], home=None, is_dir=is_dir) == ()
    assert looked == ["/var/lib/flatpak/app/a.b.C"]


def test_real_directories(tmp_path: Path) -> None:
    (tmp_path / ".local/share/flatpak/app/org.example.ScreenshareDoctorTest").mkdir(parents=True)
    assert installed_flatpaks(["org.example.ScreenshareDoctorTest"], home=str(tmp_path)) == (
        "org.example.ScreenshareDoctorTest",
    )
