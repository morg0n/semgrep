import os
import time
from pathlib import Path
from typing import Optional

from packaging.version import InvalidVersion
from packaging.version import Version

from semgrep import constants
from semgrep import util

VERSION_CHECK_URL = str(
    os.environ.get(
        "SEMGREP_VERSION_CHECK_URL", "https://semgrep.live/api/check-version"
    )
)
VERSION_CHECK_TIMEOUT = int(
    os.environ.get(
        "SEMGREP_VERSION_CHECK_TIMEOUT", 2  # Don't block user's for too long
    )
)
VERSION_CACHE_PATH = Path(
    os.environ.get(
        "SEMGREP_VERSION_CACHE_PATH",
        Path(os.path.expanduser("~")) / ".cache" / "semgrep_version",
    )
)


def _fetch_latest_version(
    url: str = VERSION_CHECK_URL, timeout: int = VERSION_CHECK_TIMEOUT
) -> Optional[str]:
    try:
        import requests

        resp = requests.get(
            url,
            headers={"User-Agent": f"Semgrep/{constants.__VERSION__}"},
            timeout=timeout,
        )
    except Exception as e:
        util.debug_print(f"Fetching latest version failed to connect: {e}")
        return None
    else:
        if resp.status_code != requests.codes.OK:
            util.debug_print(
                f"Fetching latest version received HTTP error code: {resp.status_code}"
            )
            return None
        try:
            resp_json = resp.json()
        except ValueError:
            util.debug_print("Fetching latest version received invalid JSON")
            return None
        else:
            return str(resp_json["latest"])


def _get_version_from_cache(version_cache_path: Path) -> Optional[str]:
    now = time.time()

    if version_cache_path.is_file():
        with version_cache_path.open() as f:
            timestamp_str = f.readline().strip()
            latest_version_str = f.readline().strip()

            try:
                # Treat time as integer seconds so no need to deal with str float conversion
                timestamp = int(timestamp_str)
            except ValueError:
                util.debug_print(f"Version cache invalid timestamp: {timestamp_str}")
                return None

            one_day = 86400
            if now - timestamp > one_day:
                util.debug_print(f"Version cache expired: {timestamp_str}:{now}")
                return None

            return latest_version_str

    util.debug_print("Version cache does not exist")
    return None


def _get_latest_version(version_cache_path: Path) -> Optional[str]:
    latest_version_str = _get_version_from_cache(version_cache_path)
    if latest_version_str is None:
        latest_version_str = _fetch_latest_version()
        if latest_version_str is None:
            # Request timed out or invalid
            return None

        version_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with version_cache_path.open("w") as f:
            # Integer time so no need to deal with str float conversions
            f.write(f"{int(time.time())}\n")
            f.write(latest_version_str)

    return latest_version_str


def is_running_latest(version_cache_path: Path = VERSION_CACHE_PATH) -> bool:
    latest_version_str = _get_latest_version(version_cache_path)
    if latest_version_str is None:
        return False

    try:
        latest_version = Version(latest_version_str)
        current_version = Version(constants.__VERSION__)
    except InvalidVersion as e:
        util.debug_print(f"Invalid version string: {e}")
        return False

    if current_version < latest_version:
        return False

    return True
