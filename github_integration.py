"""
GitHub repository integration for importing code
"""

import os
import re
import requests
import base64
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from app import db
from models import CodeFile

class GitHubIntegration:
    """Handle GitHub repository imports"""
    
    def __init__(self):
        self.api_base = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "VibeDeCoder"
        }
        
        # Add GitHub token if available
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
        
        # Directories to exclude from import (package directories, build outputs, etc.)
        # Store all as lowercase for case-insensitive matching
        self.excluded_dirs = {
            dir_name.lower() for dir_name in {
                'node_modules',
                'dist',
                'build',
                'venv',
                'env',
                '.venv',
                '__pycache__',
                '.pytest_cache',
                'site-packages',
                '.git',
                '.github',
                'vendor',
                'target',
                'bin',
                'obj',
                'coverage',
                '.idea',
                '.vscode',
                '.DS_Store',
                '.next',
                'out',
                '.nuxt',
                '.cache',
                'bower_components',
                'jspm_packages',
                '.sass-cache',
                '.gradle',
                '.mvn',
                'logs',
                'tmp',
                'temp',
                '.terraform',
                '.serverless'
            }
        }
    
    def should_exclude_directory(self, dir_name: str) -> bool:
        """Check if a directory should be excluded from import"""
        return dir_name.lower() in self.excluded_dirs
    
    def parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub URL to extract owner, repo, branch, and optional subdirectory path"""
        # Handle different GitHub URL formats
        # 1. github.com/owner/repo/tree/branch/path/to/folder
        # 2. github.com/owner/repo/tree/branch
        # 3. github.com/owner/repo.git/path/to/folder (non-standard but handle it)
        # 4. github.com/owner/repo.git
        # 5. github.com/owner/repo
        
        patterns = [
            # Match: github.com/owner/repo/tree/branch/path/to/folder
            (r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/tree/([^/]+)/(.+)', True),
            # Match: github.com/owner/repo/tree/branch
            (r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/tree/([^/]+)/?$', False),
            # Match: github.com/owner/repo.git/path (non-standard)
            (r'github\.com/([^/]+)/([^/]+?)\.git/(.+)', True),
            # Match: github.com/owner/repo.git or github.com/owner/repo/
            (r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', False),
        ]
        
        for pattern, has_path in patterns:
            match = re.search(pattern, url)
            if match:
                owner = match.group(1)
                repo = match.group(2).replace('.git', '')
                
                if has_path:
                    if len(match.groups()) == 4:
                        # Format: github.com/owner/repo/tree/branch/path
                        branch = match.group(3)
                        path = match.group(4).rstrip('/')
                    else:
                        # Format: github.com/owner/repo.git/path
                        branch = 'main'
                        path = match.group(3).rstrip('/')
                else:
                    branch = match.group(3) if len(match.groups()) >= 3 else 'main'
                    path = ''
                
                return {
                    'owner': owner,
                    'repo': repo,
                    'branch': branch,
                    'path': path
                }
        
        return None
    
    def get_repository_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Get repository information from GitHub API"""
        try:
            url = f"{self.api_base}/repos/{owner}/{repo}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Check if it's a private repo issue
                if "Authorization" not in self.headers:
                    raise Exception(f"Repository {owner}/{repo} not found. If this is a private repository, please set the GITHUB_TOKEN environment variable.")
                else:
                    raise Exception(f"Repository {owner}/{repo} not found or you don't have access to it")
            elif response.status_code == 403:
                # Check if it's rate limit or auth issue
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_remaining == '0':
                    raise Exception("GitHub API rate limit exceeded. Please wait or set a GITHUB_TOKEN to increase your rate limit.")
                else:
                    raise Exception(f"Access denied to repository {owner}/{repo}. If this is a private repository, ensure your GITHUB_TOKEN has the necessary permissions.")
            elif response.status_code == 401:
                raise Exception("GitHub authentication failed. Please check your GITHUB_TOKEN is valid.")
            else:
                raise Exception(f"GitHub API error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to connect to GitHub: {str(e)}")
    
    def get_repository_contents(self, owner: str, repo: str, branch: str = 'main', path: str = '') -> List[Dict[str, Any]]:
        """Get repository contents recursively"""
        try:
            url = f"{self.api_base}/repos/{owner}/{repo}/contents/{path}"
            params = {'ref': branch}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Try with 'master' branch if 'main' doesn't exist
                if branch == 'main':
                    return self.get_repository_contents(owner, repo, 'master', path)
                raise Exception(f"Path {path} not found in repository")
            else:
                raise Exception(f"GitHub API error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get repository contents: {str(e)}")
    
    def get_file_content(self, download_url: str) -> str:
        """Download file content from GitHub"""
        try:
            response = requests.get(download_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Try to decode as UTF-8
            try:
                return response.content.decode('utf-8')
            except UnicodeDecodeError:
                # Skip binary files
                raise Exception("Binary file - skipping")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download file: {str(e)}")
    
    def is_supported_file(self, filename: str) -> bool:
        """Check if file is supported for analysis"""
        supported_extensions = {
            'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'htm', 'css',
            'c', 'cpp', 'cc', 'cxx', 'h', 'hpp', 'cs', 'go',
            'java', 'php', 'rb', 'swift', 'kt', 'rs'
        }
        
        if '.' not in filename:
            return False
        
        ext = filename.split('.')[-1].lower()
        return ext in supported_extensions
    
    def get_language_from_extension(self, filename: str) -> str:
        """Determine programming language from file extension"""
        if '.' not in filename:
            return 'unknown'
        
        ext = filename.split('.')[-1].lower()
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'javascript',
            'tsx': 'javascript',
            'html': 'html',
            'htm': 'html',
            'css': 'css',
            'c': 'c',
            'h': 'c',
            'cpp': 'cpp',
            'cc': 'cpp',
            'cxx': 'cpp',
            'hpp': 'cpp',
            'cs': 'csharp',
            'go': 'go',
            'java': 'java',
            'php': 'php',
            'rb': 'ruby',
            'swift': 'swift',
            'kt': 'kotlin',
            'rs': 'rust'
        }
        
        return language_map.get(ext, 'unknown')
    
    def import_repository(self, url: str, analysis_id: int, github_token: Optional[str] = None, max_files: int = 100, max_file_size: int = 1024*1024) -> List[CodeFile]:
        """Import a GitHub repository for analysis
        
        Args:
            url: GitHub repository URL
            analysis_id: ID of the analysis record
            github_token: Optional GitHub PAT for private repos (overrides system token)
            max_files: Maximum number of files to import
            max_file_size: Maximum file size in bytes
        """
        # Use per-import token if provided, otherwise use system token
        original_headers = self.headers.copy()
        if github_token:
            self.headers = self.headers.copy()
            self.headers["Authorization"] = f"token {github_token}"
        
        # Initialize code_files list before try block
        code_files = []
        
        try:
            # Parse GitHub URL
            repo_info = self.parse_github_url(url)
            if not repo_info:
                raise Exception("Invalid GitHub URL format")
            
            owner = repo_info['owner']
            repo = repo_info['repo']
            branch = repo_info['branch']
            start_path = repo_info.get('path', '')
            
            # Get repository information
            repo_data = self.get_repository_info(owner, repo)
            if not repo_data:
                raise Exception("Failed to get repository information")
            
            # Import files
            file_count = 0
            
            def process_contents(contents: List[Dict[str, Any]], current_path: str = ''):
                nonlocal file_count, code_files
                
                if file_count >= max_files:
                    return
                
                for item in contents:
                    if file_count >= max_files:
                        break
                    
                    if item['type'] == 'file':
                        filename = item['name']
                        file_path = item['path']
                        
                        # Check if file is supported
                        if not self.is_supported_file(filename):
                            continue
                        
                        # Check file size
                        if item.get('size', 0) > max_file_size:
                            print(f"Skipping large file: {file_path} ({item.get('size', 0)} bytes)")
                            continue
                        
                        try:
                            # Download file content
                            content = self.get_file_content(item['download_url'])
                            
                            # Determine language
                            language = self.get_language_from_extension(filename)
                            
                            # Create CodeFile object
                            code_file = CodeFile(
                                filename=filename,
                                file_path=file_path,
                                language=language,
                                content=content,
                                size_bytes=len(content.encode('utf-8')),
                                line_count=len(content.splitlines()),
                                analysis_id=analysis_id
                            )
                            
                            db.session.add(code_file)
                            code_files.append(code_file)
                            file_count += 1
                            
                            print(f"Imported: {file_path} ({language})")
                            
                        except Exception as e:
                            print(f"Failed to import {file_path}: {str(e)}")
                            continue
                    
                    elif item['type'] == 'dir':
                        # Skip excluded directories (node_modules, venv, etc.)
                        dir_name = item['name']
                        if self.should_exclude_directory(dir_name):
                            print(f"Skipping excluded directory: {item['path']}")
                            continue
                        
                        # Recursively process directories
                        if file_count < max_files:
                            try:
                                subcontents = self.get_repository_contents(owner, repo, branch, item['path'])
                                process_contents(subcontents, item['path'])
                            except Exception as e:
                                print(f"Failed to process directory {item['path']}: {str(e)}")
                                continue
            
            # Start processing from specified path (or root if no path specified)
            contents = self.get_repository_contents(owner, repo, branch, start_path)
            process_contents(contents, start_path)
            
            if not code_files:
                raise Exception("No supported code files found in repository")
            
            return code_files
            
        except Exception as e:
            # Clean up any added files if import fails
            for code_file in code_files:
                db.session.delete(code_file)
            raise e
        finally:
            # Restore original headers
            self.headers = original_headers

# Global instance
github_integration = GitHubIntegration()

def import_github_repo(url: str, analysis_id: int, github_token: Optional[str] = None) -> List[CodeFile]:
    """Import a GitHub repository for analysis
    
    Args:
        url: GitHub repository URL
        analysis_id: ID of the analysis record
        github_token: Optional GitHub PAT for private repos
    """
    return github_integration.import_repository(url, analysis_id, github_token)
