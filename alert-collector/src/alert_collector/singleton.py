from threading import Lock


class SingletonMeta(type):
    """Metaclass for creating singleton classes."""

    _instances = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

    def get_instance(cls):
        """Return existing instance for a singleton class, if any."""
        return cls._instances.get(cls)
