
class AgentConfig:
    def __init__(self, config):
        self.config = config


    def get_config_value(self, key_path, default=None):
        """
        Checks if the specified key path is present and not None in the given dictionary.

        Parameters:
        config_dict (dict): The configuration dictionary.
        key_path (list): List of nested keys leading to the desired value.
        default: The default value to return if the key is present but its value is None.

        Returns:
        The value if present and not None, otherwise raises a KeyError or ValueError.
        """
        current_dict = self.config

        for key in key_path:
            if key not in current_dict and default is not None:
                return default
            if key not in current_dict:
                raise KeyError(f"The key '{key}' is missing in the configuration.")
            current_dict = current_dict[key]

        # Raise ValueError if the final value is None (you can use default if needed)
        if current_dict is None:
            if default is not None:
                return default
            raise ValueError(f"The key path {'.'.join(key_path)} leads to a None value.")

        return current_dict
