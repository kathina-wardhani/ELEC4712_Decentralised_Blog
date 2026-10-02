class ActionRegistry:
    _registry = {}
    @classmethod
    def register(cls, name, action_cls):
        cls._registry[name] = action_cls
    @classmethod
    def get(cls, name):
        return cls._registry.get(name)

class ActionFactory:
    @staticmethod
    def create(command, social_path):
        action_cls = ActionRegistry.get(command)
        if not action_cls:
            raise ValueError(f"Unknown action: {command}")
        return action_cls(social_path)