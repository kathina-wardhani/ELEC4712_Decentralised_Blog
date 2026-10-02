import os
import git
import json
from src.actions.base import ActionBase
from src.discovery.profile_verifier import ProfileVerifier


class FollowAction(ActionBase):

    def _extend(self, obj, target):
        obj["target"] = target
        return obj

    def create_follow(self, target_public_key):
        return self._create("follow", target=target_public_key)

    # -------------------------------------------------------
    # Git-native profile.json fetch (AFTER remote + fetch)
    # -------------------------------------------------------
    def fetch_profile_git(self, repo, handle):
        """
        Fetch profile.json using pure Git:
        1. git fetch <handle> main
        2. git show <handle>/main:social/profile.json
        """

        print(f"[FOLLOW] Fetching remote branch: {handle}/main")
        repo.remotes[handle].fetch("main")

        git_cmd = git.cmd.Git(repo.working_tree_dir)

        try:
            raw_json = git_cmd.show(f"{handle}/main:social/profile.json")
        except Exception as e:
            raise Exception(
                f"[FOLLOW] profile.json missing in remote branch {handle}/main\n{e}"
            )

        print("[FOLLOW] Successfully fetched profile.json via Git")
        return json.loads(raw_json)

    # -------------------------------------------------------
    # Add remote BEFORE fetching profile.json
    # -------------------------------------------------------
    def add_remote(self, repo, handle, repo_url):
        if handle not in [r.name for r in repo.remotes]:
            print(f"[FOLLOW] Adding remote {handle} → {repo_url}")
            repo.create_remote(handle, repo_url)
        else:
            print(f"[FOLLOW] Remote {handle} already exists")

    # -------------------------------------------------------
    # Main FOLLOW logic
    # -------------------------------------------------------
    def run(self, args):
        handle = args.target_handle
        repo_url = args.target_repo_url

        print(f"[FOLLOW] Following {handle}")
        print(f"[FOLLOW] Repo URL = {repo_url}")

        # Load identity repo
        identity_repo_root = os.path.dirname(self.social_path)
        repo = git.Repo(identity_repo_root)

        # Step 1: Add remote FIRST
        self.add_remote(repo, handle, repo_url)

        # Step 2: Fetch remote + read profile.json
        profile = self.fetch_profile_git(repo, handle)

        # Step 3: Verify profile.json
        pv = ProfileVerifier(profile)
        verified = pv.verify()
        target_public_key = verified["publicKey"]
        print(f"[FOLLOW] Verified publicKey = {target_public_key}")

        # Step 4: Create follow action JSON
        path, obj = self.create_follow(target_public_key)
        print(f"[FOLLOW] Created follow action at {path}")

        return path, obj
