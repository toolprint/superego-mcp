#!/usr/bin/env python3
"""Container test validation script.

This script validates that the container testing environment is properly set up
and that all container test dependencies are available.
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import docker
import requests


def run_command(cmd: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, and stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", f"Command failed: {e}"


def check_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def check_docker_buildx() -> bool:
    """Check if Docker Buildx is available."""
    code, _, _ = run_command(["docker", "buildx", "version"])
    return code == 0


def check_python_dependencies() -> Dict[str, bool]:
    """Check if required Python dependencies are available."""
    dependencies = {
        'docker': False,
        'httpx': False,
        'psutil': False,
        'pytest': False,
        'requests': False,
    }
    
    for dep in dependencies:
        try:
            __import__(dep)
            dependencies[dep] = True
        except ImportError:
            dependencies[dep] = False
    
    return dependencies


def check_project_structure() -> Dict[str, bool]:
    """Check if project structure is correct for container testing."""
    project_root = Path(__file__).parent.parent
    
    required_files = {
        'docker/production/Dockerfile': project_root / 'docker/production/Dockerfile',
        'docker-compose.yml': project_root / 'docker-compose.yml',
        'tests/test_container.py': project_root / 'tests/test_container.py',
        'justfile': project_root / 'justfile',
        'pyproject.toml': project_root / 'pyproject.toml',
    }
    
    file_status = {}
    for name, path in required_files.items():
        file_status[name] = path.exists()
    
    return file_status


def check_uv_available() -> bool:
    """Check if UV is available for Python package management."""
    code, _, _ = run_command(["uv", "--version"])
    return code == 0


def validate_dockerfile() -> bool:
    """Validate Dockerfile syntax and structure."""
    project_root = Path(__file__).parent.parent
    dockerfile_path = project_root / 'docker/production/Dockerfile'
    
    if not dockerfile_path.exists():
        return False
    
    content = dockerfile_path.read_text()
    
    # Check for required elements
    required_elements = [
        'FROM python:3.12-slim',
        'USER superego',
        'HEALTHCHECK',
        'EXPOSE 8000',
        'ENTRYPOINT'
    ]
    
    return all(element in content for element in required_elements)


def check_justfile_tasks() -> Dict[str, bool]:
    """Check if container test tasks are present in justfile."""
    project_root = Path(__file__).parent.parent
    justfile_path = project_root / 'justfile'
    
    if not justfile_path.exists():
        return {}
    
    content = justfile_path.read_text()
    
    required_tasks = {
        'test-container-build': 'test-container-build:' in content,
        'test-container': 'test-container:' in content,
        'test-container-startup': 'test-container-startup:' in content,
        'test-container-transports': 'test-container-transports:' in content,
        'test-container-performance': 'test-container-performance:' in content,
        'test-container-security': 'test-container-security:' in content,
        'test-container-full': 'test-container-full:' in content,
    }
    
    return required_tasks


def print_status(name: str, status: bool, details: str = "") -> None:
    """Print status with color coding."""
    if status:
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    else:
        print(f"❌ {name}")
        if details:
            print(f"   {details}")


def print_dict_status(name: str, status_dict: Dict[str, bool]) -> None:
    """Print status dictionary with individual items."""
    all_good = all(status_dict.values())
    print_status(name, all_good)
    
    for item, status in status_dict.items():
        indent = "   "
        if status:
            print(f"{indent}✅ {item}")
        else:
            print(f"{indent}❌ {item}")


def main() -> int:
    """Main validation function."""
    print("🔍 Validating Container Testing Environment")
    print("=" * 50)
    
    success = True
    
    # Check Docker
    docker_available = check_docker_available()
    print_status("Docker Available", docker_available, 
                 "Docker daemon is running" if docker_available else "Docker not available or not running")
    if not docker_available:
        success = False
    
    # Check Docker Buildx
    buildx_available = check_docker_buildx()
    print_status("Docker Buildx Available", buildx_available)
    if not buildx_available:
        success = False
    
    # Check UV
    uv_available = check_uv_available()
    print_status("UV Package Manager Available", uv_available)
    if not uv_available:
        success = False
    
    # Check Python dependencies
    print("\n📦 Python Dependencies:")
    deps = check_python_dependencies()
    print_dict_status("Python Dependencies", deps)
    if not all(deps.values()):
        success = False
        print("   💡 Install missing dependencies with: uv sync")
    
    # Check project structure
    print("\n📁 Project Structure:")
    files = check_project_structure()
    print_dict_status("Required Files", files)
    if not all(files.values()):
        success = False
    
    # Check Dockerfile
    dockerfile_valid = validate_dockerfile()
    print_status("Dockerfile Valid", dockerfile_valid, 
                 "All required elements present" if dockerfile_valid else "Missing required elements")
    if not dockerfile_valid:
        success = False
    
    # Check justfile tasks
    print("\n📝 Justfile Tasks:")
    tasks = check_justfile_tasks()
    print_dict_status("Container Test Tasks", tasks)
    if not all(tasks.values()):
        success = False
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 Environment validation successful!")
        print("\n💡 Next steps:")
        print("   1. Build container image: just test-container-build")
        print("   2. Run basic tests: just test-container")
        print("   3. Run full test suite: just test-container-full")
        return 0
    else:
        print("❌ Environment validation failed!")
        print("\n🔧 Fix the issues above and run validation again")
        return 1


if __name__ == "__main__":
    exit(main())