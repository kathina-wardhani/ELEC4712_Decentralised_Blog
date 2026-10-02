# Purpose
# Step-by-step testing of core components(Identuty, Signing, Profile Creation)
# Before adding CLI commands, or Git integration
import argparse
import os

# Import identity modules
from src.actions.feed import ShowFeedAction
from src.identity.keypair import KeyPair
from src.identity.signer import Signer
from src.identity.profile import ProfileCreator
# Import social action modules
from src.actions.post import PostAction
from src.actions.reply import ReplyAction
from src.actions.like import LikeAction
from src.actions.follow import FollowAction

from src.actions.action_factory import ActionRegistry, ActionFactory
from src.replication.git_publisher import GitPublisher
from src.replication.replicator import Replicator

from src.utils.identity_loader import load_identity
from src.publishing.publish_manager import PublishManager
from src.publishing.site_publisher import SitePublisher

# Correct project root (ELEC4712_Decentralised_Blog/)
project_root = os.path.dirname(os.path.dirname(__file__))


def print_allowed_commands():
    print("\n==================== Allowed Commands ====================")

    print("profile create --handle <handle> --name <name> --bio <bio>")
    print('    Example: python app.py profile create --handle bharat.social --name Bharat --bio "Student at USYD"')
    print()

    print("post <content>")
    print('    Example: python app.py post "Hello world"')
    print()

    print("reply <target_handle> <target_action_id> <content>")
    print('    Example: python app.py reply carl.social post-carl.social-003 "I agree"')
    print()

    print("like <target_handle> <target_action_id>")
    print("    Example: python app.py like carl.social post-carl.social-001")
    print()

    print("follow <target_handle> <target_repo_url>")
    print("    Example: python app.py follow alice.social https://github.com/alice/alice-social.git")
    print()

    print("replicate")
    print("    Example: python app.py replicate")
    print()

    print("feed")
    print("    Example: python app.py feed")
    print()

    print("feed --followers-only")
    print("    Example: python app.py feed --followers-only")
    print()

    print("publish --url <git-remote-url>")
    print("    Example: python app.py publish --url https://github.com/bharat/bharat-social.git")
    print()

    print("publish-site")
    print("    Example: python app.py publish-site")
    print()

    print("===========================================================\n")

def main():
    # print custom help menu each time program starts
    print_allowed_commands()
    # Create main parser
    parser = argparse.ArgumentParser(description="Decentralised Social CLI")
    # Create subcommand group
    sub = parser.add_subparsers(dest="command")

    # ---------------- POST ----------------
    post = sub.add_parser("post")
    post.add_argument("content")

    # ---------------- PROFILE ----------------
    p = sub.add_parser("profile")
    p.add_argument("create") # user must type profile create
    p.add_argument("--handle", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--bio", required=True)

    # ---------------- REPLY ----------------
    reply = sub.add_parser("reply")
    reply.add_argument("target_handle")
    reply.add_argument("target_action")
    reply.add_argument("content")

    # ---------------- LIKE ----------------
    like = sub.add_parser("like")
    like.add_argument("target_handle")
    like.add_argument("target_action")

    # ---------------- FOLLOW ----------------
    follow = sub.add_parser("follow")
    follow.add_argument("target_handle")
    follow.add_argument("target_repo_url")
    # follow.add_argument("target_public_key")

    # ---------------- REPLICATE ----------------
    replicate = sub.add_parser("replicate")


    # ---------------- PUBLISH ----------------
    publish = sub.add_parser("publish")
    publish.add_argument("--url", required=True)

    publish_site = sub.add_parser("publish-site")

    show = sub.add_parser("feed")
    # show.add_argument("include_only_followers")
    show.add_argument(
        "--followers-only",
        action="store_true",
        help="Show only posts from users you explicitly follow"
    )

    # Register Actions
    ActionRegistry.register("post", PostAction)
    ActionRegistry.register("reply", ReplyAction)
    ActionRegistry.register("like", LikeAction)
    ActionRegistry.register("follow", FollowAction)

    ActionRegistry.register("feed", ShowFeedAction)

    # Parse user input
    args = parser.parse_args()

    # If no command was provided
    if args.command is None:
        parser.print_help()
        return
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    # Load active identity
    identity = load_identity()

    # Correct SOCIAL_PATH (points to <project_root>/<repo>/social)
    SOCIAL_PATH = os.path.join(
        project_root,
        identity["repoPath"],
        "social"
    )

    if args.command == "profile":
        creator = ProfileCreator(project_root)
        creator.create_profile(args.handle, args.name, args.bio)
        print("Profile created for:", args.handle)    
        return

    # ---------------- PUBLISH ----------------
    elif args.command == "publish":
        publisher = PublishManager(project_root)
        publisher.publish(args.url)
        return

    elif args.command == "publish-site":
        identity_repo_root = os.path.dirname(SOCIAL_PATH)
        SitePublisher(project_root, identity_repo_root).publish()
        return
    
    # ---------------- REPLICATE (NEW) ----------------
    elif args.command == "replicate":
        identity_repo_root = os.path.dirname(SOCIAL_PATH)
        r = Replicator(identity_repo_root)
        r.run()
        return



    # ---------------- ALL OTHER SOCIAL ACTIONS ----------------
    # Use factory method pattern for all other social actions
    action = ActionFactory.create(args.command, SOCIAL_PATH)
    path, obj = action.run(args)

    if isinstance(action, ShowFeedAction):
        return


    print(f"{args.command.capitalize()} created at:", path)
    print(f"{args.command.capitalize()} object:", obj)
    
    # Git Publishing - repo root is where .git lives
    repo_root = os.path.join(project_root, identity["repoPath"])
    # Create a GitPublisher bound to the project root repo
    publisher = GitPublisher(repo_root)
    
    # Commit and push the newly created action file
    # obj['id'] should be like "post-001"
    publisher.publish(path, f"Add {obj['id']}")
if __name__ == "__main__":
    main()
