import argparse
from typing import Callable, List, Type, Optional, Any, Union
from collections import UserDict
from typing import Sequence
from argparse import ArgumentError
from collections.abc import Mapping, MutableMapping
import os
import yaml
from distutils.util import strtobool

from os import stat

from . import yaml_utils


# global config instance
_config:'Config' = None

# TODO: remove this duplicate code which is also in utils.py without circular deps
def deep_update(d:MutableMapping, u:Mapping, create_map:Callable[[],MutableMapping])\
        ->MutableMapping:
    for k, v in u.items():
        if isinstance(v, Mapping):
            d[k] = deep_update(d.get(k, create_map()), v, create_map)
        else:
            d[k] = v
    return d

class Config(UserDict):
    def __init__(self, config_filepath:Optional[str]=None,
                 app_desc:Optional[str]=None, use_args=False,
                 param_args: Sequence = [], resolve_redirects=True) -> None:
        """Create config from specified files and args

        Config is simply a dictionary of key, value map. The value can itself be
        a dictionary so config can be hierarchical. This class allows to load
        config from yaml. A special key '__include__' can specify another yaml relative
        file path which will be loaded first and the key-value pairs in the main file
        will override the ones in include file. You can think of included file as
        defaults provider. This allows to create one base config and then several
        environment/experiment specific configs. On the top of that you can use
        param_args to perform final overrides for a given run.

        Keyword Arguments:
            config_filepath {[str]} -- [Yaml file to load config from, could be names of files separated by semicolon which will be loaded in sequence oveeriding previous config] (default: {None})
            app_desc {[str]} -- [app description that will show up in --help] (default: {None})
            use_args {bool} -- [if true then command line parameters will override parameters from config files] (default: {False})
            param_args {Sequence} -- [parameters specified as ['--key1',val1,'--key2',val2,...] which will override parameters from config file.] (default: {[]})
            resolve_redirects -- [if True then _copy commands in yaml are executed]
        """
        super(Config, self).__init__()
        # without below Python would let static method override instance method
        self.get = super(Config, self).get

        self.args, self.extra_args = None, []

        if use_args:
            # let command line args specify/override config file
            parser = argparse.ArgumentParser(description=app_desc)
            parser.add_argument('--config', type=str, default=None,
                help='config filepath in yaml format, can be list separated by ;')
            self.args, self.extra_args = parser.parse_known_args()
            config_filepath = self.args.config or config_filepath

        if config_filepath:
            for filepath in config_filepath.strip().split(';'):
                self._load_from_file(filepath.strip())
        self._update_from_args(param_args)      # merge from params
        self._update_from_args(self.extra_args) # merge from command line

        # replace _copy paths
        # HACK: using file names to detect root config, may be there should be a flag?
        if resolve_redirects:
            yaml_utils.resolve_all(self, self)

        self.config_filepath = config_filepath

    def _load_from_file(self, filepath:Optional[str])->None:
        if filepath:
            filepath = os.path.expanduser(os.path.expandvars(filepath))
            filepath = os.path.abspath(filepath)
            with open(filepath, 'r') as f:
                config_yaml = yaml.load(f, Loader=yaml.Loader)
            if '__include__' in config_yaml:
                include_filepath = os.path.join(
                    os.path.dirname(filepath),
                    config_yaml['__include__'])
                self._load_from_file(include_filepath)
            deep_update(self, config_yaml, lambda: Config(resolve_redirects=False))
            print('config loaded from: ', filepath)

    def _update_from_args(self, args:Sequence)->None:
        i = 0
        while i < len(args)-1:
            arg = args[i]
            if arg.startswith(("--")):
                path = arg[len("--"):].split('.')
                i += Config._update_section(self, path, args[i+1])
            else: # some other arg
                i += 1

    def to_dict(self)->dict:
        return deep_update({}, self, lambda: dict()) # type: ignore

    @staticmethod
    def _update_section(section:'Config', path:List[str], val:Any)->int:
        for p in range(len(path)-1):
            sub_path = path[p]
            if sub_path in section:
                section = section[sub_path]
            else:
                return 1 # path not found, ignore this
        key = path[-1] # final leaf node value

        if key in section:
            original_val, original_type = None, None
            try:
                original_val = section[key]
                original_type = type(original_val)
                if original_type == bool: # bool('False') is True :(
                    original_type = lambda x: strtobool(x)==1
                section[key] = original_type(val)
            except Exception as e:
                raise KeyError(
                    f'Error occurred while setting key {key} to value {val}.'
                    f'The originally key is set to {original_val} which is of type {original_type}.'
                    f'Original exception: {e}')
            return 2 # path was found, increment arg pointer by 2 as we use up val
        else:
            return 1 # path not found, ignore this


    @staticmethod
    def set(instance:'Config')->None:
        global _config
        _config = instance

    @staticmethod
    def get()->'Config':
        global _config
        return _config
