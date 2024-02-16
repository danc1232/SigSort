'''Log and Config utilities for real-time config updates'''
import logging
import yaml
 
class Log:
    '''Custom logger object with option to suppress root log output for debugging purposes'''
    def __init__(self, name='application', level="INFO", suppress_root=False):
        self.logger = logging.getLogger(name)
        match level:
            case "DEBUG":
                _lvl = logging.DEBUG
            case "INFO":
                _lvl = logging.INFO
            case "WARN":
                _lvl = logging.WARN
            case "ERROR":
                _lvl = logging.ERROR
            case "CRITICAL":
                _lvl = logging.CRITICAL
            case _:
                _lvl = logging.INFO
        self.logger.setLevel(_lvl)

        # Create console handler with the specified log level
        ch = logging.StreamHandler()
        ch.setLevel(level)

        # Create formatter and add it to the handler
        formatter = logging.Formatter('[%(asctime)s]: [%(levelname)s] %(message)s')
        formatter.datefmt = '%Y-%m-%d %H:%M:%S'
        ch.setFormatter(formatter)

        # Add the handler to the logger
        self.logger.addHandler(ch)

        # Optionally suppress log messages from other libraries
        if suppress_root:
            logging.getLogger().setLevel(logging.WARNING)

    def get_logger(self):
        """Returns the configured logger."""
        return self.logger
    
    def update_settings(self, level='INFO', suppress_root=False):
        '''Method to update logger settings dynamically'''
        match level:
            case "DEBUG":
                _lvl = logging.DEBUG
            case "INFO":
                _lvl = logging.INFO
            case "WARN":
                _lvl = logging.WARN
            case "ERROR":
                _lvl = logging.ERROR
            case "CRITICAL":
                _lvl = logging.CRITICAL
            case _:
                _lvl = logging.INFO
        self.logger.setLevel(_lvl)

        if suppress_root:
            logging.getLogger().setLevel(logging.WARNING)
        else:
            logging.getLogger().setLevel(logging.INFO)  # or your default

class SubConfigProxy:
    def __init__(self, config, key_path):
        self._config = config
        self._key_path = key_path

    def __getitem__(self, key):
        # Fetches the current state of the subconfig directly without creating a new proxy
        subconfig = self._config.get_subconfig_data(self._key_path)
        return subconfig[key]

    def __setitem__(self, key, value):
        # Allow modifications that reflect directly in the main config
        subconfig = self._config.get_subconfig(self._key_path)
        subconfig[key] = value
        self._config.set_subconfig(self._key_path, subconfig)

    # IF NEEDED: implement other methods (__contains__, get, etc.)

class Config:
    def __init__(self, config_path):
        self.config_path = config_path
        self._config = self._load_config()
        self._subconfigs = {}
        # Initialize Log instance with settings from conf
        log_config = self._config.get('global', {}).get('logging', {})
        self.log = Log(level=log_config.get('level', 'INFO'),
                       suppress_root=log_config.get('suppress_root', False))

    def _load_config(self):
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def reload_config(self):
        self._config = self._load_config()
        # Invalidate the cached subconfigs to ensure fresh data is fetched
        self._subconfigs = {}
        # Update log
        log_config = self._config.get('global', {}).get('logging', {})
        self.log.update_settings(level=log_config.get('level', 'INFO'),
                                 suppress_root=log_config.get('suppress_root', False))

    def get_subconfig(self, key_path, update=False):
        # CREATE A NEW SUBCONFIG
        if key_path in self._subconfigs and not update:
            # Return a proxy instead of the actual subconfig
            return SubConfigProxy(self, key_path)

        subconfig = self._config
        for key in key_path:
            subconfig = subconfig.get(key, {})  # Safely navigate the config

        self._subconfigs[key_path] = subconfig
        # Return a proxy to interact with the subconfig
        return SubConfigProxy(self, key_path)

    def get_subconfig_data(self, key_path):
        """Directly fetches subconfig data for the given key path."""
        subconfig = self._config
        for key in key_path:
            try:
                subconfig = subconfig[key]
            except KeyError as exc:
                raise KeyError(f"Key path {'->'.join(key_path)} not found in configuration.") from exc
        return subconfig

    def set_subconfig(self, key_path, subconfig):
        config_section = self._config
        for key in key_path[:-1]:  # Navigate to the parent of the target subconfig
            config_section = config_section.setdefault(key, {})
        config_section[key_path[-1]] = subconfig
        # IF NEEDED: implement write back to file or other actions to persist changes?

    def get_base(self):
        return self._config
    
    def get_logger(self):
        return self.log.get_logger()