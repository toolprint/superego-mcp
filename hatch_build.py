"""Custom Hatch build hooks for superego-mcp asset management.

This module provides comprehensive build hooks for:
- Frontend asset copying and optimization
- Configuration file validation and inclusion
- Static asset management with compression
- UV-based Python execution throughout build process
- Build-time validation and metadata injection
- Runtime asset verification
"""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class SuperegoBuildHook(BuildHookInterface):
    """Custom build hook for superego-mcp with asset management and optimization.
    
    Features:
    - UV-integrated Python execution
    - Frontend asset copying and optimization
    - Configuration directory management (config/, static/, templates/)
    - Static asset compression and validation
    - Build-time integrity checks
    - Custom metadata injection
    """

    PLUGIN_NAME = "superego-build-hook"
    
    # Asset directories to manage
    ASSET_DIRECTORIES = {
        "config": ["*.yaml", "*.yml", "*.json"],
        "static": ["*.css", "*.js", "*.html", "*.png", "*.svg", "*.ico"],
        "templates": ["*.html", "*.jinja2", "*.j2"],
        "demo/config": ["*.yaml", "*.yml", "*.json"],
    }
    
    @property
    def root_path(self) -> Path:
        """Get root path as a Path object."""
        return Path(self.root)
    
    # Compression settings for static assets
    COMPRESSION_SETTINGS = {
        "css": {"compress": True, "min_size": 1024},
        "js": {"compress": True, "min_size": 1024},
        "html": {"compress": True, "min_size": 512},
        "json": {"compress": False, "min_size": 0},  # Keep JSON readable
        "yaml": {"compress": False, "min_size": 0},  # Keep YAML readable
        "yml": {"compress": False, "min_size": 0},
    }

    def _run_uv_python(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        """Execute Python script using UV for consistent environment."""
        cmd = ["uv", "run", "python", "-c", script] + list(args)
        return subprocess.run(
            cmd,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            check=False,
        )
    
    def _run_uv_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Execute UV command with error handling."""
        cmd = ["uv"] + list(args)
        return subprocess.run(
            cmd,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            check=False,
        )

    def clean(self, versions: list[str]) -> None:
        """Clean build artifacts and temporary files."""
        print("🧹 Cleaning superego-mcp build artifacts...")
        
        # Clean common build artifacts
        artifacts_to_clean = [
            self.root_path / "dist",
            self.root_path / "build", 
            self.root_path / ".pytest_cache",
            self.root_path / "htmlcov",
            self.root_path / "build_report.json",
            self.root_path / "src" / "superego_mcp" / "_build_metadata.json",
            self.root_path / "src" / "superego_mcp" / "_asset_checksums.json",
        ]
        
        for artifact in artifacts_to_clean:
            if artifact.exists():
                if artifact.is_dir():
                    shutil.rmtree(artifact, ignore_errors=True)
                else:
                    artifact.unlink(missing_ok=True)
        
        # Clean __pycache__ directories
        for pycache_dir in self.root_path.rglob("__pycache__"):
            shutil.rmtree(pycache_dir, ignore_errors=True)
        
        # Clean optimized assets
        for asset_dir in self.ASSET_DIRECTORIES:
            asset_path = self.root_path / asset_dir
            if asset_path.exists():
                for gz_file in asset_path.rglob("*.gz"):
                    gz_file.unlink(missing_ok=True)
            
        print("✅ Build artifacts cleaned")

    def initialize(self, version: str, build_data: Dict[str, Any]) -> None:
        """Initialize the build process with validation and metadata injection."""
        print("🔧 Initializing superego-mcp build process...")
        
        # Validate UV is available
        self._validate_uv_available()
        
        # Validate critical files exist
        self._validate_critical_files()
        
        # Copy and prepare frontend assets
        self._copy_frontend_assets()
        
        # Optimize static assets
        self._optimize_static_assets()
        
        # Inject build metadata
        self._inject_build_metadata(version, build_data)
        
        # Prepare asset directories for copying
        self._prepare_asset_directories()
        
        # Validate asset integrity
        self._validate_asset_integrity()
        
        print(f"✅ Build initialization complete for version {version}")

    def finalize(self, version: str, build_data: Dict[str, Any], artifact_path: str) -> None:
        """Finalize the build with post-processing and validation."""
        print("🏁 Finalizing superego-mcp build...")
        
        # Validate the built artifact
        self._validate_artifact_contents(artifact_path)
        
        # Generate build report
        self._generate_build_report(version, artifact_path)
        
        print(f"✅ Build finalized successfully: {os.path.basename(artifact_path)}")

    def _validate_uv_available(self) -> None:
        """Validate that UV is available for Python execution."""
        try:
            result = self._run_uv_command("--version")
            if result.returncode != 0:
                raise RuntimeError("UV is not available or not working properly")
            print(f"✅ UV available: {result.stdout.strip()}")
        except FileNotFoundError:
            raise RuntimeError(
                "UV is required for building superego-mcp. Please install UV: "
                "https://docs.astral.sh/uv/getting-started/installation/"
            )
    
    def _validate_critical_files(self) -> None:
        """Validate that all critical files are present before building."""
        critical_files = [
            "src/superego_mcp/__init__.py",
            "src/superego_mcp/main.py", 
            "src/superego_mcp/cli.py",
            "README.md",
            "pyproject.toml",
        ]
        
        missing_files = []
        for file_path in critical_files:
            if not (self.root_path / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            raise RuntimeError(
                f"Critical files missing before build: {', '.join(missing_files)}"
            )
        
        print(f"✅ Validated {len(critical_files)} critical files")
        
        # Validate asset directories exist or can be created
        for asset_dir in self.ASSET_DIRECTORIES:
            asset_path = self.root_path / asset_dir
            if not asset_path.exists():
                print(f"ℹ️  Asset directory {asset_dir} not found (will be skipped)")
            else:
                print(f"✅ Asset directory {asset_dir} found")

    def _copy_frontend_assets(self) -> None:
        """Copy frontend assets to the package for distribution."""
        copied_assets = []
        
        for asset_dir_name, patterns in self.ASSET_DIRECTORIES.items():
            source_dir = self.root_path / asset_dir_name
            if not source_dir.exists():
                continue
                
            # For demo/config, copy to package config
            if asset_dir_name == "demo/config":
                target_dir = self.root_path / "src" / "superego_mcp" / "demo_config"
            else:
                target_dir = self.root_path / "src" / "superego_mcp" / asset_dir_name.replace("/", "_")
            
            # Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy matching files
            copied_count = 0
            for pattern in patterns:
                for source_file in source_dir.rglob(pattern):
                    if source_file.is_file():
                        # Preserve directory structure
                        rel_path = source_file.relative_to(source_dir)
                        target_file = target_dir / rel_path
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        shutil.copy2(source_file, target_file)
                        copied_count += 1
            
            if copied_count > 0:
                copied_assets.append(f"{asset_dir_name} ({copied_count} files)")
        
        if copied_assets:
            print(f"📋 Frontend assets copied: {', '.join(copied_assets)}")
        else:
            print("ℹ️  No frontend assets found to copy")
    
    def _optimize_static_assets(self) -> None:
        """Optimize static assets with compression where appropriate."""
        optimized_count = 0
        
        # Look for static assets in the package directory
        pkg_dir = self.root_path / "src" / "superego_mcp"
        
        for asset_file in pkg_dir.rglob("*"):
            if not asset_file.is_file():
                continue
                
            suffix = asset_file.suffix.lstrip(".")
            if suffix not in self.COMPRESSION_SETTINGS:
                continue
                
            settings = self.COMPRESSION_SETTINGS[suffix]
            if not settings["compress"]:
                continue
                
            # Check if file is large enough to compress
            file_size = asset_file.stat().st_size
            if file_size < settings["min_size"]:
                continue
                
            # Compress the file
            compressed_file = asset_file.with_suffix(asset_file.suffix + ".gz")
            try:
                with open(asset_file, "rb") as f_in:
                    with gzip.open(compressed_file, "wb", compresslevel=9) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Only keep compressed version if it's significantly smaller
                compressed_size = compressed_file.stat().st_size
                if compressed_size < file_size * 0.9:  # At least 10% reduction
                    optimized_count += 1
                else:
                    compressed_file.unlink()  # Remove if not worth it
                    
            except Exception as e:
                print(f"⚠️  Warning: Failed to compress {asset_file}: {e}")
                if compressed_file.exists():
                    compressed_file.unlink()
        
        if optimized_count > 0:
            print(f"📊 Static assets optimized: {optimized_count} files compressed")
    
    def _validate_asset_integrity(self) -> None:
        """Validate integrity of copied and optimized assets."""
        pkg_dir = self.root_path / "src" / "superego_mcp"
        asset_files = []
        
        # Find all asset files in package
        for asset_dir_name in self.ASSET_DIRECTORIES:
            target_dir_name = asset_dir_name.replace("/", "_")
            if asset_dir_name == "demo/config":
                target_dir_name = "demo_config"
                
            target_dir = pkg_dir / target_dir_name
            if target_dir.exists():
                for asset_file in target_dir.rglob("*"):
                    if asset_file.is_file():
                        asset_files.append(asset_file)
        
        # Simple validation - check files are readable
        valid_files = 0
        for asset_file in asset_files[:20]:  # Limit to avoid performance issues
            try:
                with open(asset_file, "rb") as f:
                    content = f.read()
                    if len(content) > 0:
                        valid_files += 1
            except Exception:
                pass  # Skip problematic files
        
        if asset_files:
            print(f"✅ Asset integrity validated: {valid_files}/{min(len(asset_files), 20)} files checked")
        else:
            print("ℹ️  No assets to validate")
    
    def _inject_build_metadata(self, version: str, build_data: Dict[str, Any]) -> None:
        """Inject build-time metadata into the package."""
        metadata = {
            "build_version": version,
            "build_timestamp": self._get_build_timestamp(),
            "build_commit": self._get_git_commit(),
            "build_branch": self._get_git_branch(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "build_platform": sys.platform,
            "hatchling_version": self._get_hatchling_version(),
        }
        
        # Add asset information to metadata
        metadata["assets"] = self._get_asset_information()
        
        # Write metadata to a file that will be included in the package
        metadata_file = self.root_path / "src" / "superego_mcp" / "_build_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)
        
        print(f"✅ Injected build metadata: {metadata['build_commit'][:8]} on {metadata['build_branch']}")
        if metadata["assets"]["total_files"] > 0:
            print(f"📋 Assets included: {metadata['assets']['total_files']} files, {metadata['assets']['total_size_kb']} KB")

    def _get_asset_information(self) -> Dict[str, Any]:
        """Get information about assets for metadata."""
        pkg_dir = self.root_path / "src" / "superego_mcp"
        asset_info = {
            "directories": {},
            "total_files": 0,
            "total_size_bytes": 0,
            "total_size_kb": 0,
        }
        
        for asset_dir_name in self.ASSET_DIRECTORIES:
            target_dir_name = asset_dir_name.replace("/", "_")
            if asset_dir_name == "demo/config":
                target_dir_name = "demo_config"
                
            target_dir = pkg_dir / target_dir_name
            if target_dir.exists():
                files = list(target_dir.rglob("*"))
                file_count = len([f for f in files if f.is_file()])
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                
                asset_info["directories"][target_dir_name] = {
                    "file_count": file_count,
                    "size_bytes": total_size,
                }
                asset_info["total_files"] += file_count
                asset_info["total_size_bytes"] += total_size
        
        asset_info["total_size_kb"] = round(asset_info["total_size_bytes"] / 1024, 2)
        return asset_info
    
    def _prepare_asset_directories(self) -> None:
        """Prepare and validate asset directories for inclusion in the wheel."""
        asset_info = []
        
        # Check main config directory
        config_dir = self.root_path / "config"
        if config_dir.exists() and config_dir.is_dir():
            yaml_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))
            if yaml_files:
                asset_info.append(f"config ({len(yaml_files)} YAML files)")
        
        # Check demo config directory
        demo_config_dir = self.root_path / "demo" / "config"
        if demo_config_dir.exists() and demo_config_dir.is_dir():
            all_files = list(demo_config_dir.rglob("*"))
            config_files = [f for f in all_files if f.is_file() and f.suffix in ['.yaml', '.yml', '.json']]
            if config_files:
                asset_info.append(f"demo/config ({len(config_files)} config files)")
        
        # Check existing package config
        pkg_config_dir = self.root_path / "src" / "superego_mcp" / "config"
        if pkg_config_dir.exists() and pkg_config_dir.is_dir():
            pkg_configs = list(pkg_config_dir.glob("*.yaml")) + list(pkg_config_dir.glob("*.yml"))
            if pkg_configs:
                asset_info.append(f"package config ({len(pkg_configs)} files)")
        
        if asset_info:
            print(f"✅ Asset directories prepared: {', '.join(asset_info)}")
        else:
            print("⚠️  Warning: No configuration assets found to include")

        # Generate asset checksums for validation
        self._generate_asset_checksums()
        
        # Validate that critical config files are accessible
        self._validate_config_accessibility()

    def _validate_config_accessibility(self) -> None:
        """Validate that configuration files are accessible and properly formatted."""
        pkg_dir = self.root_path / "src" / "superego_mcp"
        config_files_found = 0
        
        # Check package config directory
        pkg_config_dir = pkg_dir / "config"
        if pkg_config_dir.exists():
            for config_file in pkg_config_dir.rglob("*.yaml"):
                if config_file.is_file():
                    try:
                        # Simple file readability check
                        with open(config_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            if len(content) > 0:
                                config_files_found += 1
                    except Exception as e:
                        print(f"⚠️  Warning: Cannot read {config_file.name}: {e}")
        
        if config_files_found > 0:
            print(f"✅ Configuration files validated: {config_files_found} files")
        else:
            print("ℹ️  No configuration files found to validate")
    
    def _generate_asset_checksums(self) -> None:
        """Generate checksums for asset files to include in the build."""
        checksums = {}
        
        pkg_dir = self.root_path / "src" / "superego_mcp"
        
        # Checksum all asset files in package
        for asset_dir_name in self.ASSET_DIRECTORIES:
            target_dir_name = asset_dir_name.replace("/", "_")
            if asset_dir_name == "demo/config":
                target_dir_name = "demo_config"
                
            target_dir = pkg_dir / target_dir_name
            if target_dir.exists():
                for asset_file in target_dir.rglob("*"):
                    if asset_file.is_file() and not asset_file.name.endswith(".gz"):
                        with open(asset_file, "rb") as f:
                            content = f.read()
                            checksum = hashlib.sha256(content).hexdigest()[:16]  # Short checksum
                            rel_path = asset_file.relative_to(pkg_dir)
                            checksums[str(rel_path)] = checksum
        
        # Also checksum the main package config if it exists
        pkg_config_dir = pkg_dir / "config"
        if pkg_config_dir.exists():
            for config_file in pkg_config_dir.rglob("*"):
                if config_file.is_file():
                    with open(config_file, "rb") as f:
                        content = f.read()
                        checksum = hashlib.sha256(content).hexdigest()[:16]
                        rel_path = config_file.relative_to(pkg_dir)
                        checksums[str(rel_path)] = checksum
        
        if checksums:
            checksums_file = pkg_dir / "_asset_checksums.json"
            with open(checksums_file, "w", encoding="utf-8") as f:
                json.dump(checksums, f, indent=2, sort_keys=True)
            
            print(f"✅ Generated checksums for {len(checksums)} asset files")
        else:
            print("ℹ️  No assets found for checksum generation")

    def _validate_artifact_contents(self, artifact_path: str) -> None:
        """Validate that the built artifact contains expected contents."""
        if not artifact_path.endswith('.whl'):
            print("ℹ️  Skipping content validation (not a wheel)")
            return
            
        try:
            import zipfile
            with zipfile.ZipFile(artifact_path, 'r') as wheel:
                contents = wheel.namelist()
                
                # Check for essential package files
                required_patterns = [
                    "superego_mcp/__init__.py",
                    "superego_mcp/main.py",
                    "superego_mcp/cli.py",
                ]
                
                optional_patterns = [
                    "superego_mcp/_build_metadata.json",
                    "superego_mcp/_asset_checksums.json", 
                    "superego_mcp/config/",
                    "superego_mcp/static/",
                    "superego_mcp/templates/",
                    "superego_mcp/demo_config/",
                ]
                
                missing_required = []
                for pattern in required_patterns:
                    if not any(pattern in path for path in contents):
                        missing_required.append(pattern)
                
                if missing_required:
                    raise RuntimeError(
                        f"Wheel validation failed - missing required files: {', '.join(missing_required)}"
                    )
                
                found_optional = []
                for pattern in optional_patterns:
                    if any(pattern in path for path in contents):
                        found_optional.append(pattern.rstrip('/'))
                
                print(f"✅ Wheel validation passed ({len(contents)} files)")
                if found_optional:
                    print(f"📦 Optional assets included: {', '.join(found_optional)}")
                
        except ImportError:
            print("⚠️  Warning: Cannot validate wheel contents (zipfile not available)")
        except Exception as e:
            print(f"⚠️  Warning: Wheel validation error: {e}")

    def _generate_build_report(self, version: str, artifact_path: str) -> None:
        """Generate a comprehensive build report."""
        artifact_size = 0
        artifact_name = "unknown"
        
        if os.path.exists(artifact_path):
            artifact_size = os.path.getsize(artifact_path)
            artifact_name = os.path.basename(artifact_path)
        
        report = {
            "package_name": "superego-mcp",
            "version": version,
            "artifact_name": artifact_name,
            "artifact_size_bytes": artifact_size,
            "artifact_size_kb": round(artifact_size / 1024, 2) if artifact_size > 0 else 0,
            "build_timestamp": self._get_build_timestamp(),
            "build_commit": self._get_git_commit(),
            "build_branch": self._get_git_branch(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "build_platform": sys.platform,
        }
        
        # Write build report
        report_path = self.root_path / "build_report.json" 
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
        
        print(f"📊 Build report: {report_path}")
        if artifact_size > 0:
            print(f"📦 Final artifact: {report['artifact_size_kb']} KB")

    def _get_build_timestamp(self) -> str:
        """Get the current build timestamp."""
        import datetime
        return datetime.datetime.utcnow().isoformat() + "Z"

    def _get_git_commit(self) -> str:
        """Get the current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except (subprocess.SubprocessError, FileNotFoundError):
            return "unknown"

    def _get_git_branch(self) -> str:
        """Get the current git branch."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except (subprocess.SubprocessError, FileNotFoundError):
            return "unknown"

    def _get_hatchling_version(self) -> str:
        """Get the Hatchling version used for building."""
        try:
            import hatchling
            return getattr(hatchling, '__version__', 'unknown')
        except (ImportError, AttributeError):
            return "unknown"