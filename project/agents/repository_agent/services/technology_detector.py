from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "build",
    "dist",
    "__pycache__",
}


def detect_repository_technology(repo_path: Path) -> dict:
    """Infer primary language and technology from repository files."""

    if not repo_path.is_dir():
        return {
            "language": "Unknown",
            "technology": "Unknown",
        }

    extensions = {}
    root_files = set()

    for path in repo_path.iterdir():
        if path.is_file():
            root_files.add(path.name.lower())

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue

        if any(part in SKIP_DIRS for part in path.parts):
            continue

        extension = path.suffix.lower()
        if extension:
            extensions[extension] = extensions.get(extension, 0) + 1

    if ".java" in extensions:
        language = "Java"
        technology = "Java"

        pom_path = repo_path / "pom.xml"
        gradle_files = list(repo_path.glob("*.gradle")) + list(
            repo_path.glob("*.gradle.kts")
        )

        if pom_path.is_file():
            try:
                pom_text = pom_path.read_text(encoding="utf-8", errors="ignore").lower()

                if "spring-boot" in pom_text or "springframework.boot" in pom_text:
                    technology = "Spring Boot"
                elif "springframework" in pom_text:
                    technology = "Spring"
                else:
                    technology = "Maven / Java"
            except OSError:
                technology = "Java"

        elif gradle_files:
            technology = "Gradle / Java"

    elif ".tsx" in extensions or ".jsx" in extensions:
        language = "TypeScript" if ".tsx" in extensions else "JavaScript"
        technology = (
            "React" if ".tsx" in extensions or ".jsx" in extensions else language
        )

    elif ".ts" in extensions:
        language = "TypeScript"
        technology = "TypeScript"

    elif ".js" in extensions:
        language = "JavaScript"
        technology = "JavaScript"

    elif ".py" in extensions:
        language = "Python"
        technology = "Python"

        if "requirements.txt" in root_files or "pyproject.toml" in root_files:
            technology = "Python project"

    elif ".cs" in extensions or any(name.endswith(".csproj") for name in root_files):
        language = "C#"
        technology = ".NET"

    elif ".go" in extensions:
        language = "Go"
        technology = "Go"

    elif ".php" in extensions:
        language = "PHP"
        technology = "PHP"

    else:
        language = "Unknown"
        technology = "Unknown"

    return {
        "language": language,
        "technology": technology,
    }
