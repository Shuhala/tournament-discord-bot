from dataclasses import dataclass, fields, asdict, is_dataclass


@dataclass
class BaseDataClass:
    def __post_init__(self):
        """
        Convert all fields of type `dataclass` into an instance of the
        specified data class if the current value is of type dict.

        There's some real sketchy stuff here bro.
        """

        def unpack_values(field_type, val):
            """ unpack dict if field exists for this type """
            return field_type(
                **{
                    k: v
                    for k, v in val.items()
                    if k in {ft.name for ft in fields(field_type)}
                }
            )

        cls = type(self)
        for f in fields(cls):
            is_list_of_dataclass = (
                hasattr(f.type, "_name")
                and f.type._name == "List"
                and is_dataclass(next(iter(f.type.__args__), None))
            )
            # if the field is not a dataclass, OR is not a List of dataclasses
            if not is_dataclass(f.type) and not is_list_of_dataclass:
                continue

            value = getattr(self, f.name)

            if isinstance(value, dict):
                new_value = unpack_values(f.type, value)
                setattr(self, f.name, new_value)
            elif isinstance(value, list):
                new_value = []
                for v in value:
                    if isinstance(v, dict):
                        new_value.append(unpack_values(f.type.__args__[0], v))
                setattr(self, f.name, new_value)

    @classmethod
    def from_dict(cls, values: dict):
        """ Ignore dict keys if they're not a field of the dataclass """
        class_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in values.items() if k in class_fields})

    def to_dict(self):
        return asdict(self)
