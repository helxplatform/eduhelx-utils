"""
Basic git wrapper for common Eduhelx git operations.
Note that error handling here is not reliable, this should be rewritten probably.
"""

import re
from .process import execute

class GitException(Exception):
    pass

class InvalidGitRepositoryException(GitException):
    pass

def get_repo_root(path="./") -> str:
    (root, err, exit_code) = execute(["git", "rev-parse", "--show-toplevel"], cwd=path)
    if err != "":
        raise InvalidGitRepositoryException()
    return root

def get_remote(name="origin", path="./") -> str:
    (remote, err, exit_code) = execute(["git", "remote", "get-url", name], cwd=path)
    if err != "":
        raise InvalidGitRepositoryException()
    return remote
    
def get_commit_info(commit_id: str, path="./"):
    fmt = "%an%n%ae%n%cn%n%ce"
    (out, err, exit_code) = execute(["git", "show", "-s", f"--format={ fmt }", commit_id], cwd=path)
    if err != "":
        raise InvalidGitRepositoryException()
    
    [author_name, author_email, committer_name, committer_email] = out.split("\n")

    (message_out, err, exit_code) = execute(["git", "show", "-s", f"--format=%B", commit_id], cwd=path)
    if err != "":
        raise InvalidGitRepositoryException()

    return {
        "id": commit_id,
        "message": message_out,
        "author_name": author_name,
        "author_email": author_email,
        "committer_name": committer_name,
        "committer_email": committer_email
    }

def get_head_commit_id(path="./") -> str:
    (out, err, exit_code) = execute(["git", "rev-parse", "HEAD"], cwd=path)
    if err != "":
        # Note: this will also error if ran on a repository with 0 commits,
        # although that should never be a use-case so it should be alright.
        raise InvalidGitRepositoryException()
    return out

def get_tail_commit_id(path="./") -> str:
    (out, err, exit_code) = execute(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=path)
    if err != "":
        # Note: this will also error if ran on a repository with 0 commits,
        # although that should never be a use-case so it should be alright.
        raise InvalidGitRepositoryException()
    return out
    
def clone_repository(remote: str, path="./"):
    (out, err, exit_code) = execute(["git", "clone", remote, path])
    # Git clone outputs human-useful information to stderr.
    last_line = err.split("\n")[-1]
    if last_line.startswith("fatal:"):
        raise GitException(last_line)

def get_repo_name(path="./") -> str:
    (out, err, exit_code) = execute(["git", "config", "--get", "remote.origin.url"], cwd=path)
    if out == "" or err != "":
        raise InvalidGitRepositoryException()
    # Technically, a git remote URL can contain quotes, so it could break out of the quotations around `out`.
    # However, since execute is not executing in shell mode, it can't perform command substitution so there isn't
    # any risk involved here.
    (out, err, exit_code) = execute(["basename", "-s", ".git", out])
    if err != "":
        raise GitException(err)
    return out

def add_remote(remote_name: str, remote_url: str, path="./"):
    (out, err, exit_code) = execute(["git", "remote", "add", remote_name, remote_url], cwd=path)
    if err != "":
        raise InvalidGitRepositoryException()

def stage_files(files: str | list[str], path="./") -> list[tuple[str,]]:
    if isinstance(files, str): files = [files]

    (out, err, exit_code) = execute(["git", "add", "--verbose", *files], cwd=path)
    if err != "":
        raise InvalidGitRepositoryException()

    return [line.split(" ", 1) for line in out.splitlines()]

def commit(summary: str, description: str | None = None, path="./") -> str:
    description_args = ["-m", description] if description is not None else []
    (out, err, exit_code) = execute(["git", "commit", "--allow-empty", "-m", summary, *description_args], cwd=path)

    if err != "":
        raise InvalidGitRepositoryException()

    if exit_code != 0:
        raise GitException(out)
    
    # `git commit` does return the short version of the generated commit, but we want to return the full version.
    return get_head_commit_id(path=path)

def push(remote_name: str, branch_name: str, path="./"):
    (out, err, exit_code) = execute(["git", "push", remote_name, branch_name], cwd=path)
    if exit_code != 0:
        raise InvalidGitRepositoryException()