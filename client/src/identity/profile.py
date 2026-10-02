import os
import json
import subprocess
from datetime import datetime, timezone

from src.identity.keypair import KeyPair
from src.identity.signer import Signer

CANONICAL_URL = "https://github.com/gargster/canonical-social.git"

class ProfileCreator:
    def __init__(self, project_root: str):
        self.project_root = project_root

    # ------------------------------------------------------------
    # 1. CANONICAL CREATION (ONE TIME ONLY)
    # ------------------------------------------------------------
    def create_canonical(self, handle, display_name, bio):
        repo_name = "canonical-social"
        repo_path = os.path.join(self.project_root, repo_name)
        social_path = os.path.join(repo_path, "social")

        # Create folder structure
        os.makedirs(os.path.join(social_path, "actions"), exist_ok=True)

        # Generate canonical keypair
        keypair = KeyPair()
        public_key = keypair.public_key()
        private_key = keypair.private_key()

        profile = {
            "publicKey": public_key,
            "handle": handle,
            "repoURL": None,
            "displayName": display_name,
            "bio": bio,
            "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        signer = Signer(private_key)
        profile["signature"] = signer.sign_json(profile)

        profile_path = os.path.join(social_path, "profile.json")
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)

        # Save private key in client/state/canonical
        state_path = os.path.join(self.project_root, "client", "state", "canonical")
        os.makedirs(state_path, exist_ok=True)
        keystore = os.path.join(state_path, "keystore")
        os.makedirs(keystore, exist_ok=True)

        with open(os.path.join(keystore, "private.key"), "w") as f:
            f.write(private_key)

        # Initialize git
        subprocess.run(["git", "init"], cwd=repo_path)
        subprocess.run(["git", "add", "."], cwd=repo_path)
        subprocess.run(["git", "commit", "-m", "Initial canonical creation"], cwd=repo_path)

        print("[CANONICAL] canonical-social created.")
        return repo_path, profile_path

    # ------------------------------------------------------------
    # 2. NORMAL USER CREATION (clone canonical + overwrite profile.json)
    # ------------------------------------------------------------
    def create_user(self, handle, display_name, bio):
        identity_name = handle.split(".")[0]
        repo_name = f"{identity_name}-social"
        repo_path = os.path.join(self.project_root, repo_name)

        # Clone canonical automatically
        subprocess.run(["git", "clone", CANONICAL_URL, repo_path])
        subprocess.run(
            ["git", "config", "merge.ours.driver", "true"],
            cwd=repo_path,
            check=True
        )

        social_path = os.path.join(repo_path, "social")
        os.makedirs(os.path.join(social_path, "actions"), exist_ok=True)

        # Generate new keypair
        keypair = KeyPair()
        public_key = keypair.public_key()
        private_key = keypair.private_key()

        profile = {
            "publicKey": public_key,
            "handle": handle,
            "repoURL": None,
            "displayName": display_name,
            "bio": bio,
            "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        signer = Signer(private_key)
        profile["signature"] = signer.sign_json(profile)

        # Overwrite canonical profile.json
        profile_path = os.path.join(social_path, "profile.json")
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)

        # Save private key in client/state/<identity>/keystore
        state_path = os.path.join(self.project_root, "client", "state", identity_name)
        os.makedirs(state_path, exist_ok=True)
        keystore = os.path.join(state_path, "keystore")
        os.makedirs(keystore, exist_ok=True)

        with open(os.path.join(keystore, "private.key"), "w") as f:
            f.write(private_key)

        # Commit changes
        subprocess.run(["git", "add", "."], cwd=repo_path)
        subprocess.run(["git", "commit", "-m", "Create user profile"], cwd=repo_path)

        print(f"[USER] {handle} created by cloning canonical.")
        return repo_path, profile_path

    # ------------------------------------------------------------
    # 3. Unified entry point
    # ------------------------------------------------------------
    def create_profile(self, handle, display_name, bio):
        if handle == "canonical.social":
            return self.create_canonical(handle, display_name, bio)
        else:
            return self.create_user(handle, display_name, bio)
