"""Local file operations for working with PyTorch repository directly."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class LocalFileOperations:
    """Handle local file operations for PyTorch repository."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Read content of a file relative to repo root."""
        try:
            full_path = self.repo_path / file_path
            if not full_path.exists():
                return None
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Write content to a file relative to repo root."""
        try:
            full_path = self.repo_path / file_path
            # Create directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Successfully wrote file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            return False
    
    def search_code(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for code using ripgrep."""
        try:
            # Use ripgrep for fast searching
            cmd = [
                "rg", 
                "--type", "py",  # Focus on Python files
                "--type", "cpp", # Include C++ files
                "--type", "c",   # Include C files
                "--line-number",
                "--max-count", str(max_results),
                "--no-heading",
                "--with-filename",
                query,
                str(self.repo_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.warning(f"ripgrep search failed for query '{query}'")
                return []
            
            results = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    # Parse ripgrep output: file:line:content
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        file_path = parts[0]
                        line_num = int(parts[1])
                        content = parts[2]
                        
                        # Make path relative to repo root
                        rel_path = Path(file_path).relative_to(self.repo_path)
                        
                        results.append({
                            "path": str(rel_path),
                            "line": line_num,
                            "content": content.strip()
                        })
                except Exception as e:
                    logger.debug(f"Failed to parse ripgrep line: {line} - {e}")
                    continue
            
            return results[:max_results]
            
        except subprocess.TimeoutExpired:
            logger.error(f"Search timed out for query: {query}")
            return []
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []
    
    def find_files(self, pattern: str, max_results: int = 50) -> List[str]:
        """Find files matching a pattern."""
        try:
            cmd = ["find", str(self.repo_path), "-name", pattern, "-type", "f"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return []
            
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        rel_path = Path(line).relative_to(self.repo_path)
                        files.append(str(rel_path))
                    except ValueError:
                        continue
            
            return files[:max_results]
            
        except Exception as e:
            logger.error(f"Find files failed for pattern '{pattern}': {e}")
            return []
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file."""
        try:
            full_path = self.repo_path / file_path
            if not full_path.exists():
                return None
            
            stat = full_path.stat()
            return {
                "path": file_path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "exists": True
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return None
    
    def list_directory(self, dir_path: str = "") -> List[str]:
        """List contents of a directory."""
        try:
            full_path = self.repo_path / dir_path
            if not full_path.exists() or not full_path.is_dir():
                return []
            
            items = []
            for item in full_path.iterdir():
                rel_path = item.relative_to(self.repo_path)
                items.append(str(rel_path))
            
            return sorted(items)
            
        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")
            return []
    
    def get_recent_files(self, days: int = 7, max_results: int = 20) -> List[str]:
        """Get recently modified files using git."""
        try:
            cmd = [
                "git", "-C", str(self.repo_path),
                "log", "--name-only", "--pretty=format:", f"--since={days} days ago"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return []
            
            files = set()
            for line in result.stdout.strip().split('\n'):
                if line and not line.startswith(' '):
                    files.add(line.strip())
            
            return list(files)[:max_results]
            
        except Exception as e:
            logger.error(f"Failed to get recent files: {e}")
            return []