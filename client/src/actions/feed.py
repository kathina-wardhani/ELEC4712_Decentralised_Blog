import os
import json
import git
from collections import defaultdict
from src.actions.base import ActionBase
from src.actions.action_verifier import ActionVerifier

import urllib.request

class ShowFeedAction(ActionBase):

    publish_locally = False
    DIRECTORY_URL = "https://gargster.github.io/social-directory/directory.json"

    def __init__(self, social_path):
        super().__init__(social_path)

        self.actions = []
        self.pubkey_to_handle = {}

        self.my_posts = []
        self.my_following = set()
        self.followed_users_posts = []
        self.all_posts = []

        self.indexed = None

    # --------------------------------------------------------
    # MAIN ENTRY POINT
    # --------------------------------------------------------

    def run(self, args):
        active_handle = self.get_active_handle()
        followers_only = args.followers_only

        # 1. Load all actions
        self.load_actions()

        # 2. Load profile mapping
        self.load_profile_mapping()

        # 3. Index actions
        self.indexed = self.index_actions(self.actions)

        # 4. Categorize feed sections
        self.categorize_sections(active_handle, followers_only)

        # 5. Render feed
        self.render_structured_feed(active_handle, followers_only)

        return None, None

    def get_active_handle(self):
        repo_name = os.path.basename(os.path.dirname(self.social_path))
        return repo_name.replace("-social", ".social")

    # --------------------------------------------------------
    # LOAD ACTIONS
    # --------------------------------------------------------

    def load_actions(self):
        actions_dir = os.path.join(self.social_path, "actions")

        for filename in os.listdir(actions_dir):
            if filename.endswith(".json"):
                path = os.path.join(actions_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        obj = json.load(f)
                    if ActionVerifier.verify(obj):
                        self.actions.append(obj)
                    else:
                        print(f"[FEED] Rejected invalid action: {path}")
                except Exception as e:
                    print(f"[FEED] Error reading {path}: {e}")

    def load_profiles_from_remotes(self):
        """
        Load profiles from existing Git remotes.
        These remotes already exist because the user follows those users.
        No new remotes or clones are created.
        """
        try:
            repo_root = os.path.dirname(self.social_path)
            repo = git.Repo(repo_root)
            git_cmd = git.cmd.Git(repo.working_tree_dir)

            for remote in repo.remotes:
                if remote.name == "origin":
                    continue

                try:
                    raw_json = git_cmd.show(
                        f"{remote.name}/main:social/profile.json"
                    )

                    profile = json.loads(raw_json)

                    pk = profile.get("publicKey")
                    handle = profile.get("handle")

                    if pk and handle:
                        self.pubkey_to_handle[pk] = handle

                except Exception as e:
                    print(
                        f"[FEED] Could not load profile from "
                        f"remote {remote.name}: {e}"
                    )

        except Exception as e:
            print(f"[FEED] Could not load profiles from remotes: {e}")

    # --------------------------------------------------------
    # LOAD PROFILE MAPPING
    # --------------------------------------------------------
    def load_profile_mapping(self):
        # --------------------------------------------------------
        # 1. Load my own profile
        # --------------------------------------------------------
        profile_path = os.path.join(self.social_path, "profile.json")

        try:
            with open(profile_path, "r", encoding="utf-8") as pf:
                profile = json.load(pf)

            pk = profile.get("publicKey")
            handle = profile.get("handle", self.get_active_handle())

            if pk:
                self.pubkey_to_handle[pk] = handle

        except Exception as e:
            print(f"[FEED] Could not load profile.json: {e}")

        # --------------------------------------------------------
        # 2. Load profiles from existing followed-user remotes
        # --------------------------------------------------------
        #self.load_profiles_from_remotes()

        # --------------------------------------------------------
        # 3. Load public discovery directory
        # --------------------------------------------------------
        try:
            with urllib.request.urlopen(self.DIRECTORY_URL, timeout=5) as response:
                directory = json.load(response)

        except Exception as e:
            print(f"[FEED] Could not load discovery directory: {e}")
            directory = {}

        # --------------------------------------------------------
        # 4. Discover profiles from repository URLs
        # --------------------------------------------------------
        for handle, user_info in directory.items():

            repo_url = user_info.get("repoURL")

            if not repo_url:
                continue

            # Convert:
            # https://github.com/gargster/ash-social.git
            #
            # into:
            # https://raw.githubusercontent.com/gargster/ash-social/main/social/profile.json
            #
            if repo_url.endswith(".git"):
                repo_url = repo_url[:-4]

            if repo_url.startswith("https://github.com/"):
                profile_url = (
                    repo_url.replace(
                        "https://github.com/",
                        "https://raw.githubusercontent.com/"
                    )
                    + "/main/social/profile.json"
                )
            else:
                continue

            try:
                with urllib.request.urlopen(profile_url, timeout=5) as response:
                    discovered_profile = json.load(response)

                discovered_pk = discovered_profile.get("publicKey")
                discovered_handle = discovered_profile.get("handle", handle)

                if discovered_pk and discovered_handle:
                    self.pubkey_to_handle.setdefault(discovered_pk, discovered_handle)

            except Exception as e:
                print(
                    f"[FEED] Could not load profile for "
                    f"{handle}: {e}"
                )

        # --------------------------------------------------------
        # 5. Unknown public keys remain public keys
        # --------------------------------------------------------
        for action in self.actions:
            author_pk = action.get("author")

            if author_pk and author_pk not in self.pubkey_to_handle:
                self.pubkey_to_handle[author_pk] = author_pk

    # --------------------------------------------------------
    # INDEXING
    # --------------------------------------------------------

    def index_actions(self, actions_list):

        posts_by_id = {}
        likes_by_target = defaultdict(list)
        replies_by_target = defaultdict(list)
        follows = []

        for action in actions_list:
            t = action["type"]

            if t == "post":
                posts_by_id[action["id"]] = action

            elif t == "like":
                likes_by_target[action["target"]].append(action)

            elif t == "reply":
                replies_by_target[action["inReplyTo"]].append(action)

            elif t == "follow":
                follows.append(action)

        return {
            "posts": posts_by_id,
            "likes": likes_by_target,
            "replies": replies_by_target,
            "follows": follows,
        }

    # --------------------------------------------------------
    # CATEGORIZE SECTIONS
    # --------------------------------------------------------

    def categorize_sections(self, active_handle, followers_only):

        posts = self.indexed["posts"]
        follows = self.indexed["follows"]

        self.my_following = set()
        self.my_posts = []
        self.followed_users_posts = []
        self.all_posts = []

        # Who I follow
        for f in follows:
            if self.pubkey_to_handle.get(f["author"]) == active_handle:
                target_pk = f["target"]
                target_handle = self.pubkey_to_handle.get(target_pk, target_pk)
                self.my_following.add(target_handle)

        # Categorize posts
        for post in posts.values():
            author_pk = post["author"]
            author_handle = self.pubkey_to_handle.get(author_pk, author_pk)

            # My posts
            if author_handle == active_handle:
                self.my_posts.append(post)

            # Posts from people I follow
            if author_handle in self.my_following:
                self.followed_users_posts.append(post)

            # All posts (multi-hop)
            self.all_posts.append(post)

        # Sorting
        self.my_posts.sort(key=lambda p: p["created"])
        self.followed_users_posts.sort(key=lambda p: p["created"])
        self.all_posts.sort(key=lambda p: p["created"])

        # Apply mode
        if followers_only:
            self.all_posts = []  # hide multi-hop
        else:
            self.my_posts = []
            self.followed_users_posts = []  # hide follow-only

    # --------------------------------------------------------
    # RENDER FEED
    # --------------------------------------------------------

    def render_structured_feed(self, active_handle, followers_only):

        print("\n===========================================================\n")

        # MODE: FOLLOW-ONLY
        if followers_only:
            print("===== FEED (FOLLOW-ONLY MODE) =====\n")

            if not self.my_following:
                print("(no feed available — you are not following anyone)\n")
                return

            for post in self.followed_users_posts:
                self.render_post(post)
            return

        # MODE: MULTI-HOP
        print("===== FEED (MULTI-HOP MODE) =====\n")

        for post in self.all_posts:
            self.render_post(post)

    # --------------------------------------------------------
    # RENDER SINGLE POST
    # --------------------------------------------------------

    def render_post(self, post):
        author_pk = post["author"]
        author_handle = self.pubkey_to_handle.get(author_pk, author_pk)
        post_id = post["id"]
        content = post.get("content", "")
        created = post["created"]

        print(f"{author_handle} — {created}")
        print(f"POST: {content}")

        # Likes (dedupe)
        raw_likes = self.indexed["likes"].get(post_id, [])
        unique_likes = {l["author"]: l for l in raw_likes}

        if unique_likes:
            print(f"  ❤️ {len(unique_likes)} likes")
            for like in unique_likes.values():
                liker_handle = self.pubkey_to_handle.get(like["author"], like["author"])
                print(f"    - {liker_handle} liked this")

        # Replies
        replies = self.indexed["replies"].get(post_id, [])
        if replies:
            print(f"  💬 {len(replies)} replies")
            for r in replies:
                replier_handle = self.pubkey_to_handle.get(r["author"], r["author"])
                print(f"    - {replier_handle}: {r['content']}")

        print("\n----------------------------------------\n")
