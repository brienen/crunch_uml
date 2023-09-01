class Registry:
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore

    @classmethod
    def register(cls, name=None, descr=''):  # sourcery skip: or-if-exp-identity
        def inner(registered_class):
            class_name = name if name else registered_class.__name__
            # if class_name in cls._registry:
            #    raise ValueError(f"Class name {class_name} already registered!")
            cls._registry[class_name] = registered_class
            cls._descr_registry[class_name] = descr
            return registered_class

        return inner

    @classmethod
    def display_registry(cls):
        for name, reg_class in cls._registry.items():
            print(name, "->", reg_class.__name__)

    @classmethod
    def entries(cls):
        return list(cls._registry.keys())

    @classmethod
    def getinstance(cls, name):
        clazz = cls._registry.get(name)
        return clazz() if clazz is not None else None

    @classmethod
    def getDescription(cls, name):
        descr = cls._descr_registry.get(name)
        return descr if descr is not None else ''
