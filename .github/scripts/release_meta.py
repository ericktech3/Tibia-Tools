from __future__ import annotations

import re
from pathlib import Path


class ReleaseMetadataError(RuntimeError):
    pass



def read_buildozer_version(spec_path: str = "buildozer.spec") -> str:
    text = Path(spec_path).read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(?m)^\s*version\s*=\s*([^\s#]+)\s*$", text)
    if not match:
        raise ReleaseMetadataError("version não encontrada no buildozer.spec")
    return match.group(1).strip()



def normalize_release_tag(tag: str) -> str:
    value = str(tag or "").strip()
    value = re.sub(r"^[vV][._-]?", "", value)
    return value.strip()



def validate_release_tag(tag: str, version: str) -> None:
    normalized_tag = normalize_release_tag(tag)
    normalized_version = normalize_release_tag(version)
    if not normalized_tag:
        raise ReleaseMetadataError("tag de release vazia")
    if normalized_tag != normalized_version:
        raise ReleaseMetadataError(
            f"tag '{tag}' não bate com a versão '{version}' do buildozer.spec"
        )


if __name__ == "__main__":
    version = read_buildozer_version()
    print(version)
