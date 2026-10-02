# Purpose:
# Shared base class for all social actions (post, reply, like, follow)
import json
from datetime import datetime, timezone
import os

from src.identity.signer import Signer
from src.identity.keypair import KeyPair

class ActionBase:
    publish_locally = True
    def __init__(self, social_path: str):
        self.social_path = social_path
        self.actions_path = os.path.join(social_path, "actions")
        os.makedirs(self.actions_path, exist_ok=True)
    
    # Build fields common to all actions
    def _build_base(self, action_type: str, public_key: str, action_id: str):
        return {
            "id": action_id,
            "type": action_type,
            "author": public_key,
            "created": self._timestamp()
        }
    # Child classes override this to add extra fields
    def _extend(self, obj: dict, **kwargs):
        return obj
    
    # Template method: shared creation workflow
    def _create(self, action_type: str, actions_path=None, **kwargs):
        public_key, private_key_hex, handle  = self._load_identity()
        action_id = self._next_id(action_type, handle, actions_path)
        # Author verification: ensure the public key stored in profile.json matches private key
        # we are using to sign actions. Thus preventing forged actions, corrupted identities and invalid signatures
        signer = Signer(private_key_hex)
        derived_pubkey_hex = signer.signing_key.verify_key.encode().hex()
        derived_public_key = f"ed25519:{derived_pubkey_hex}"
        if derived_public_key != public_key:
            raise ValueError(
                "Author verification failed: publicKey in profile.json does not match private.key"
            )
        # Base fields
        obj = self._build_base(action_type, public_key, action_id)
        # Child-specific fields
        obj = self._extend(obj, **kwargs)
        # Sign + write
        self._sign_action(obj, private_key_hex)
        path = self._write(obj, actions_path)

        return path, obj

    def _next_id(self, prefix: str, handle: str, actions_path=None) -> str:
        # Use the provided actions_path if given, otherwise fall back to self.actions_path
        actions_path = actions_path or self.actions_path
        # Generate the next sequential ID for this action type.
        all_files = os.listdir(actions_path)
        numbers = []
        for name in all_files:
            if not name.endswith(".json"):
                continue
            # filenames now look like: post-bharat.social-001.json
            # So we extract the LAST part (001) instead of the middle part. 
            parts = name.split("-")
            if len(parts) < 3:
                continue
            try:
                num = int(parts[-1].replace(".json", ""))
                numbers.append(num)
            except Exception:
                continue
        # Determine the next number, if no existing files, start at 1
        next_num = (max(numbers) + 1) if numbers else 1
        # <actionType>-<handle>-<counter>
        return f"{prefix}-{handle}-{next_num:03d}" 
    
    def _timestamp(self) -> str:
        # Return the current UTC timestamp in ISO 8601 format with 'Z' suffix
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
   
    def _sign_action(self, action: dict, private_key: str) -> None:
        # Sign the action JSON using the provided private key
        signer = Signer(private_key)
        action["signature"] = signer.sign_json(action)

    def _write(self, action: dict, actions_path=None) -> str:
        # Write the JSON object to /social/actions/<id>.json.
        # Note: The action object already contains and "id" (added earlier by the action creator using_next_id())
        # This simply uses that existing ID to name the file
        
        actions_path = actions_path or self.actions_path
        os.makedirs(actions_path, exist_ok=True)

        raw_id = action["id"]
        # remove accidental '.json' if it already exists
        if raw_id.endswith(".json"):
            raw_id = raw_id[:-5] # strip the last 5 chars ".json"

        filename = f"{raw_id}.json"
        path = os.path.join(actions_path, filename)
        # Save the JSON object to disk
        with open(path, "w") as f:
            json.dump(action, f, indent=2)
        return path
    
    def _load_identity(self):        
        # Load publicKey from /social/profile.json
        profile_path = os.path.join(self.social_path, "profile.json")
        with open(profile_path, "r") as file:
            profile = json.load(file)
        public_key = profile["publicKey"]
        handle = profile["handle"]

        # Load identity.json
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        identity_json_path = os.path.join(project_root, "client", "identity.json")

        with open(identity_json_path, "r") as f:
            identity_data = json.load(f)
        active_identity = identity_data["activeIdentity"]

            # Load private key from client/state/<activeIdentity>/keystore/private.key
        private_key_path = os.path.join(
            project_root,
            "client",
            "state",
            active_identity,
            "keystore",
            "private.key"
        )

        with open(private_key_path, "r") as file:
            private_key = file.read().strip()

        return public_key, private_key, handle
    

    
    
    
