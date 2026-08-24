def inspect_json(obj, indent=0):
    prefix = " " * indent

    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{prefix}{k}: {type(v).__name__}")
            inspect_json(v, indent + 4)

    elif isinstance(obj, list):
        print(f"{prefix}List[{len(obj)}]")
        if obj:
            inspect_json(obj[0], indent + 4)